from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .models import APIToken, UserProfile


class AuthenticationTests(TestCase):
    def test_user_creation_normalizes_email_and_creates_profile(self):
        user = get_user_model().objects.create_user(
            email=" Person@Example.COM ",
            password="StrongPassphrase123!",
        )
        self.assertEqual(user.email, "person@example.com")
        self.assertTrue(UserProfile.objects.filter(user=user).exists())

    def test_jwt_login_and_api_token_authentication(self):
        user = get_user_model().objects.create_user(
            email="person@example.com",
            password="StrongPassphrase123!",
        )
        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": user.email, "password": "StrongPassphrase123!"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.json())

        _, raw_token = APIToken.issue(user, "automation", timezone.now() + timedelta(days=1))
        client = APIClient()
        response = client.get("/api/v1/endpoint-catalog/", HTTP_X_API_KEY=raw_token)
        self.assertEqual(response.status_code, 200)
