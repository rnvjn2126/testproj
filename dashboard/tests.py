"""Integration and domain tests for the local steel quotation MVP.

All customers, suppliers, rates, and phone details in these tests are synthetic.
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .forms import QuoteCreateForm
from .models import (
    Customer,
    FollowUp,
    Product,
    Quote,
    QuoteLine,
    QuotePricingSettings,
    RFQ,
    RFQLine,
    Supplier,
    SupplierOffer,
)


class SteelWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        users = get_user_model()
        cls.owner = users.objects.create_user(
            username="trader1", password="TestPass!12345",
        )
        cls.other_user = users.objects.create_user(
            username="trader2", password="TestPass!12345",
        )
        cls.customer = Customer.objects.create(
            owner=cls.owner, name="Demo Buyer", company_name="Sample Industries",
        )
        cls.other_customer = Customer.objects.create(
            owner=cls.other_user, name="Other Buyer",
        )
        cls.supplier = Supplier.objects.create(
            owner=cls.owner, name="Demo Steel Supply",
        )
        cls.other_supplier = Supplier.objects.create(
            owner=cls.other_user, name="Other Supplier",
        )
        cls.product = Product.objects.create(
            owner=cls.owner,
            name="SS 304 Round Bar",
            grade="SS 304",
            shape=Product.Shape.ROUND_BAR,
            unit=Product.Unit.KG,
        )
        cls.other_product = Product.objects.create(
            owner=cls.other_user, name="Private Product",
            shape=Product.Shape.SHEET, unit=Product.Unit.KG,
        )
        today = timezone.localdate()
        cls.rfq = RFQ.objects.create(
            owner=cls.owner, customer=cls.customer,
            reference="RFQ-DEMO-1", received_on=today,
        )
        cls.other_rfq = RFQ.objects.create(
            owner=cls.other_user, customer=cls.other_customer,
            reference="RFQ-PRIVATE", received_on=today,
        )
        cls.line = RFQLine.objects.create(
            owner=cls.owner, rfq=cls.rfq, product=cls.product,
            quantity=Decimal("1000.000"), unit=Product.Unit.KG,
        )
        cls.offer = SupplierOffer.objects.create(
            owner=cls.owner, rfq_line=cls.line, supplier=cls.supplier,
            available_quantity=Decimal("1.000"), unit=Product.Unit.TONNE,
            unit_price=Decimal("188000.0000"),
            freight_cost=Decimal("3000.00"),
            packaging_cost=Decimal("2000.00"), delivery_days=7,
        )
        cls.quote = Quote.objects.create(
            owner=cls.owner, rfq=cls.rfq, number="QT-DEMO-001",
            revision=1, issue_date=today, valid_until=today + timedelta(days=7),
            target_margin_percent=Decimal("12.00"),
            minimum_margin_percent=Decimal("8.00"),
            maximum_discount_percent=Decimal("5.00"),
            tax_rate_percent=Decimal("18.00"),
            status=Quote.Status.READY,
        )
        cls.quote_line = QuoteLine.objects.create(
            owner=cls.owner, quote=cls.quote,
            rfq_line=cls.line, supplier_offer=cls.offer,
            quantity=Decimal("1000.000"), unit=Product.Unit.KG,
            landed_cost_per_unit=Decimal("193.0000"),
            selling_price_per_unit=Decimal("225.0000"),
            discount_percent=Decimal("0.00"),
        )

    def login_owner(self):
        self.client.force_login(self.owner)

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(reverse("dashboard:rfq_list"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)

    def test_customer_list_does_not_disclose_other_account(self):
        self.login_owner()
        response = self.client.get(reverse("dashboard:customer_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Demo Buyer")
        self.assertNotContains(response, "Other Buyer")

    def test_other_account_customer_cannot_be_edited(self):
        self.login_owner()
        response = self.client.get(
            reverse("dashboard:customer_update", args=[self.other_customer.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_other_account_rfq_cannot_be_opened(self):
        self.login_owner()
        response = self.client.get(
            reverse("dashboard:rfq_detail", args=[self.other_rfq.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_supplier_and_product_lists_are_scoped(self):
        self.login_owner()
        suppliers = self.client.get(reverse("dashboard:supplier_list"))
        products = self.client.get(reverse("dashboard:product_list"))
        self.assertEqual(suppliers.status_code, 200)
        self.assertEqual(products.status_code, 200)
        self.assertContains(suppliers, "Demo Steel Supply")
        self.assertNotContains(suppliers, "Other Supplier")
        self.assertContains(products, "SS 304 Round Bar")
        self.assertNotContains(products, "Private Product")

    def test_enquiry_rejects_foreign_customer(self):
        self.rfq.customer = self.other_customer
        with self.assertRaises(ValidationError):
            self.rfq.full_clean()

    def test_enquiry_line_rejects_foreign_product(self):
        self.line.product = self.other_product
        with self.assertRaises(ValidationError):
            self.line.full_clean()

    def test_offer_rejects_foreign_supplier(self):
        self.offer.supplier = self.other_supplier
        with self.assertRaises(ValidationError):
            self.offer.full_clean()

    def test_tonne_to_kg_conversion_is_exact(self):
        self.assertEqual(self.offer.unit_conversion_factor, Decimal("1000"))
        self.assertEqual(
            self.offer.converted_available_quantity, Decimal("1000"),
        )
        self.assertTrue(self.offer.covers_full_quantity)
        self.assertEqual(self.offer.normalized_unit_price, Decimal("188"))
        self.assertEqual(
            self.offer.landed_cost_per_requested_unit, Decimal("193"),
        )
        self.assertEqual(self.offer.total_landed_cost, Decimal("193000"))

    def test_partial_offer_cannot_cover_whole_enquiry(self):
        self.offer.available_quantity = Decimal("0.400")
        self.offer.save(update_fields=["available_quantity"])
        self.assertFalse(self.offer.covers_full_quantity)
        settings = QuotePricingSettings(owner=self.owner)
        form = QuoteCreateForm(
            owner=self.owner, lines=[self.line], pricing_settings=settings,
        )
        offer_field, _ = form.line_fields[self.line.pk]
        self.assertNotIn(
            self.offer.pk,
            list(form.fields[offer_field].queryset.values_list("pk", flat=True)),
        )

    def test_unconvertible_metre_offer_rejected(self):
        self.offer.unit = Product.Unit.METRE
        with self.assertRaises(ValidationError):
            self.offer.full_clean()

    def test_quote_money_math_uses_gross_margin_not_markup(self):
        self.assertEqual(self.quote.total_landed_cost, Decimal("193000.00"))
        self.assertEqual(self.quote.total_selling_price, Decimal("225000.00"))
        self.assertEqual(self.quote.gross_margin_percent, Decimal("14.22"))
        self.assertEqual(self.quote.tax_amount, Decimal("40500.00"))
        self.assertEqual(self.quote.grand_total, Decimal("265500.00"))
        self.assertEqual(
            self.quote_line.target_price_per_unit, Decimal("219.3182"),
        )

    def test_discounted_quote_line_needs_review_below_floor(self):
        self.quote.minimum_margin_percent = Decimal("15.00")
        self.assertTrue(self.quote_line.needs_review)

    def test_quote_detail_and_pdf_reject_other_user(self):
        self.client.force_login(self.other_user)
        for name in ("dashboard:quote_detail", "dashboard:quote_pdf"):
            response = self.client.get(reverse(name, args=[self.quote.pk]))
            self.assertEqual(response.status_code, 404)

    def test_quote_pdf_is_available_when_margin_is_safe(self):
        self.login_owner()
        response = self.client.get(
            reverse("dashboard:quote_pdf", args=[self.quote.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF-"))

    def test_quote_pdf_blocks_unapproved_low_margin(self):
        self.login_owner()
        self.quote.status = Quote.Status.NEEDS_REVIEW
        self.quote.save(update_fields=["status"])
        response = self.client.get(
            reverse("dashboard:quote_pdf", args=[self.quote.pk])
        )
        self.assertEqual(response.status_code, 403)

    def test_quote_approval_requires_staff(self):
        self.login_owner()
        self.quote.status = Quote.Status.NEEDS_REVIEW
        self.quote.save(update_fields=["status"])
        response = self.client.post(
            reverse("dashboard:quote_approve", args=[self.quote.pk])
        )
        self.assertEqual(response.status_code, 403)

    def test_csv_export_excludes_other_user_products(self):
        self.login_owner()
        response = self.client.get(reverse("dashboard:product_csv_export"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("SS 304 Round Bar", response.content.decode("utf-8"))
        self.assertNotIn("Private Product", response.content.decode("utf-8"))

    def test_csv_formula_like_product_names_are_escaped(self):
        Product.objects.create(
            owner=self.owner, name="=1+2",
            shape=Product.Shape.SHEET, unit=Product.Unit.KG,
        )
        self.login_owner()
        response = self.client.get(reverse("dashboard:product_csv_export"))
        self.assertIn("'=1+2", response.content.decode("utf-8"))

    def test_followup_is_scoped_to_owner(self):
        followup = FollowUp.objects.create(
            owner=self.owner, rfq=self.rfq,
            due_on=timezone.localdate(), note="Manual callback",
        )
        self.client.force_login(self.other_user)
        response = self.client.post(
            reverse("dashboard:followup_complete", args=[followup.pk])
        )
        self.assertEqual(response.status_code, 404)
        followup.refresh_from_db()
        self.assertIsNone(followup.completed_at)

    def test_followup_can_be_completed_by_owner(self):
        followup = FollowUp.objects.create(
            owner=self.owner, rfq=self.rfq,
            due_on=timezone.localdate(), note="Manual callback",
        )
        self.login_owner()
        response = self.client.post(
            reverse("dashboard:followup_complete", args=[followup.pk])
        )
        self.assertEqual(response.status_code, 302)
        followup.refresh_from_db()
        self.assertIsNotNone(followup.completed_at)
