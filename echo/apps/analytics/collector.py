from __future__ import annotations

from collections import Counter
from datetime import timedelta
from typing import Any

from django.db import transaction
from django.utils import timezone

from .models import AnalyticsEvent, MetricDefinition, MetricPoint, UsageAggregate


class AnalyticsCollector:
    """Store structured events and derive repeatable usage aggregates."""

    @staticmethod
    def record(user, event_name: str, properties: dict[str, Any] | None = None) -> AnalyticsEvent:
        name = event_name.strip()
        if not name:
            raise ValueError("event_name is required")
        return AnalyticsEvent.objects.create(
            owner=user,
            name=name,
            title=name.replace("_", " ").title(),
            status="recorded",
            category=(properties or {}).get("category", "application"),
            configuration={"properties": properties or {}, "recorded_at": timezone.now().isoformat()},
        )

    @classmethod
    @transaction.atomic
    def aggregate(cls, user, days: int = 30) -> UsageAggregate:
        if not 1 <= days <= 366:
            raise ValueError("days must be between 1 and 366")
        since = timezone.now() - timedelta(days=days)
        events = AnalyticsEvent.objects.filter(owner=user, created_at__gte=since)
        counts = Counter(events.values_list("name", flat=True))
        definition, _ = MetricDefinition.objects.get_or_create(
            owner=user,
            name="event_count",
            defaults={
                "title": "Event Count",
                "status": "active",
                "category": "usage",
                "configuration": {"unit": "count", "aggregation": "sum"},
            },
        )
        for event_name, value in counts.items():
            MetricPoint.objects.create(
                owner=user,
                name=event_name,
                title=f"{event_name} count",
                status="computed",
                category="usage",
                configuration={
                    "metric_definition_id": str(definition.pk),
                    "value": value,
                    "window_days": days,
                    "computed_at": timezone.now().isoformat(),
                },
            )
        return UsageAggregate.objects.create(
            owner=user,
            name="usage_summary",
            title=f"Usage summary ({days} days)",
            status="completed",
            category="usage",
            configuration={
                "window_days": days,
                "event_total": sum(counts.values()),
                "by_event": dict(counts),
                "computed_at": timezone.now().isoformat(),
            },
        )
