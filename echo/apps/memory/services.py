from __future__ import annotations

import math
import re
from datetime import datetime
from typing import Any

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from echo.common.services import DomainService

from .models import (
    Memory,
    MemoryAccessLog,
    MemoryFeedback,
    MemoryRelationship,
    MemoryRule,
    MemorySnapshot,
)


class MemoryAgentService:
    """Central owner-scoped memory service used by all Echo agents.

    Memory is intentionally reserved for user/project preferences, decisions and
    durable personal context. External factual material belongs in Knowledge.
    """

    STOP_WORDS = {
        "that", "this", "with", "from", "have", "what", "when", "where", "which", "your", "about",
        "remember", "memory", "echo", "please", "would", "could", "should", "project",
    }

    @staticmethod
    def _owned(user):
        query = Memory.objects.all()
        return query if user.is_staff else query.filter(owner=user)

    @staticmethod
    def _normalize(text: str) -> str:
        return re.sub(r"\s+", " ", str(text or "").strip()).casefold()

    @classmethod
    def classify(cls, content: str) -> str:
        lowered = cls._normalize(content)
        if any(token in lowered for token in ("prefer", "like", "dislike", "favorite", "favourite")):
            return "preference"
        if any(token in lowered for token in ("decided", "decision", "we will", "i will", "use ", "named", "called")):
            return "decision"
        if any(token in lowered for token in ("project", "working on", "ongoing", "current")):
            return "project_context"
        return "personal_context"

    @classmethod
    def _terms(cls, query: str) -> list[str]:
        return [
            token for token in dict.fromkeys(re.findall(r"[a-zA-Z0-9_-]{2,}", str(query or "").casefold()))
            if token not in cls.STOP_WORDS
        ][:16]

    @classmethod
    def retrieve(cls, user, query: str, *, limit: int = 8, reason: str = "agent_context", conversation_id: str = "") -> list[dict[str, Any]]:
        terms = cls._terms(query)
        queryset = cls._owned(user).filter(status="active")
        if terms:
            condition = Q()
            for term in terms:
                condition |= Q(content__icontains=term) | Q(summary__icontains=term) | Q(title__icontains=term) | Q(name__icontains=term)
            candidates = list(queryset.filter(condition).order_by("-importance_score", "-updated_at")[: max(limit * 4, 30)])
        else:
            candidates = list(queryset.order_by("-importance_score", "-updated_at")[:limit])

        scored: list[tuple[float, Memory]] = []
        for memory in candidates:
            haystack = " ".join((memory.title, memory.summary, memory.content, memory.description)).casefold()
            coverage = sum(1 for term in terms if term in haystack)
            exact = 1.0 if query and cls._normalize(query) in haystack else 0.0
            score = coverage * 2.0 + exact * 3.0 + float(memory.importance_score or 0) + float(memory.confidence_score or 0) * 0.25
            scored.append((score, memory))
        rows = [item for _, item in sorted(scored, key=lambda pair: (-pair[0], -pair[1].updated_at.timestamp()))[:limit]]
        now = timezone.now()
        for rank, memory in enumerate(rows, 1):
            MemoryAccessLog.objects.create(
                owner=user,
                memory=memory,
                user=user,
                name="memory_retrieval",
                title=f"Retrieved {memory.title or memory.name}",
                status="completed",
                conversation=str(conversation_id or "")[:255],
                reason=reason,
                retrieval_score=max(0, 1 - (rank - 1) * 0.08),
                accessed_at=now,
            )
            memory.access_count = int(memory.access_count or 0) + 1
            memory.last_accessed = now.isoformat()
            memory.save(update_fields=["access_count", "last_accessed", "updated_at"])
        return [cls.serialize(item) for item in rows]

    @classmethod
    @transaction.atomic
    def remember(
        cls,
        user,
        content: str,
        *,
        summary: str = "",
        category: str = "",
        memory_type: str = "",
        source_type: str = "agent",
        source_id: str = "",
        importance: float = 0.6,
        confidence: float = 0.9,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[Memory, bool]:
        content = re.sub(r"\s+", " ", str(content or "").strip())
        if not content:
            raise ValueError("Memory content is required.")
        normalized = cls._normalize(content)
        for item in cls._owned(user).filter(status="active").order_by("-updated_at")[:200]:
            if cls._normalize(item.content) == normalized:
                item.confidence_score = max(float(item.confidence_score or 0), min(max(float(confidence), 0), 1))
                item.importance_score = max(float(item.importance_score or 0), min(max(float(importance), 0), 1))
                item.data = {**(item.data or {}), **(metadata or {}), "deduplicated_at": timezone.now().isoformat()}
                item.save(update_fields=["confidence_score", "importance_score", "data", "updated_at"])
                return item, False
        memory = Memory.objects.create(
            owner=user,
            user=user,
            name=(summary or content)[:255],
            title=(summary or content)[:160],
            description="Durable Echo memory.",
            status="active",
            content=content,
            summary=(summary or content)[:500],
            memory_type=memory_type or cls.classify(content),
            category=category or cls.classify(content),
            importance_score=min(max(float(importance), 0), 1),
            confidence_score=min(max(float(confidence), 0), 1),
            created_from=str(source_id or "")[:255],
            source_type=str(source_type or "agent")[:255],
            data=metadata or {},
        )
        MemorySnapshot.objects.create(
            owner=user,
            memory=memory,
            name="version-1",
            title="Initial memory snapshot",
            status="completed",
            version=1,
            content=content,
        )
        return memory, True

    @classmethod
    @transaction.atomic
    def update(cls, user, memory_id, *, content: str, summary: str = "") -> Memory:
        memory = cls._owned(user).select_for_update().filter(pk=memory_id).first()
        if not memory:
            raise ValueError("Memory was not found.")
        previous = memory.content
        version = MemorySnapshot.objects.filter(memory=memory).count() + 1
        MemorySnapshot.objects.create(
            owner=user,
            memory=memory,
            name=f"version-{version}",
            title=f"Memory snapshot {version}",
            status="completed",
            version=version,
            content=previous,
        )
        memory.content = re.sub(r"\s+", " ", str(content or "").strip())
        if summary:
            memory.summary = summary[:500]
            memory.title = summary[:255]
        memory.data = {**(memory.data or {}), "corrected_at": timezone.now().isoformat()}
        memory.save(update_fields=["content", "summary", "title", "data", "updated_at"])
        return memory

    @classmethod
    @transaction.atomic
    def delete(cls, user, memory_id) -> None:
        memory = cls._owned(user).select_for_update().filter(pk=memory_id).first()
        if not memory:
            raise ValueError("Memory was not found.")
        memory.delete()

    @classmethod
    def deduplicate(cls, user) -> dict[str, int]:
        seen: dict[str, Memory] = {}
        removed = 0
        for memory in cls._owned(user).filter(status="active").order_by("-importance_score", "-updated_at"):
            key = cls._normalize(memory.content)
            if not key:
                continue
            if key in seen:
                memory.delete()
                removed += 1
            else:
                seen[key] = memory
        return {"kept": len(seen), "removed": removed}

    @classmethod
    def prune_expired(cls, user) -> int:
        now = timezone.now()
        removed = 0
        for memory in cls._owned(user).filter(status="active"):
            expires = (memory.data or {}).get("expires_at")
            if not expires:
                continue
            try:
                value = datetime.fromisoformat(str(expires).replace("Z", "+00:00"))
                if timezone.is_naive(value):
                    value = timezone.make_aware(value, timezone.get_current_timezone())
            except ValueError:
                continue
            if value <= now:
                memory.status = "expired"
                memory.save(update_fields=["status", "updated_at"])
                removed += 1
        return removed

    @staticmethod
    def serialize(memory: Memory) -> dict[str, Any]:
        return {
            "id": str(memory.pk),
            "title": memory.title or memory.name,
            "content": memory.content,
            "summary": memory.summary,
            "memory_type": memory.memory_type,
            "category": memory.category,
            "importance": float(memory.importance_score or 0),
            "confidence": float(memory.confidence_score or 0),
            "source_type": memory.source_type,
            "updated_at": memory.updated_at.isoformat(),
        }


class MemoryService(DomainService):
    model = Memory


class ExtractionService(DomainService):
    model = Memory


class ConsolidationService(DomainService):
    model = MemorySnapshot


class RetrievalService(DomainService):
    model = Memory


class RankingService(DomainService):
    model = Memory


class ScoringService(DomainService):
    model = MemoryFeedback


class ExpirationService(DomainService):
    model = MemoryRule


class RelationshipService(DomainService):
    model = MemoryRelationship


class SynchronizationService(DomainService):
    model = MemorySnapshot
