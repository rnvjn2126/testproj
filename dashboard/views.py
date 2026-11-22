from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse
from django.views.generic import CreateView, DeleteView, ListView, UpdateView
from django.shortcuts import render

from .forms import CustomerForm, ProductForm, SupplierForm
from .models import Customer, Product, Supplier


@login_required
def home(request):
    return render(request, "dashboard/home.html", {
        "customer_count": Customer.objects.filter(owner=request.user).count(),
        "supplier_count": Supplier.objects.filter(owner=request.user).count(),
        "product_count": Product.objects.filter(owner=request.user).count(),
    })


class OwnedListView(LoginRequiredMixin, ListView):
    template_name = "dashboard/catalogue_list.html"
    context_object_name = "records"
    title = "Catalogue"
    singular = "record"

    def get_queryset(self):
        return self.model.objects.filter(owner=self.request.user)

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        data.update(title=self.title, singular=self.singular, create_url=f"dashboard:{self.singular}_create")
        return data


class OwnedCreateView(LoginRequiredMixin, CreateView):
    template_name = "dashboard/catalogue_form.html"
    success_message = "Saved"
    title = "Add record"
    singular = "record"

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse(f"dashboard:{self.singular}_list")

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        data.update(title=self.title, singular=self.singular)
        return data


class OwnedUpdateView(LoginRequiredMixin, UpdateView):
    def get_queryset(self):
        return self.model.objects.filter(owner=self.request.user)

    def get_success_url(self):
        return reverse(f"dashboard:{self.singular}_list")

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        data.update(title=self.title, singular=self.singular)
        return data


class OwnedDeleteView(LoginRequiredMixin, DeleteView):
    template_name = "dashboard/catalogue_confirm_delete.html"

    def get_queryset(self):
        return self.model.objects.filter(owner=self.request.user)

    def get_success_url(self):
        return reverse(f"dashboard:{self.singular}_list")

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        data.update(title=f"Delete {self.singular}", singular=self.singular)
        return data


class CustomerListView(OwnedListView):
    model, title, singular = Customer, "Customers", "customer"


class CustomerCreateView(OwnedCreateView):
    model, form_class, title, singular = Customer, CustomerForm, "Add customer", "customer"


class CustomerUpdateView(OwnedUpdateView):
    model, form_class, title, singular = Customer, CustomerForm, "Edit customer", "customer"


class CustomerDeleteView(OwnedDeleteView):
    model, singular = Customer, "customer"


class SupplierListView(OwnedListView):
    model, title, singular = Supplier, "Suppliers", "supplier"


class SupplierCreateView(OwnedCreateView):
    model, form_class, title, singular = Supplier, SupplierForm, "Add supplier", "supplier"


class SupplierUpdateView(OwnedUpdateView):
    model, form_class, title, singular = Supplier, SupplierForm, "Edit supplier", "supplier"


class SupplierDeleteView(OwnedDeleteView):
    model, singular = Supplier, "supplier"


class ProductListView(OwnedListView):
    model, title, singular = Product, "Products", "product"


class ProductCreateView(OwnedCreateView):
    model, form_class, title, singular = Product, ProductForm, "Add product", "product"


class ProductUpdateView(OwnedUpdateView):
    model, form_class, title, singular = Product, ProductForm, "Edit product", "product"


class ProductDeleteView(OwnedDeleteView):
    model, singular = Product, "product"
