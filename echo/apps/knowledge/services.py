from __future__ import annotations

import re
from typing import Any

from django.db import transaction

from echo.apps.vector_database.embedding import feature_hash_embedding
from echo.apps.vector_database.vector_math import cosine_similarity
from echo.common.services import DomainService

from .models import ContentBlock, DocumentSection, KnowledgeDocument, KnowledgePermission, KnowledgeVersion
from .search import KnowledgeSearchService


class KnowledgeAgentService:
    """Central interface for Echo's retrievable external/user-provided knowledge."""

    @staticmethod
    def _owned(model, user):
        query = model.objects.all()
        return query if user.is_staff else query.filter(owner=user)

    @classmethod
    def search(cls, user, query: str, *, limit: int = 12) -> list[dict[str, Any]]:
        query = str(query or "").strip()
        if not query:
            return []
        lexical = KnowledgeSearchService.search(user, query, limit=max(limit * 2, 20))
        query_vector = feature_hash_embedding(query, dimensions=192)
        candidates: dict[tuple[str, str], dict[str, Any]] = {}
        for hit in lexical:
            candidates[(hit.model, hit.identifier)] = {
                "model": hit.model,
                "id": hit.identifier,
                "title": hit.title,
                "excerpt": hit.excerpt,
                "lexical_score": float(hit.score),
            }
        # Include recent documents/sections even when no literal term overlaps, then
        # use deterministic feature-hash cosine similarity as a semantic fallback.
        for model in (KnowledgeDocument, DocumentSection, ContentBlock):
            for item in cls._owned(model, user).filter(status="active").order_by("-updated_at")[:120]:
                key = (model._meta.label_lower, str(item.pk))
                candidates.setdefault(key, {
                    "model": model._meta.label_lower,
                    "id": str(item.pk),
                    "title": item.title or item.name,
                    "excerpt": item.description[:1200],
                    "lexical_score": 0.0,
                })
        ranked = []
        for item in candidates.values():
            text = f"{item['title']}\n{item['excerpt']}"
            semantic = cosine_similarity(query_vector, feature_hash_embedding(text, dimensions=192)) if text.strip() else 0.0
            combined = item["lexical_score"] * 0.55 + semantic * 4.0
            ranked.append({**item, "semantic_score": round(float(semantic), 6), "score": round(float(combined), 6)})
        return sorted(ranked, key=lambda row: (-row["score"], row["title"].casefold()))[:limit]

    @classmethod
    @transaction.atomic
    def ingest(
        cls,
        user,
        *,
        title: str,
        content: str,
        source_type: str = "agent",
        source_id: str = "",
        category: str = "research",
        metadata: dict[str, Any] | None = None,
    ) -> KnowledgeDocument:
        title = re.sub(r"\s+", " ", str(title or "").strip())[:255]
        content = str(content or "").strip()
        if not content:
            raise ValueError("Knowledge content is required.")
        fingerprint = feature_hash_embedding(content[:10000], dimensions=64)
        config = {
            "source_type": source_type,
            "source_id": str(source_id or ""),
            "semantic_fingerprint": fingerprint,
            **(metadata or {}),
        }
        existing = cls._owned(KnowledgeDocument, user).filter(name=f"{source_type}:{source_id}").first() if source_id else None
        if existing:
            KnowledgeVersion.objects.create(
                owner=user,
                name=f"knowledge:{existing.pk}:version",
                title=f"Previous version of {existing.title or existing.name}",
                description=existing.description,
                status="completed",
                category="snapshot",
                configuration={"knowledge_document_id": str(existing.pk)},
            )
            existing.title = title or existing.title
            existing.description = content
            existing.category = category
            existing.configuration = {**(existing.configuration or {}), **config}
            existing.save(update_fields=["title", "description", "category", "configuration", "updated_at"])
            return existing
        return KnowledgeDocument.objects.create(
            owner=user,
            name=(f"{source_type}:{source_id}" if source_id else (title or content[:80]))[:255],
            title=title or content[:120],
            description=content,
            status="active",
            category=category,
            configuration=config,
        )

    @classmethod
    def retrieve_topic(cls, user, topic: str, *, limit: int = 12) -> dict[str, Any]:
        hits = cls.search(user, topic, limit=limit)
        return {"topic": topic, "results": hits, "count": len(hits)}


class KnowledgeService(DomainService):
    model = KnowledgeDocument


class SearchService(DomainService):
    model = KnowledgeDocument


class IndexingService(DomainService):
    model = ContentBlock


class ImportService(DomainService):
    model = KnowledgeDocument


class ExportService(DomainService):
    model = KnowledgeDocument


class VersionService(DomainService):
    model = KnowledgeVersion


class AnalyticsService(DomainService):
    model = KnowledgeDocument


class PermissionService(DomainService):
    model = KnowledgePermission
