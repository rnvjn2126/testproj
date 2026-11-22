from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


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
