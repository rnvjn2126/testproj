from django import forms
from django.forms import inlineformset_factory
from decimal import Decimal, ROUND_HALF_UP

from .models import (
    Customer, Product, QuotePricingSettings, RFQ, RFQLine, Supplier, SupplierOffer,
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


class QuoteOfferChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, offer):
        return (
            f"{offer.supplier} — INR {offer.landed_cost_per_requested_unit:.4f} per "
            f"{offer.rfq_line.get_unit_display()} ({offer.delivery_days} days)"
        )


class QuoteCreateForm(forms.Form):
    """Select one full-coverage supplier offer and discount for every enquiry line."""

    def __init__(self, *args, owner, lines, pricing_settings, **kwargs):
        super().__init__(*args, **kwargs)
        self.owner = owner
        self.lines = list(lines)
        self.pricing_settings = pricing_settings
        self.pricing_rows = []
        self.line_fields = {}
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

