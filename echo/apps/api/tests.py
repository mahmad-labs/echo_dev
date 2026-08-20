from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient


class CompatibilityAPITests(TestCase):
    def setUp(self):
        self.first = get_user_model().objects.create_user(
            email="first@example.com",
            password="StrongPassphrase123!",
        )
        self.second = get_user_model().objects.create_user(
            email="second@example.com",
            password="StrongPassphrase123!",
        )

    def test_owner_isolation_on_specification_route(self):
        first_client = APIClient()
        first_client.force_authenticate(self.first)
        created = first_client.post(
            "/api/chat/conversations/",
            {"name": "private", "title": "Private conversation"},
            format="json",
        )
        self.assertEqual(created.status_code, 201)

        second_client = APIClient()
        second_client.force_authenticate(self.second)
        listing = second_client.get("/api/chat/conversations/")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.data, [])
        detail = second_client.patch(
            f"/api/chat/conversations/{created.data['id']}/",
            {"title": "Changed"},
            format="json",
        )
        self.assertEqual(detail.status_code, 404)


    def test_cross_owner_relationship_is_rejected(self):
        first_client = APIClient()
        first_client.force_authenticate(self.first)
        conversation = first_client.post(
            "/api/chat/conversations/",
            {"name": "owned", "title": "Owned conversation"},
            format="json",
        )
        self.assertEqual(conversation.status_code, 201)

        second_client = APIClient()
        second_client.force_authenticate(self.second)
        response = second_client.post(
            "/api/chat/messages/",
            {
                "name": "intrusion",
                "role": "user",
                "content": "Cross-owner relation",
                "conversation": conversation.data["id"],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_catalog_contains_full_specification(self):
        client = APIClient()
        client.force_authenticate(self.first)
        response = client.get("/api/v1/endpoint-catalog/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 238)
