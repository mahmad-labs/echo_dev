from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.files.storage import default_storage
from django.db import transaction
from django.utils import timezone

from echo.apps.knowledge.models import DocumentSection, KnowledgeDocument

from .extractors import DocumentExtractor
from .models import Document, DocumentContent, ProcessingJob


class DocumentProcessingError(RuntimeError):
    pass


def _chunk_text(text: str, *, target_chars: int = 4000, overlap_chars: int = 300) -> list[str]:
    """Split extracted text at paragraph boundaries with small contextual overlap."""
    normalized = "\n".join(line.rstrip() for line in text.replace("\x00", "").splitlines()).strip()
    if not normalized:
        return []
    paragraphs = [item.strip() for item in normalized.split("\n\n") if item.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(candidate) <= target_chars:
            current = candidate
            continue
        if current:
            chunks.append(current)
            prefix = current[-overlap_chars:] if overlap_chars else ""
            current = f"{prefix}\n\n{paragraph}".strip()
        else:
            for start in range(0, len(paragraph), max(1, target_chars - overlap_chars)):
                chunks.append(paragraph[start : start + target_chars])
            current = ""
    if current:
        chunks.append(current)
    return chunks


class DocumentProcessingService:
    """Extract and index an uploaded document into Echo's existing knowledge models."""

    @classmethod
    def _local_path(cls, storage_key: str) -> tuple[Path, bool]:
        try:
            return Path(default_storage.path(storage_key)), False
        except (AttributeError, NotImplementedError):
            suffix = Path(storage_key).suffix
            handle = tempfile.NamedTemporaryFile(prefix="echo-document-", suffix=suffix, delete=False)
            try:
                with default_storage.open(storage_key, "rb") as source:
                    for chunk in iter(lambda: source.read(1024 * 1024), b""):
                        handle.write(chunk)
            finally:
                handle.close()
            return Path(handle.name), True

    @classmethod
    def _job(cls, user, document: Document) -> ProcessingJob:
        job, _ = ProcessingJob.objects.get_or_create(
            owner=user,
            name=f"document:{document.pk}:processing",
            defaults={
                "title": f"Process {document.title or document.name}",
                "description": "Extract text and connect the document to Echo Knowledge.",
                "status": "queued",
                "category": "document_indexing",
                "configuration": {"document_id": str(document.pk)},
            },
        )
        return job

    @classmethod
    def process(cls, user, document: Document, storage_key: str) -> dict[str, Any]:
        job = cls._job(user, document)
        job.status = "running"
        job.configuration = {**(job.configuration or {}), "started_at": timezone.now().isoformat()}
        job.save(update_fields=["status", "configuration", "updated_at"])
        document.status = "processing"
        document.save(update_fields=["status", "updated_at"])

        path: Path | None = None
        temporary = False
        try:
            path, temporary = cls._local_path(storage_key)
            text = DocumentExtractor().extract(path)
            max_chars = int(getattr(settings, "DOCUMENT_MAX_EXTRACTED_CHARS", 2_000_000))
            text = str(text or "").replace("\x00", "").strip()
            truncated = len(text) > max_chars
            text = text[:max_chars]
            if not text:
                raise DocumentProcessingError("No readable text could be extracted from this file.")
            chunks = _chunk_text(text)
            with transaction.atomic():
                content, _ = DocumentContent.objects.update_or_create(
                    owner=user,
                    name=f"document:{document.pk}:content",
                    defaults={
                        "title": document.title or document.name,
                        "description": text,
                        "status": "completed",
                        "category": document.category,
                        "configuration": {
                            "document_id": str(document.pk),
                            "character_count": len(text),
                            "chunk_count": len(chunks),
                            "truncated": truncated,
                        },
                    },
                )
                knowledge, _ = KnowledgeDocument.objects.update_or_create(
                    owner=user,
                    name=f"document:{document.pk}",
                    defaults={
                        "title": document.title or document.name,
                        "description": text,
                        "status": "active",
                        "category": document.category or "document",
                        "configuration": {
                            "source_document_id": str(document.pk),
                            "document_content_id": str(content.pk),
                            "storage_key": storage_key,
                            "chunk_count": len(chunks),
                            "truncated": truncated,
                        },
                    },
                )
                section_prefix = f"document:{document.pk}:section:"
                DocumentSection.objects.filter(owner=user, name__startswith=section_prefix).delete()
                DocumentSection.objects.bulk_create(
                    [
                        DocumentSection(
                            owner=user,
                            name=f"{section_prefix}{index}",
                            title=f"{document.title or document.name} · Part {index}",
                            description=chunk,
                            status="active",
                            category="extracted",
                            configuration={
                                "knowledge_document_id": str(knowledge.pk),
                                "source_document_id": str(document.pk),
                                "position": index,
                            },
                        )
                        for index, chunk in enumerate(chunks, 1)
                    ],
                    batch_size=100,
                )
                configuration = dict(document.configuration or {})
                configuration.update(
                    {
                        "storage_key": storage_key,
                        "document_content_id": str(content.pk),
                        "knowledge_document_id": str(knowledge.pk),
                        "processing_job_id": str(job.pk),
                    }
                )
                data = dict(document.data or {})
                data.update({"character_count": len(text), "chunk_count": len(chunks), "truncated": truncated})
                document.configuration = configuration
                document.data = data
                document.status = "indexed"
                document.save(update_fields=["configuration", "data", "status", "updated_at"])
                job.status = "completed"
                job.configuration = {
                    **(job.configuration or {}),
                    "completed_at": timezone.now().isoformat(),
                    "document_content_id": str(content.pk),
                    "knowledge_document_id": str(knowledge.pk),
                    "chunk_count": len(chunks),
                }
                job.save(update_fields=["status", "configuration", "updated_at"])
            return {
                "document_id": str(document.pk),
                "knowledge_document_id": str(knowledge.pk),
                "content_id": str(content.pk),
                "chunk_count": len(chunks),
                "status": "indexed",
            }
        except Exception as exc:
            document.status = "failed"
            document.configuration = {**(document.configuration or {}), "processing_error": str(exc), "processing_job_id": str(job.pk)}
            document.save(update_fields=["status", "configuration", "updated_at"])
            job.status = "failed"
            job.configuration = {**(job.configuration or {}), "failed_at": timezone.now().isoformat(), "error": str(exc), "error_type": exc.__class__.__name__}
            job.save(update_fields=["status", "configuration", "updated_at"])
            raise DocumentProcessingError(str(exc)) from exc
        finally:
            if temporary and path:
                try:
                    os.unlink(path)
                except FileNotFoundError:
                    pass
