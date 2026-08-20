from __future__ import annotations

import re
from dataclasses import dataclass

from django.db.models import Q

from .models import ContentBlock, DocumentSection, KnowledgeDocument


@dataclass(frozen=True)
class SearchHit:
    model: str
    identifier: str
    title: str
    score: int
    excerpt: str


class KnowledgeSearchService:
    """Rank owner-scoped knowledge records using deterministic term coverage."""

    MODELS = (KnowledgeDocument, DocumentSection, ContentBlock)

    @staticmethod
    def _terms(query: str) -> tuple[str, ...]:
        return tuple(dict.fromkeys(re.findall(r"[\w-]{2,}", query.lower())))

    @classmethod
    def search(cls, user, query: str, limit: int = 25) -> list[SearchHit]:
        terms = cls._terms(query)
        if not terms:
            return []
        hits: list[SearchHit] = []
        for model in cls.MODELS:
            condition = Q()
            for term in terms:
                condition |= Q(title__icontains=term) | Q(description__icontains=term) | Q(name__icontains=term)
            for item in model.objects.filter(owner=user).filter(condition)[: max(limit * 2, 50)]:
                haystack = " ".join((item.title, item.name, item.description)).lower()
                score = sum(3 if term in item.title.lower() else 1 for term in terms if term in haystack)
                excerpt = item.description[:300]
                hits.append(SearchHit(model._meta.label_lower, str(item.pk), item.title or item.name, score, excerpt))
        return sorted(hits, key=lambda hit: (-hit.score, hit.title.lower()))[:limit]
