from __future__ import annotations

from echo.common.health_checks import app_database_health

from celery import shared_task
from django.contrib.auth import get_user_model

from .models import Document
from .processing import DocumentProcessingService


@shared_task(bind=True, autoretry_for=(OSError,), retry_backoff=True, max_retries=3)
def process_document(self, document_id: str, user_id: str, storage_key: str):
    user = get_user_model().objects.get(pk=user_id)
    document = Document.objects.get(pk=document_id, owner=user)
    return DocumentProcessingService.process(user, document, storage_key)


@shared_task
def health_task():
    return app_database_health("documents")
