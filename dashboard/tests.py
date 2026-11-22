from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from .models import Customer, Product, RFQ, RFQLine, Supplier, SupplierOffer


class FoundationTests(TestCase):
    def test_home_requires_login(self):
        response = self.client.get(reverse("dashboard:home"))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('dashboard:home')}")

    def test_login_opens_dashboard(self):
        get_user_model().objects.create_user(username="demo", password="local-test-password")
        response = self.client.post(reverse("login"), {
            "username": "demo", "password": "local-test-password",
        })
        self.assertRedirects(response, reverse("dashboard:home"))
        self.assertContains(self.client.get(reverse("dashboard:home")), "Steel quotation workspace")

    def test_login_page_is_available(self):
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sign in")


class CatalogueTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="owner", password="local-test-password")
        self.other = get_user_model().objects.create_user(username="other", password="local-test-password")
        self.client.force_login(self.user)

    def test_owner_can_create_each_catalogue_record(self):
        submissions = [
            ("dashboard:customer_create", {"name": "Synthetic Customer"}, Customer),
            ("dashboard:supplier_create", {"name": "Synthetic Supplier"}, Supplier),
            ("dashboard:product_create", {"name": "Round bar", "grade": "304", "shape": "round_bar", "dimensions": "25 mm diameter", "unit": "kg", "weight_basis": "na", "weight_kg": ""}, Product),
        ]
        for route, data, model in submissions:
            response = self.client.post(reverse(route), data)
            self.assertEqual(response.status_code, 302)
            record = model.objects.get()
            self.assertEqual(record.owner, self.user)

    def test_create_forms_ignore_submitted_owner(self):
        response = self.client.post(reverse("dashboard:customer_create"), {
            "name": "Owned by session", "owner": self.other.pk,
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Customer.objects.get(name="Owned by session").owner, self.user)

    def test_catalogue_lists_are_scoped_to_signed_in_owner(self):
        Customer.objects.create(owner=self.user, name="My Customer")
        Customer.objects.create(owner=self.other, name="Other Customer")
        response = self.client.get(reverse("dashboard:customer_list"))
        self.assertContains(response, "My Customer")
        self.assertNotContains(response, "Other Customer")

    def test_other_users_records_cannot_be_viewed_edited_or_deleted(self):
        records = [
            (Customer.objects.create(owner=self.other, name="Private Customer"), "customer"),
            (Supplier.objects.create(owner=self.other, name="Private Supplier"), "supplier"),
            (Product.objects.create(owner=self.other, name="Private Product", shape="sheet", unit="kg"), "product"),
        ]
        for record, kind in records:
            for action in ("update", "delete"):
                response = self.client.get(reverse(f"dashboard:{kind}_{action}", args=[record.pk]))
                self.assertEqual(response.status_code, 404)
            response = self.client.post(reverse(f"dashboard:{kind}_delete", args=[record.pk]))
            self.assertEqual(response.status_code, 404)
            self.assertTrue(type(record).objects.filter(pk=record.pk).exists())

    def test_owner_can_edit_and_delete_catalogue_records(self):
        records = [
            (Customer.objects.create(owner=self.user, name="Old customer"), "customer", {"name": "New customer"}),
            (Supplier.objects.create(owner=self.user, name="Old supplier"), "supplier", {"name": "New supplier"}),
            (Product.objects.create(owner=self.user, name="Old product", shape="sheet", unit="kg"), "product", {
                "name": "New product", "shape": "plate", "unit": "tonne", "weight_basis": "na",
            }),
        ]
        for record, kind, data in records:
            response = self.client.post(reverse(f"dashboard:{kind}_update", args=[record.pk]), data)
            self.assertEqual(response.status_code, 302)
            record.refresh_from_db()
            self.assertEqual(record.name, data["name"])
            self.assertEqual(record.owner, self.user)
            response = self.client.post(reverse(f"dashboard:{kind}_delete", args=[record.pk]))
            self.assertEqual(response.status_code, 302)
            self.assertFalse(type(record).objects.filter(pk=record.pk).exists())

    def test_product_weight_is_validated_and_weight_basis_is_explicit(self):
        invalid = self.client.post(reverse("dashboard:product_create"), {
            "name": "Invalid bar", "shape": "round_bar", "unit": "piece", "weight_basis": "na", "weight_kg": "12.5",
        })
        self.assertEqual(invalid.status_code, 200)
        self.assertFalse(Product.objects.filter(name="Invalid bar").exists())
        valid = self.client.post(reverse("dashboard:product_create"), {
            "name": "Weighted bar", "shape": "round_bar", "unit": "piece", "weight_basis": "theoretical", "weight_kg": "12.5",
        })
        self.assertEqual(valid.status_code, 302)
        self.assertEqual(str(Product.objects.get(name="Weighted bar").weight_kg), "12.500")

    def test_product_rejects_unknown_units_and_non_positive_weight(self):
        for unit, weight in (("bundle", ""), ("kg", "0"), ("piece", "-2")):
            with self.subTest(unit=unit, weight=weight):
                response = self.client.post(reverse("dashboard:product_create"), {
                    "name": f"Invalid {unit} {weight}", "shape": "round_bar", "unit": unit,
                    "weight_basis": "actual", "weight_kg": weight,
                })
                self.assertEqual(response.status_code, 200)


class RFQIntakeTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="rfq-owner", password="local-test-password")
        self.other = get_user_model().objects.create_user(username="rfq-other", password="local-test-password")
        self.customer = Customer.objects.create(owner=self.user, name="Synthetic customer")
        self.product = Product.objects.create(owner=self.user, name="304 round bar", shape="round_bar", unit="kg")
        self.foreign_customer = Customer.objects.create(owner=self.other, name="Other customer")
        self.foreign_product = Product.objects.create(owner=self.other, name="Private plate", shape="plate", unit="kg")
        self.client.force_login(self.user)

    def payload(self, **overrides):
        data = {
            "customer": self.customer.pk, "reference": "ENQ-001", "source": "whatsapp",
            "received_on": "2026-11-22", "required_by": "", "notes": "Synthetic enquiry",
            "lines-TOTAL_FORMS": "2", "lines-INITIAL_FORMS": "0", "lines-MIN_NUM_FORMS": "1", "lines-MAX_NUM_FORMS": "1000",
            "lines-0-product": self.product.pk, "lines-0-description": "", "lines-0-grade": "304",
            "lines-0-dimensions": "25 mm diameter", "lines-0-quantity": "125.500", "lines-0-unit": "kg", "lines-0-DELETE": "",
            "lines-1-product": "", "lines-1-description": "Sheet", "lines-1-grade": "", "lines-1-dimensions": "2 x 1 m x 3 mm",
            "lines-1-quantity": "12", "lines-1-unit": "piece", "lines-1-DELETE": "",
        }
        data.update(overrides)
        return data

    def test_owner_can_create_enquiry_with_multiple_metric_lines(self):
        response = self.client.post(reverse("dashboard:rfq_create"), self.payload())
        self.assertEqual(response.status_code, 302)
        rfq = RFQ.objects.get()
        self.assertRedirects(response, reverse("dashboard:rfq_detail", args=[rfq.pk]))
        self.assertEqual(rfq.owner, self.user)
        self.assertEqual(rfq.customer, self.customer)
        self.assertEqual(rfq.lines.count(), 2)
        self.assertTrue(all(line.owner == self.user for line in rfq.lines.all()))
        self.assertEqual(str(rfq.lines.get(product=self.product).quantity), "125.500")

    def test_account_boundaries_exclude_foreign_customer_product_and_rfq(self):
        response = self.client.get(reverse("dashboard:rfq_create"))
        self.assertContains(response, "Synthetic customer")
        self.assertNotContains(response, "Other customer")
        foreign_rfq = RFQ.objects.create(owner=self.other, customer=self.foreign_customer, received_on="2026-11-21")
        self.assertEqual(self.client.get(reverse("dashboard:rfq_detail", args=[foreign_rfq.pk])).status_code, 404)
        self.assertNotContains(self.client.get(reverse("dashboard:rfq_list")), str(foreign_rfq))

    def test_foreign_customer_and_product_cannot_be_submitted(self):
        bad_customer = self.client.post(reverse("dashboard:rfq_create"), self.payload(customer=self.foreign_customer.pk))
        self.assertEqual(bad_customer.status_code, 200)
        self.assertFalse(RFQ.objects.exists())
        bad_product = self.client.post(reverse("dashboard:rfq_create"), self.payload(**{"lines-0-product": self.foreign_product.pk}))
        self.assertEqual(bad_product.status_code, 200)
        self.assertFalse(RFQ.objects.exists())

    def test_invalid_quantity_unit_and_missing_item_details_are_rejected(self):
        for changes in (
            {"lines-0-quantity": "0"}, {"lines-0-quantity": "-2"}, {"lines-0-unit": "bundle"},
            {"lines-0-product": "", "lines-0-grade": "", "lines-0-dimensions": "", "lines-0-description": ""},
        ):
            with self.subTest(changes=changes):
                response = self.client.post(reverse("dashboard:rfq_create"), self.payload(**changes))
                self.assertEqual(response.status_code, 200)
                self.assertFalse(RFQ.objects.exists())

    def test_signed_in_user_required_for_intake(self):
        self.client.logout()
        response = self.client.get(reverse("dashboard:rfq_create"))
        self.assertEqual(response.status_code, 302)


class SupplierOfferTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="offer-owner", password="local-test-password")
        self.other = get_user_model().objects.create_user(username="offer-other", password="local-test-password")
        self.customer = Customer.objects.create(owner=self.user, name="Offer customer")
        self.product = Product.objects.create(owner=self.user, name="Synthetic round bar", shape="round_bar", unit="kg")
        self.supplier = Supplier.objects.create(owner=self.user, name="Supplier Alpha")
        self.other_supplier = Supplier.objects.create(owner=self.other, name="Private Supplier")
        self.rfq = RFQ.objects.create(owner=self.user, customer=self.customer, reference="OFF-001", received_on="2026-11-22")
        self.line = RFQLine.objects.create(
            owner=self.user, rfq=self.rfq, product=self.product, quantity="100", unit=Product.Unit.KG,
        )
        self.client.force_login(self.user)

    def post_offer(self, **overrides):
        data = {
            "supplier": self.supplier.pk,
            "available_quantity": "100",
            "unit": Product.Unit.KG,
            "unit_price": "90.0000",
            "freight_cost": "500.00",
            "packaging_cost": "100.00",
            "delivery_days": "4",
        }
        data.update(overrides)
        return self.client.post(reverse("dashboard:supplier_offer_create", args=[self.rfq.pk, self.line.pk]), data)

    def make_offer(self, **overrides):
        values = {
            "owner": self.user,
            "rfq_line": self.line,
            "supplier": self.supplier,
            "available_quantity": "100",
            "unit": Product.Unit.KG,
            "unit_price": "90.0000",
            "freight_cost": "500.00",
            "packaging_cost": "100.00",
            "delivery_days": 4,
        }
        values.update(overrides)
        offer = SupplierOffer(**values)
        offer.full_clean()
        offer.save()
        return offer

    def test_owner_can_add_offer_and_comparison_displays_landed_cost(self):
        response = self.post_offer()
        self.assertRedirects(response, reverse("dashboard:rfq_detail", args=[self.rfq.pk]))
        offer = SupplierOffer.objects.get()
        self.assertEqual(offer.owner, self.user)
        self.assertEqual(offer.rfq_line, self.line)
        detail = self.client.get(reverse("dashboard:rfq_detail", args=[self.rfq.pk]))
        self.assertContains(detail, "INR 96.0000")
        self.assertContains(detail, "INR 9600.00")
        self.assertContains(detail, "Freight (INR 500.00)")
        self.assertContains(detail, "packaging/incidental cost (INR 100.00)")
        self.assertContains(detail, "Covers 100.000")
        self.assertContains(detail, "4 days")

    def test_offers_are_sorted_by_normalized_landed_rate_and_tonne_is_converted(self):
        expensive = self.make_offer()
        cheaper = self.make_offer(
            available_quantity="0.1", unit=Product.Unit.TONNE, unit_price="90000.0000",
            freight_cost="300.00", packaging_cost="0.00", delivery_days=2,
            supplier=Supplier.objects.create(owner=self.user, name="Supplier Beta"),
        )
        self.assertEqual(cheaper.unit_conversion_factor, 1000)
        self.assertEqual(cheaper.landed_cost_per_requested_unit, 93)
        response = self.client.get(reverse("dashboard:rfq_detail", args=[self.rfq.pk]))
        self.assertEqual(response.context["rfq"].lines.all()[0].comparison_offers, [cheaper, expensive])
        self.assertContains(response, "Converted metric tonne to kilogram (kg) using the metric weight ratio.")
        self.assertContains(response, "0.100 Metric tonne")
        self.assertContains(response, "100.000 Kilogram (kg) after conversion")

    def test_partial_offer_cost_allocates_freight_over_covered_quantity(self):
        offer = self.make_offer(available_quantity="50", freight_cost="100.00", packaging_cost="50.00")
        self.assertEqual(offer.covered_quantity, 50)
        self.assertFalse(offer.covers_full_quantity)
        self.assertEqual(offer.landed_cost_per_requested_unit, 93)
        self.assertEqual(offer.total_landed_cost, 4650)

    def test_piece_conversion_uses_recorded_catalogue_weight(self):
        self.product.weight_kg = "2.500"
        self.product.weight_basis = Product.WeightBasis.THEORETICAL
        self.product.save()
        self.line.quantity = "25"
        self.line.save()
        offer = self.make_offer(
            available_quantity="20", unit=Product.Unit.PIECE, unit_price="250.0000",
            freight_cost="250.00", packaging_cost="0.00",
        )
        self.assertEqual(offer.unit_conversion_factor, 2.5)
        self.assertEqual(offer.converted_available_quantity, 50)
        self.assertEqual(offer.landed_cost_per_requested_unit, 110)
        self.assertEqual(offer.total_landed_cost, 2750)
        self.assertIn("theoretical weight of 2.500 kg per piece", offer.conversion_assumption)
        self.product.weight_kg = "5.000"
        self.product.save()
        self.assertEqual(offer.landed_cost_per_requested_unit, 110)
        self.assertIn("2.500 kg per piece", offer.conversion_assumption)

    def test_offer_units_must_be_convertible_and_invalid_quantities_are_rejected(self):
        self.line.unit = Product.Unit.METRE
        self.line.save()
        invalid_unit = self.post_offer(unit=Product.Unit.TONNE)
        self.assertEqual(invalid_unit.status_code, 200)
        self.assertFalse(SupplierOffer.objects.exists())
        self.line.unit = Product.Unit.KG
        self.line.save()
        for changes in (
            {"available_quantity": "0"}, {"available_quantity": "-2"},
            {"unit_price": "0"}, {"freight_cost": "-1"}, {"delivery_days": "-1"},
        ):
            with self.subTest(changes=changes):
                response = self.post_offer(**changes)
                self.assertEqual(response.status_code, 200)
                self.assertFalse(SupplierOffer.objects.exists())

    def test_supplier_and_enquiry_ownership_boundaries_are_enforced(self):
        foreign_supplier = self.post_offer(supplier=self.other_supplier.pk)
        self.assertEqual(foreign_supplier.status_code, 200)
        self.assertFalse(SupplierOffer.objects.exists())
        invalid_offer = SupplierOffer(
            owner=self.user, rfq_line=self.line, supplier=self.other_supplier,
            available_quantity="100", unit=Product.Unit.KG, unit_price="90", delivery_days=4,
        )
        with self.assertRaises(ValidationError):
            invalid_offer.full_clean()

        # Even invalid rows written outside the application cannot expose a foreign supplier.
        SupplierOffer.objects.create(
            owner=self.user, rfq_line=self.line, supplier=self.other_supplier,
            available_quantity="100", unit=Product.Unit.KG, unit_price="90", delivery_days=4,
        )
        detail = self.client.get(reverse("dashboard:rfq_detail", args=[self.rfq.pk]))
        self.assertNotContains(detail, "Private Supplier")

        other_customer = Customer.objects.create(owner=self.other, name="Other offer customer")
        other_rfq = RFQ.objects.create(owner=self.other, customer=other_customer, received_on="2026-11-22")
        other_line = RFQLine.objects.create(owner=self.other, rfq=other_rfq, quantity="100", unit=Product.Unit.KG, description="Other steel")
        self.assertEqual(self.client.get(reverse("dashboard:rfq_detail", args=[other_rfq.pk])).status_code, 404)
        self.assertEqual(
            self.client.get(reverse("dashboard:supplier_offer_create", args=[other_rfq.pk, other_line.pk])).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(reverse("dashboard:supplier_offer_create", args=[self.rfq.pk, other_line.pk])).status_code,
            404,
        )

    def test_offer_entry_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("dashboard:supplier_offer_create", args=[self.rfq.pk, self.line.pk]))
        self.assertEqual(response.status_code, 302)
