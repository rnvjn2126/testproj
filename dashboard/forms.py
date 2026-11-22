import csv
import io
from datetime import timedelta
from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.forms import inlineformset_factory
from decimal import Decimal, ROUND_HALF_UP

from .models import (
    Customer, FollowUp, Product, Quote, QuotePricingSettings, RFQ, RFQLine, Supplier, SupplierOffer,
)


class StyledModelForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "field"


class CustomerForm(StyledModelForm):
    class Meta:
        model = Customer
        fields = ["name", "company_name", "email", "phone", "billing_address", "notes"]


class SupplierForm(StyledModelForm):
    class Meta:
        model = Supplier
        fields = ["name", "company_name", "email", "phone", "address", "notes"]


class ProductForm(StyledModelForm):
    class Meta:
        model = Product
        fields = ["name", "grade", "shape", "dimensions", "unit", "weight_basis", "weight_kg", "notes"]


class RFQForm(StyledModelForm):
    class Meta:
        model = RFQ
        fields = ["customer", "reference", "source", "received_on", "required_by", "notes"]
        widgets = {"received_on": forms.DateInput(attrs={"type": "date"}), "required_by": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, owner, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["customer"].queryset = Customer.objects.filter(owner=owner)


class RFQStatusForm(forms.Form):
    status = forms.ChoiceField(choices=RFQ.Status.choices, label="Enquiry status")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["status"].widget.attrs["class"] = "field"


class FollowUpForm(StyledModelForm):
    class Meta:
        model = FollowUp
        fields = ["due_on", "note"]
        widgets = {"due_on": forms.DateInput(attrs={"type": "date"})}


class QuoteStatusForm(forms.Form):
    status = forms.ChoiceField(label="Update quotation status")

    def __init__(self, *args, quote, **kwargs):
        super().__init__(*args, **kwargs)
        if quote.status in (Quote.Status.READY, Quote.Status.APPROVED):
            allowed = [Quote.Status.SENT]
        elif quote.status == Quote.Status.SENT:
            allowed = [Quote.Status.ACCEPTED, Quote.Status.LOST]
            if quote.valid_until < timezone.localdate():
                allowed.append(Quote.Status.EXPIRED)
        else:
            allowed = []
        self.fields["status"].choices = [(status, Quote.Status(status).label) for status in allowed]
        self.fields["status"].widget.attrs["class"] = "field"


class RFQLineForm(StyledModelForm):
    class Meta:
        model = RFQLine
        fields = ["product", "description", "grade", "dimensions", "quantity", "unit"]

    def __init__(self, *args, owner, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["product"].queryset = Product.objects.filter(owner=owner)
        self.fields["product"].required = False

    def clean(self):
        cleaned = super().clean()
        if not any(cleaned.get(key) for key in ("product", "description", "grade", "dimensions")):
            raise forms.ValidationError("Choose a catalogue product or enter a description, grade, or dimensions.")
        return cleaned


class SupplierOfferForm(StyledModelForm):
    class Meta:
        model = SupplierOffer
        fields = [
            "supplier", "available_quantity", "unit", "unit_price", "freight_cost",
            "packaging_cost", "delivery_days",
        ]
        widgets = {
            "available_quantity": forms.NumberInput(attrs={"step": "0.001", "min": "0.001"}),
            "unit_price": forms.NumberInput(attrs={"step": "0.0001", "min": "0.0001"}),
            "freight_cost": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "packaging_cost": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "delivery_days": forms.NumberInput(attrs={"step": "1", "min": "0"}),
        }

    def __init__(self, *args, owner, rfq_line, **kwargs):
        super().__init__(*args, **kwargs)
        self.owner = owner
        self.rfq_line = rfq_line
        self.fields["supplier"].queryset = Supplier.objects.filter(owner=owner)
        self.instance.owner = owner
        self.instance.rfq_line = rfq_line

    def clean(self):
        cleaned = super().clean()
        unit = cleaned.get("unit")
        if unit:
            self.instance.unit = unit
            if self.instance.unit_conversion_factor is None:
                self.add_error("unit", "Choose a unit that can be converted to the requested item unit.")
        return cleaned


class QuotePricingSettingsForm(StyledModelForm):
    class Meta:
        model = QuotePricingSettings
        fields = ["target_margin_percent", "minimum_margin_percent", "maximum_discount_percent"]
        widgets = {
            "target_margin_percent": forms.NumberInput(attrs={"step": "0.01", "min": "0", "max": "99.99"}),
            "minimum_margin_percent": forms.NumberInput(attrs={"step": "0.01", "min": "0", "max": "99.99"}),
            "maximum_discount_percent": forms.NumberInput(attrs={"step": "0.01", "min": "0", "max": "99.99"}),
        }


class ProductCSVImportForm(forms.Form):
    """Validate an all-or-nothing, owner-scoped product catalogue CSV."""

    EXPECTED_HEADERS = ("name", "grade", "shape", "dimensions", "unit", "weight_basis", "weight_kg", "notes")
    MAX_FILE_BYTES = 1_000_000
    MAX_ROWS = 500

    file = forms.FileField(label="CSV file", help_text="UTF-8 CSV, up to 500 products and 1 MB.")

    def __init__(self, *args, owner, **kwargs):
        super().__init__(*args, **kwargs)
        self.owner = owner
        self.products = []
        self.fields["file"].widget.attrs["class"] = "field"

    def clean_file(self):
        uploaded = self.cleaned_data["file"]
        if uploaded.size > self.MAX_FILE_BYTES:
            raise ValidationError("The CSV file must be 1 MB or smaller.")
        try:
            content = uploaded.read().decode("utf-8-sig")
            reader = csv.DictReader(io.StringIO(content, newline=""))
            headers = reader.fieldnames
            if not headers or len(headers) != len(set(headers)) or set(headers) != set(self.EXPECTED_HEADERS):
                raise ValidationError(
                    "Use exactly these headers: " + ", ".join(self.EXPECTED_HEADERS) + "."
                )
            products = []
            seen_names = set()
            existing_names = set(Product.objects.filter(owner=self.owner).values_list("name", flat=True))
            errors = []
            row_count = 0
            for row_number, values in enumerate(reader, start=2):
                if None in values:
                    errors.append(f"Row {row_number}: the row has more values than the header.")
                    continue
                if all(not (value or "").strip() for value in values.values()):
                    continue
                row_count += 1
                if row_count > self.MAX_ROWS:
                    raise ValidationError("The CSV can contain at most 500 product rows.")
                row = {key: (values.get(key) or "").strip() for key in self.EXPECTED_HEADERS}
                product = Product(
                    owner=self.owner,
                    name=row["name"],
                    grade=row["grade"],
                    shape=row["shape"],
                    dimensions=row["dimensions"],
                    unit=row["unit"],
                    weight_basis=row["weight_basis"] or Product.WeightBasis.NOT_APPLICABLE,
                    weight_kg=row["weight_kg"] or None,
                    notes=row["notes"],
                )
                try:
                    product.full_clean()
                except ValidationError as error:
                    errors.append(f"Row {row_number}: {'; '.join(error.messages)}")
                    continue
                if product.name in existing_names or product.name in seen_names:
                    errors.append(f"Row {row_number}: a product named {product.name!r} already exists in this account or file.")
                    continue
                seen_names.add(product.name)
                products.append(product)
            if not row_count:
                errors.append("The CSV must contain at least one product row.")
            if errors:
                raise ValidationError(errors[:20])
            self.products = products
        except UnicodeDecodeError as error:
            raise ValidationError("Upload a UTF-8 CSV file.") from error
        except csv.Error as error:
            raise ValidationError("The CSV file could not be read.") from error
        return uploaded


class QuoteOfferChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, offer):
        return (
            f"{offer.supplier} — INR {offer.landed_cost_per_requested_unit:.4f} per "
            f"{offer.rfq_line.get_unit_display()} ({offer.delivery_days} days)"
        )


class QuoteCreateForm(forms.Form):
    """Select one full-coverage supplier offer and discount for every enquiry line."""

    issue_date = forms.DateField(
        required=False, label="Issue date", widget=forms.DateInput(attrs={"type": "date"}),
    )
    valid_until = forms.DateField(
        required=False, label="Valid until", widget=forms.DateInput(attrs={"type": "date"}),
    )
    tax_rate_percent = forms.DecimalField(
        required=False, min_value=Decimal("0.00"), max_value=Decimal("100.00"),
        max_digits=5, decimal_places=2, initial=Decimal("0.00"), label="GST / tax rate (%)",
    )
    payment_terms = forms.CharField(required=False, label="Payment terms", widget=forms.Textarea(attrs={"rows": 2}))
    delivery_terms = forms.CharField(required=False, label="Delivery terms", widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, owner, lines, pricing_settings, **kwargs):
        super().__init__(*args, **kwargs)
        self.owner = owner
        self.lines = list(lines)
        self.pricing_settings = pricing_settings
        self.pricing_rows = []
        self.line_fields = {}
        for name in ("issue_date", "valid_until", "tax_rate_percent", "payment_terms", "delivery_terms"):
            self.fields[name].widget.attrs["class"] = "field"
        for line in self.lines:
            available_offers = [
                offer for offer in SupplierOffer.objects.filter(
                    owner=owner, supplier__owner=owner, rfq_line=line,
                ).select_related("supplier", "rfq_line")
                if offer.covers_full_quantity and offer.landed_cost_per_requested_unit is not None
            ]
            offer_field = QuoteOfferChoiceField(
                queryset=SupplierOffer.objects.filter(
                    owner=owner, supplier__owner=owner, rfq_line=line,
                    pk__in=[offer.pk for offer in available_offers],
                ),
                empty_label="Choose a supplier offer",
                label=f"Supplier offer for {line.product or line.description or 'requested item'}",
                help_text="Only offers that cover the full requested quantity are available.",
            )
            discount_field = forms.DecimalField(
                min_value=Decimal("0.00"),
                max_value=pricing_settings.maximum_discount_percent,
                max_digits=5,
                decimal_places=2,
                initial=Decimal("0.00"),
                label="Discount from target price (%)",
                help_text=f"Maximum allowed: {pricing_settings.maximum_discount_percent}%.",
            )
            for field in (offer_field, discount_field):
                field.widget.attrs["class"] = "field"
            offer_name = f"offer_{line.pk}"
            discount_name = f"discount_{line.pk}"
            self.fields[offer_name] = offer_field
            self.fields[discount_name] = discount_field
            self.line_fields[line.pk] = (offer_name, discount_name)

    def clean(self):
        cleaned = super().clean()
        issue_date = cleaned.get("issue_date") or timezone.localdate()
        valid_until = cleaned.get("valid_until") or issue_date + timedelta(days=7)
        cleaned["issue_date"] = issue_date
        cleaned["valid_until"] = valid_until
        cleaned["tax_rate_percent"] = cleaned.get("tax_rate_percent") or Decimal("0.00")
        cleaned["payment_terms"] = cleaned.get("payment_terms") or ""
        cleaned["delivery_terms"] = cleaned.get("delivery_terms") or ""
        if valid_until < issue_date:
            self.add_error("valid_until", "The expiry date cannot be before the issue date.")
        target = self.pricing_settings.target_margin_percent
        divisor = Decimal("1") - target / Decimal("100")
        rows = []
        for line in self.lines:
            offer_name, discount_name = self.line_fields[line.pk]
            offer = cleaned.get(offer_name)
            discount = cleaned.get(discount_name)
            if offer is None or discount is None:
                continue
            cost = offer.landed_cost_per_requested_unit
            if cost is None or cost <= 0 or divisor <= 0:
                self.add_error(offer_name, "This offer cannot produce a valid positive selling price.")
                continue
            # Gross margin is based on the selling price, so solve cost / (1 - margin), not cost * (1 + margin).
            target_price = cost / divisor
            price = (target_price * (Decimal("1") - discount / Decimal("100"))).quantize(
                Decimal("0.0001"), rounding=ROUND_HALF_UP,
            )
            if price <= 0 or price > Decimal("9999999999.9999"):
                self.add_error(discount_name, "This discount or target margin is outside the supported price range.")
                continue
            selling_total = (line.quantity * price).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if selling_total <= 0:
                self.add_error(discount_name, "The selling total must round to at least INR 0.01.")
                continue
            margin = ((price - cost) / price * Decimal("100")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP,
            )
            rows.append({
                "rfq_line": line,
                "supplier_offer": offer,
                "discount_percent": discount,
                "landed_cost_per_unit": cost,
                "selling_price_per_unit": price,
                "gross_margin_percent": margin,
                "needs_review": margin < self.pricing_settings.minimum_margin_percent,
            })
        if not self.errors:
            self.pricing_rows = rows
        return cleaned


RFQLineFormSet = inlineformset_factory(
    RFQ, RFQLine, form=RFQLineForm, extra=1, can_delete=True, min_num=1, validate_min=True,
)
