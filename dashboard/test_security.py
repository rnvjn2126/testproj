from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .models import Customer, RFQ


class SecurityRegressionTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="security-user", password="Valid-Local-Test-Password-4!",
        )
        self.customer = Customer.objects.create(owner=self.user, name="Synthetic customer")
        self.rfq = RFQ.objects.create(
            owner=self.user, customer=self.customer, received_on="2026-11-22",
        )

    def test_password_policy_rejects_short_or_numeric_passwords(self):
        for password in ("12345", "123456789012"):
            with self.subTest(password=password), self.assertRaises(ValidationError):
                validate_password(password, user=self.user)

        validate_password("Granite-Bridge-Blue-2047!", user=self.user)

    def test_state_changes_require_a_valid_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        url = reverse("dashboard:rfq_update_status", args=[self.rfq.pk])
        data = {"status": RFQ.Status.IN_PROGRESS}

        denied = client.post(url, data, HTTP_HOST="localhost")
        self.assertEqual(denied.status_code, 403)
        self.rfq.refresh_from_db()
        self.assertEqual(self.rfq.status, RFQ.Status.NEW)

        login_page = client.get(reverse("login"), HTTP_HOST="localhost")
        token = login_page.cookies[settings.CSRF_COOKIE_NAME].value
        accepted = client.post(
            url, data, HTTP_HOST="localhost", HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(accepted.status_code, 302)
        self.rfq.refresh_from_db()
        self.assertEqual(self.rfq.status, RFQ.Status.IN_PROGRESS)

    @override_settings(DEBUG=False)
    def test_untrusted_host_header_is_rejected(self):
        response = Client().get(reverse("login"), HTTP_HOST="attacker.example")
        self.assertEqual(response.status_code, 400)

    def test_development_secret_and_host_allowlist_are_safe(self):
        self.assertGreaterEqual(len(settings.SECRET_KEY), 50)
        self.assertNotEqual(settings.SECRET_KEY, "local-development-only-change-before-deployment")
        self.assertNotIn("*", settings.ALLOWED_HOSTS)

    def test_browser_security_headers_are_set(self):
        response = self.client.get(reverse("login"))
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response["X-Frame-Options"], "DENY")
        self.assertEqual(response["Referrer-Policy"], "same-origin")
