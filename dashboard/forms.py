from django import forms
from django.forms import inlineformset_factory

from .models import Customer, Product, RFQ, RFQLine, Supplier, SupplierOffer


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


RFQLineFormSet = inlineformset_factory(
    RFQ, RFQLine, form=RFQLineForm, extra=1, can_delete=True, min_num=1, validate_min=True,
)
