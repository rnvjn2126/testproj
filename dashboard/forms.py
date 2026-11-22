from django import forms

from .models import Customer, Product, Supplier


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
