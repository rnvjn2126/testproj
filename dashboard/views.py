from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse
from django.views.generic import CreateView, DeleteView, ListView, UpdateView
from django.shortcuts import get_object_or_404, redirect, render
from django.db import transaction
from django.db.models import Prefetch, Q
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from .forms import (
    CustomerForm, ProductForm, QuoteCreateForm, QuotePricingSettingsForm,
    RFQForm, RFQLineFormSet, SupplierForm, SupplierOfferForm,
)
from .models import (
    Customer, Product, Quote, QuoteLine, QuotePricingSettings, RFQ, RFQLine,
    Supplier, SupplierOffer,
)


@login_required
def home(request):
    return render(request, "dashboard/home.html", {
        "customer_count": Customer.objects.filter(owner=request.user).count(),
        "supplier_count": Supplier.objects.filter(owner=request.user).count(),
        "product_count": Product.objects.filter(owner=request.user).count(),
        "rfq_count": RFQ.objects.filter(owner=request.user).count(),
    })


@login_required
def rfq_list(request):
    return render(request, "dashboard/rfq_list.html", {"rfqs": RFQ.objects.filter(owner=request.user).select_related("customer")})


@login_required
@require_http_methods(["GET", "POST"])
def rfq_create(request):
    from .models import RFQLine
    rfq = RFQ(owner=request.user)
    form = RFQForm(request.POST or None, owner=request.user)
    formset = RFQLineFormSet(request.POST or None, instance=rfq, form_kwargs={"owner": request.user}, prefix="lines")
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        with transaction.atomic():
            rfq = form.save(commit=False)
            rfq.owner = request.user
            rfq.full_clean()
            rfq.save()
            formset.instance = rfq
            lines = formset.save(commit=False)
            for line in lines:
                line.owner = request.user
                line.rfq = rfq
                line.full_clean()
                line.save()
            for line in formset.deleted_objects:
                line.delete()
        return redirect("dashboard:rfq_detail", pk=rfq.pk)
    return render(request, "dashboard/rfq_form.html", {"form": form, "formset": formset})


@login_required
def rfq_detail(request, pk):
    offers = SupplierOffer.objects.filter(
        owner=request.user, supplier__owner=request.user, rfq_line__owner=request.user,
    ).select_related("supplier", "rfq_line__product")
    lines = RFQLine.objects.filter(owner=request.user).select_related("product").prefetch_related(
        Prefetch("supplier_offers", queryset=offers)
    )
    rfq = get_object_or_404(
        RFQ.objects.filter(owner=request.user).select_related("customer").prefetch_related(
            Prefetch("lines", queryset=lines)
        ),
        pk=pk,
    )
    for line in rfq.lines.all():
        line.comparison_offers = sorted(
            line.supplier_offers.all(),
            key=lambda offer: (
                offer.landed_cost_per_requested_unit is None,
                offer.landed_cost_per_requested_unit or 0,
                offer.pk,
            ),
        )
    return render(request, "dashboard/rfq_detail.html", {"rfq": rfq})


@login_required
@require_http_methods(["GET", "POST"])
def supplier_offer_create(request, pk, line_pk):
    rfq = get_object_or_404(RFQ.objects.filter(owner=request.user), pk=pk)
    line = get_object_or_404(
        RFQLine.objects.filter(owner=request.user, rfq=rfq).select_related("product"),
        pk=line_pk,
    )
    form = SupplierOfferForm(
        request.POST or None, owner=request.user, rfq_line=line,
    )
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            offer = form.save(commit=False)
            offer.owner = request.user
            offer.rfq_line = line
            offer.full_clean()
            offer.save()
        return redirect("dashboard:rfq_detail", pk=rfq.pk)
    return render(request, "dashboard/supplier_offer_form.html", {"form": form, "rfq": rfq, "line": line})


@login_required
@require_http_methods(["GET", "POST"])
def quote_pricing_settings(request):
    settings, _ = QuotePricingSettings.objects.get_or_create(owner=request.user)
    form = QuotePricingSettingsForm(request.POST or None, instance=settings)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("dashboard:quote_pricing_settings")
    return render(request, "dashboard/quote_pricing_settings.html", {"form": form})


@login_required
@require_http_methods(["GET", "POST"])
def quote_create(request, pk):
    rfq = get_object_or_404(
        RFQ.objects.filter(owner=request.user, customer__owner=request.user).select_related("customer"), pk=pk,
    )
    all_lines = RFQLine.objects.filter(owner=request.user, rfq=rfq)
    lines = list(all_lines.filter(
        Q(product__isnull=True) | Q(product__owner=request.user),
    ).select_related("product"))
    has_foreign_product_line = len(lines) != all_lines.count()
    pricing_settings, _ = QuotePricingSettings.objects.get_or_create(owner=request.user)
    form = QuoteCreateForm(
        request.POST or None, owner=request.user, lines=lines,
        pricing_settings=pricing_settings,
    )
    line_rows = []
    for line in lines:
        offer_name, discount_name = form.line_fields[line.pk]
        has_offer = form.fields[offer_name].queryset.exists()
        line_rows.append({
            "line": line,
            "offer_field": form[offer_name],
            "discount_field": form[discount_name],
            "has_offer": has_offer,
        })
    can_create = bool(lines) and not has_foreign_product_line and all(row["has_offer"] for row in line_rows)
    if request.method == "POST" and can_create and form.is_valid():
        with transaction.atomic():
            quote = Quote(
                owner=request.user,
                rfq=rfq,
                target_margin_percent=pricing_settings.target_margin_percent,
                minimum_margin_percent=pricing_settings.minimum_margin_percent,
                maximum_discount_percent=pricing_settings.maximum_discount_percent,
                status=(
                    Quote.Status.NEEDS_REVIEW
                    if any(row["needs_review"] for row in form.pricing_rows)
                    else Quote.Status.READY
                ),
            )
            quote.full_clean()
            quote.save()
            for row in form.pricing_rows:
                quote_line = QuoteLine(
                    owner=request.user,
                    quote=quote,
                    rfq_line=row["rfq_line"],
                    supplier_offer=row["supplier_offer"],
                    quantity=row["rfq_line"].quantity,
                    unit=row["rfq_line"].unit,
                    landed_cost_per_unit=row["landed_cost_per_unit"],
                    discount_percent=row["discount_percent"],
                    selling_price_per_unit=row["selling_price_per_unit"],
                )
                quote_line.full_clean()
                quote_line.save()
        return redirect("dashboard:quote_detail", pk=quote.pk)
    return render(request, "dashboard/quote_create.html", {
        "rfq": rfq,
        "form": form,
        "lines": lines,
        "line_rows": line_rows,
        "can_create": can_create,
        "has_foreign_product_line": has_foreign_product_line,
        "pricing_settings": pricing_settings,
    })


@login_required
def quote_detail(request, pk):
    visible_lines = QuoteLine.objects.filter(
        owner=request.user,
        rfq_line__owner=request.user,
        rfq_line__rfq__owner=request.user,
        supplier_offer__owner=request.user,
        supplier_offer__supplier__owner=request.user,
    ).filter(
        Q(rfq_line__product__isnull=True) | Q(rfq_line__product__owner=request.user),
    ).select_related(
        "rfq_line", "rfq_line__product", "supplier_offer", "supplier_offer__supplier",
    )
    quote = get_object_or_404(
        Quote.objects.filter(
            owner=request.user, rfq__owner=request.user, rfq__customer__owner=request.user,
        )
        .select_related("rfq", "rfq__customer", "approved_by")
        .prefetch_related(Prefetch("lines", queryset=visible_lines)),
        pk=pk,
    )
    return render(request, "dashboard/quote_detail.html", {"quote": quote})


@login_required
@require_POST
def quote_approve(request, pk):
    quote = get_object_or_404(
        Quote.objects.filter(owner=request.user, status=Quote.Status.NEEDS_REVIEW), pk=pk,
    )
    if not request.user.is_staff:
        raise PermissionDenied("Only staff can approve quotations that require manager review.")
    quote.status = Quote.Status.APPROVED
    quote.approved_by = request.user
    quote.approved_at = timezone.now()
    quote.full_clean()
    quote.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
    return redirect("dashboard:quote_detail", pk=quote.pk)


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

