from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from echo.apps.chat.models import Conversation, Message
from echo.apps.documents.models import Document
from echo.apps.tasks.models import Task


class WorkspaceExperienceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            email="workspace@example.com",
            password="EchoWorkspacePassword!2026",
            display_name="Avery",
        )

    def setUp(self):
        self.client.force_login(self.user)

    def test_home_renders_ai_workspace_shell(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Tell Echo what you want to move forward.")
        self.assertContains(response, "Microphone idle")
        self.assertNotContains(response, "Platform modules")

    def test_every_workspace_section_renders(self):
        sections = (
            "home", "chat", "voice", "knowledge", "memory", "projects", "planner",
            "tasks", "analytics", "browser", "documents", "settings",
            "notifications", "email", "calendar", "agents", "workflows", "code",
        )
        for section in sections:
            with self.subTest(section=section):
                response = self.client.get(reverse("workspace", kwargs={"section": section}))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'class="echo-shell"')

    def test_unknown_workspace_is_not_found(self):
        response = self.client.get(reverse("workspace", kwargs={"section": "unknown"}))
        self.assertEqual(response.status_code, 404)

    def test_task_creation_is_persisted(self):
        response = self.client.post(
            reverse("workspace-action"),
            {"section": "tasks", "title": "Protect the launch", "description": "Resolve open risks."},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 201)
        task = Task.objects.get(owner=self.user, title="Protect the launch")
        self.assertEqual(task.description, "Resolve open risks.")

    def test_task_completion_is_persisted(self):
        task = Task.objects.create(owner=self.user, name="Review", title="Review", status="active")
        response = self.client.post(
            reverse("workspace-record-update"),
            data={"section": "tasks", "record_id": str(task.pk), "status": "completed"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        task.refresh_from_db()
        self.assertEqual(task.status, "completed")

    @override_settings(AI_PROVIDER_BASE_URL="", AI_PROVIDER_API_KEY="", AI_PROVIDER_MODEL="")
    def test_command_is_saved_when_provider_is_not_configured(self):
        response = self.client.post(
            reverse("ai-command"),
            data={"prompt": "Build a launch plan", "section": "planner"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 503)
        self.assertTrue(response.json()["saved"])
        conversation = Conversation.objects.get(owner=self.user)
        self.assertEqual(conversation.data["origin"], "planner")
        self.assertTrue(Message.objects.filter(conversation=conversation, role="user").exists())

    @override_settings(
        AI_PROVIDER_BASE_URL="https://provider.example/v1",
        AI_PROVIDER_API_KEY="secret",
        AI_PROVIDER_MODEL="echo-model",
    )
    @patch("echo.apps.core.command_service.AIExecutionService.generate")
    def test_live_command_returns_provider_response(self, generate):
        class RequestRecord:
            pk = "request-id"
            completion_tokens = 11
            latency = 42

        class ResponseRecord:
            pk = "response-id"
            content = "Here is the plan."

        generate.return_value = (RequestRecord(), ResponseRecord(), {})
        response = self.client.post(
            reverse("ai-command"),
            data={"prompt": "Build a launch plan", "section": "planner"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["content"], "Here is the plan.")
        self.assertTrue(Message.objects.filter(owner=self.user, role="assistant").exists())

    def test_workspace_search_is_owner_scoped(self):
        Task.objects.create(owner=self.user, name="Private launch", title="Private launch")
        other = get_user_model().objects.create_user(
            email="other@example.com", password="AnotherSecurePassword!2026"
        )
        Task.objects.create(owner=other, name="Private competitor", title="Private competitor")
        response = self.client.get(reverse("workspace-search"), {"q": "Private"})
        self.assertEqual(response.status_code, 200)
        titles = [item["title"] for item in response.json()["results"]]
        self.assertIn("Private launch", titles)
        self.assertNotIn("Private competitor", titles)

    def test_document_upload_creates_file_and_document_records(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        upload = SimpleUploadedFile("brief.txt", b"Echo launch brief", content_type="text/plain")
        response = self.client.post(reverse("workspace-upload"), {"file": upload})
        self.assertEqual(response.status_code, 201)
        document = Document.objects.get(owner=self.user, title="brief")
        self.assertEqual(document.status, "indexed")
