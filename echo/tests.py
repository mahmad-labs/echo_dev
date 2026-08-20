from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

class PlatformSmokeTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user(email='test@example.com',password='StrongPassphrase123!')
    def test_health(self): self.assertEqual(self.client.get('/health/').status_code,200)
    def test_dashboard_requires_authentication(self): self.assertEqual(self.client.get('/').status_code,302)
    def test_jwt_login(self):
        response=self.client.post('/api/v1/auth/login/',{'email':'test@example.com','password':'StrongPassphrase123!'},content_type='application/json')
        self.assertEqual(response.status_code,200); self.assertIn('access',response.json())
    def test_endpoint_catalog(self):
        client=APIClient(); client.force_authenticate(self.user); response=client.get('/api/v1/endpoint-catalog/')
        self.assertEqual(response.status_code,200); self.assertGreaterEqual(response.data['count'],238)
