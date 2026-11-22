import csv
from datetime import timedelta
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, HttpResponseBadRequest
from django.urls import reverse
from django.views.generic import CreateView, DeleteView, ListView, UpdateView
from django.shortcuts import get_object_or_404, redirect, render
from django.db import transaction
from django.db.models import Prefetch, Q
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from .forms import (
    CustomerForm, FollowUpForm, ProductCSVImportForm, ProductForm, QuoteCreateForm,
    QuotePricingSettingsForm, QuoteStatusForm, RFQForm, RFQLineFormSet, RFQStatusForm,
    SupplierForm, SupplierOfferForm,
)
from .models import (
    Customer, FollowUp, Product, Quote, QuoteLine, QuotePricingSettings, RFQ,
    RFQLine, Supplier, SupplierOffer,
)


@login_required
def home(request):
    active_follow_ups = FollowUp.objects.filter(
        owner=request.user, rfq__owner=request.user, rfq__customer__owner=request.user,
        completed_at__isnull=True,
    ).select_related("rfq", "rfq__customer").order_by("due_on", "id")
    return render(request, "dashboard/home.html", {
        "customer_count": Customer.objects.filter(owner=request.user).count(),
        "supplier_count": Supplier.objects.filter(owner=request.user).count(),
        "product_count": Product.objects.filter(owner=request.user).count(),
        "rfq_count": RFQ.objects.filter(owner=request.user, customer__owner=request.user).count(),
        "follow_up_count": active_follow_ups.count(),
        "overdue_follow_up_count": active_follow_ups.filter(due_on__lt=timezone.localdate()).count(),
        "upcoming_follow_ups": active_follow_ups[:5],
        "today": timezone.localdate(),
    })


@login_required
def rfq_list(request):
    rfqs = RFQ.objects.filter(owner=request.user, customer__owner=request.user).select_related("customer")
    return render(request, "dashboard/rfq_list.html", {"rfqs": rfqs})


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
    follow_ups = FollowUp.objects.filter(
        owner=request.user, rfq__owner=request.user, rfq__customer__owner=request.user,
    ).order_by("due_on", "id")
    rfq = get_object_or_404(
        RFQ.objects.filter(owner=request.user, customer__owner=request.user).select_related("customer").prefetch_related(
            Prefetch("lines", queryset=lines), Prefetch("follow_ups", queryset=follow_ups),
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
    return render(request, "dashboard/rfq_detail.html", {
        "rfq": rfq, "status_form": RFQStatusForm(initial={"status": rfq.status}),
        "today": timezone.localdate(),
    })


@login_required
@require_POST
def rfq_update_status(request, pk):
    rfq = get_object_or_404(
        RFQ.objects.filter(owner=request.user, customer__owner=request.user), pk=pk,
    )
    form = RFQStatusForm(request.POST)
    if form.is_valid():
        rfq.status = form.cleaned_data["status"]
        rfq.full_clean()
        rfq.save(update_fields=["status", "updated_at"])
    return redirect("dashboard:rfq_detail", pk=rfq.pk)


@login_required
@require_http_methods(["GET", "POST"])
def followup_create(request, pk):
    rfq = get_object_or_404(
        RFQ.objects.filter(owner=request.user, customer__owner=request.user).select_related("customer"),
        pk=pk,
    )
    form = FollowUpForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        follow_up = form.save(commit=False)
        follow_up.owner = request.user
        follow_up.rfq = rfq
        follow_up.full_clean()
        follow_up.save()
        return redirect("dashboard:rfq_detail", pk=rfq.pk)
    return render(request, "dashboard/followup_form.html", {"form": form, "rfq": rfq})


@login_required
@require_POST
def followup_complete(request, pk):
    follow_up = get_object_or_404(
        FollowUp.objects.filter(
            owner=request.user, rfq__owner=request.user, rfq__customer__owner=request.user,
            completed_at__isnull=True,
        ).select_related("rfq"),
        pk=pk,
    )
    follow_up.completed_at = timezone.now()
    follow_up.full_clean()
    follow_up.save(update_fields=["completed_at", "updated_at"])
    return redirect("dashboard:rfq_detail", pk=follow_up.rfq_id)


@login_required
def followup_list(request):
    follow_ups = FollowUp.objects.filter(
        owner=request.user, rfq__owner=request.user, rfq__customer__owner=request.user,
        completed_at__isnull=True,
    ).select_related("rfq", "rfq__customer").order_by("due_on", "id")
    return render(request, "dashboard/followup_list.html", {
        "follow_ups": follow_ups, "today": timezone.localdate(),
    })


@login_required
def product_csv_export(request):
    """Export only the signed-in user's non-sensitive product catalogue fields."""
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="steel-products.csv"'
    response.write("\ufeff")
    writer = csv.writer(response)
    writer.writerow(ProductCSVImportForm.EXPECTED_HEADERS)
    products = Product.objects.filter(owner=request.user).order_by("name", "id")

    def safe_cell(value):
        text = "" if value is None else str(value)
        # Spreadsheet programs can execute formula-like cell values when a CSV is opened.
        if text.lstrip(" \t\r\n").startswith(("=", "+", "-", "@")):
            return "'" + text
        return text

    for product in products:
        writer.writerow(safe_cell(value) for value in (
            product.name, product.grade, product.shape, product.dimensions,
            product.unit, product.weight_basis, product.weight_kg, product.notes,
        ))
    return response


@login_required
@require_http_methods(["GET", "POST"])
def product_csv_import(request):
    form = ProductCSVImportForm(request.POST or None, request.FILES or None, owner=request.user)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            for product in form.products:
                product.save()
        return redirect("dashboard:product_list")
    return render(request, "dashboard/product_csv_import.html", {"form": form})


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
    return _quote_create_page(request, rfq)


@login_required
@require_http_methods(["GET", "POST"])
def quote_revision_create(request, pk):
    source_quote = get_object_or_404(
        Quote.objects.filter(owner=request.user, rfq__owner=request.user, rfq__customer__owner=request.user)
        .select_related("rfq", "rfq__customer"),
        pk=pk,
    )
    return _quote_create_page(request, source_quote.rfq, source_quote=source_quote)


def _quote_create_page(request, rfq, source_quote=None):
    all_lines = RFQLine.objects.filter(owner=request.user, rfq=rfq)
    lines = list(all_lines.filter(
        Q(product__isnull=True) | Q(product__owner=request.user),
    ).select_related("product"))
    has_foreign_product_line = len(lines) != all_lines.count()
    if source_quote:
        pricing_settings = source_quote
        initial = {
            "issue_date": timezone.localdate(),
            "valid_until": timezone.localdate() + timedelta(days=7),
            "tax_rate_percent": source_quote.tax_rate_percent,
            "payment_terms": source_quote.payment_terms,
            "delivery_terms": source_quote.delivery_terms,
        }
    else:
        pricing_settings, _ = QuotePricingSettings.objects.get_or_create(owner=request.user)
        today = timezone.localdate()
        initial = {
            "issue_date": today,
            "valid_until": today + timedelta(days=7),
            "tax_rate_percent": 0,
        }
    prior_lines = {
        line.rfq_line_id: line for line in source_quote.lines.select_related("supplier_offer")
    } if source_quote else {}
    for line in lines:
        prior = prior_lines.get(line.pk)
        if prior:
            initial[f"offer_{line.pk}"] = prior.supplier_offer_id
            initial[f"discount_{line.pk}"] = prior.discount_percent
    form = QuoteCreateForm(
        request.POST or None, owner=request.user, lines=lines,
        pricing_settings=pricing_settings, initial=initial,
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
                revision_of=source_quote,
                number=source_quote.number if source_quote else "",
                revision=source_quote.revision + 1 if source_quote else 1,
                issue_date=form.cleaned_data["issue_date"],
                valid_until=form.cleaned_data["valid_until"],
                tax_rate_percent=form.cleaned_data["tax_rate_percent"],
                payment_terms=form.cleaned_data["payment_terms"],
                delivery_terms=form.cleaned_data["delivery_terms"],
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
            if not quote.number:
                quote.number = f"QT-{quote.issue_date.year}-{quote.pk:06d}"
                quote.save(update_fields=["number", "updated_at"])
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
        "source_quote": source_quote,
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
    quote.revision_history = Quote.objects.filter(owner=request.user, number=quote.number).order_by("revision")
    status_form = QuoteStatusForm(quote=quote)
    return render(request, "dashboard/quote_detail.html", {
        "quote": quote, "status_form": status_form,
        "can_update_status": bool(status_form.fields["status"].choices),
    })


@login_required
def quote_list(request):
    quotes = Quote.objects.filter(
        owner=request.user, rfq__owner=request.user, rfq__customer__owner=request.user,
    ).select_related("rfq", "rfq__customer").order_by("-created_at", "-id")
    return render(request, "dashboard/quote_list.html", {"quotes": quotes, "today": timezone.localdate()})


@login_required
@require_POST
def quote_update_status(request, pk):
    quote = get_object_or_404(
        Quote.objects.filter(owner=request.user, rfq__owner=request.user, rfq__customer__owner=request.user),
        pk=pk,
    )
    form = QuoteStatusForm(request.POST, quote=quote)
    if not form.is_valid():
        return HttpResponseBadRequest("Choose a valid quotation status.")
    target = form.cleaned_data["status"]
    # Keep the pipeline manual: each user action must match one of these transitions.
    transitions = {
        Quote.Status.READY: {Quote.Status.SENT},
        Quote.Status.APPROVED: {Quote.Status.SENT},
        Quote.Status.SENT: {Quote.Status.ACCEPTED, Quote.Status.LOST, Quote.Status.EXPIRED},
    }
    if target not in transitions.get(quote.status, set()):
        return HttpResponseBadRequest("That quotation status transition is not allowed.")
    now = timezone.now()
    today = timezone.localdate()
    if target == Quote.Status.SENT:
        if quote.valid_until < today:
            return HttpResponseBadRequest("An expired quotation cannot be marked as sent.")
        quote.sent_at = now
    elif target == Quote.Status.EXPIRED:
        if quote.valid_until >= today:
            return HttpResponseBadRequest("A quotation can be marked expired after its validity date.")
        quote.closed_at = now
    else:
        quote.closed_at = now
    quote.status = target
    quote.full_clean()
    quote.save(update_fields=["status", "sent_at", "closed_at", "updated_at"])
    return redirect("dashboard:quote_detail", pk=quote.pk)


@login_required
@require_http_methods(["GET"])
def quote_pdf(request, pk):
    visible_lines = QuoteLine.objects.filter(
        owner=request.user,
        rfq_line__owner=request.user,
        rfq_line__rfq__owner=request.user,
        supplier_offer__owner=request.user,
        supplier_offer__supplier__owner=request.user,
    ).filter(
        Q(rfq_line__product__isnull=True) | Q(rfq_line__product__owner=request.user),
    ).select_related("rfq_line", "rfq_line__product")
    quote = get_object_or_404(
        Quote.objects.filter(owner=request.user, rfq__owner=request.user, rfq__customer__owner=request.user)
        .select_related("rfq__customer")
        .prefetch_related(Prefetch("lines", queryset=visible_lines)),
        pk=pk,
    )
    visible = list(quote.lines.all())
    if len(visible) != QuoteLine.objects.filter(quote=quote).count():
        raise PermissionDenied("The quotation contains records outside this account boundary.")
    if not visible:
        return HttpResponseBadRequest("A quotation must contain at least one item.")
    if quote.needs_review or (
        quote.status != Quote.Status.APPROVED and any(line.needs_review for line in visible)
    ):
        raise PermissionDenied("A quotation awaiting manager review cannot be issued to a customer.")
    from .documents import build_quote_pdf
    response = HttpResponse(build_quote_pdf(quote), content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{quote.number}-R{quote.revision}.pdf"'
    return response


@login_required
@require_POST
def quote_approve(request, pk):
    quote = get_object_or_404(
        Quote.objects.filter(
            owner=request.user,
            rfq__owner=request.user,
            rfq__customer__owner=request.user,
            status=Quote.Status.NEEDS_REVIEW,
        ),
        pk=pk,
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

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        data.update(
            import_url="dashboard:product_csv_import",
            export_url="dashboard:product_csv_export",
        )
        return data


class ProductCreateView(OwnedCreateView):
    model, form_class, title, singular = Product, ProductForm, "Add product", "product"


class ProductUpdateView(OwnedUpdateView):
    model, form_class, title, singular = Product, ProductForm, "Edit product", "product"


class ProductDeleteView(OwnedDeleteView):
    model, singular = Product, "product"
