from django import forms
from django.forms import inlineformset_factory

from .models import Customer, Product, RFQ, RFQLine, Supplier


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


RFQLineFormSet = inlineformset_factory(
    RFQ, RFQLine, form=RFQLineForm, extra=1, can_delete=True, min_num=1, validate_min=True,
)
