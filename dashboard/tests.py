from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Customer, Product, Supplier


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
