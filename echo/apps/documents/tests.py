import shutil
import tempfile
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.test import TestCase, override_settings

from echo.apps.knowledge.models import DocumentSection, KnowledgeDocument

from .models import Document, DocumentContent, ProcessingJob
from .processing import DocumentProcessingError, DocumentProcessingService


class DocumentsModelTests(TestCase):
    def test_models_are_registered(self):
        from django.apps import apps

        self.assertGreaterEqual(len(list(apps.get_app_config("documents").get_models())), 7)


class DocumentProcessingTests(TestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp(prefix="echo-documents-test-")
        self.settings_override = override_settings(MEDIA_ROOT=self.media_root)
        self.settings_override.enable()
        self.user = get_user_model().objects.create_user(
            email="documents@example.com",
            password="DocumentsPassword!2026",
        )

    def tearDown(self):
        self.settings_override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)

    def make_document(self, content=b"Echo connects documents to searchable knowledge."):
        storage_key = default_storage.save("tests/brief.txt", content=ContentFile(content))
        document = Document.objects.create(
            owner=self.user,
            name="brief.txt",
            title="Brief",
            status="uploaded",
            category="txt",
            configuration={"storage_key": storage_key},
        )
        return document, storage_key

    def test_text_document_is_extracted_and_indexed(self):
        document, storage_key = self.make_document()
        result = DocumentProcessingService.process(self.user, document, storage_key)
        document.refresh_from_db()
        self.assertEqual(result["status"], "indexed")
        self.assertEqual(document.status, "indexed")
        self.assertTrue(DocumentContent.objects.filter(owner=self.user, name=f"document:{document.pk}:content").exists())
        self.assertTrue(KnowledgeDocument.objects.filter(owner=self.user, name=f"document:{document.pk}").exists())
        self.assertTrue(DocumentSection.objects.filter(owner=self.user, name__startswith=f"document:{document.pk}:section:").exists())
        self.assertTrue(ProcessingJob.objects.filter(owner=self.user, status="completed").exists())

    def test_unreadable_document_persists_failure_state(self):
        document, storage_key = self.make_document(b"")
        with self.assertRaises(DocumentProcessingError):
            DocumentProcessingService.process(self.user, document, storage_key)
        document.refresh_from_db()
        self.assertEqual(document.status, "failed")
        self.assertIn("processing_error", document.configuration)
        self.assertTrue(ProcessingJob.objects.filter(owner=self.user, status="failed").exists())
