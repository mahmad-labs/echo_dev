from __future__ import annotations

from datetime import datetime

from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import Event, TimeBlock


def _parse_datetime(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError({field: "Use an ISO-8601 date-time."}) from exc
    return timezone.make_aware(parsed) if timezone.is_naive(parsed) else parsed


class SchedulingService:
    """Validate event windows and detect owner-scoped scheduling conflicts."""

    @classmethod
    def conflicts(cls, user, start: datetime, end: datetime, exclude_event=None):
        if end <= start:
            raise ValidationError({"end": "End time must be after start time."})
        candidates = Event.objects.filter(owner=user).exclude(status__in=("cancelled", "deleted"))
        if exclude_event:
            candidates = candidates.exclude(pk=exclude_event.pk)
        conflicts = []
        for event in candidates.only("id", "title", "configuration"):
            config = event.configuration or {}
            if not config.get("start") or not config.get("end"):
                continue
            event_start = _parse_datetime(config["start"], "start")
            event_end = _parse_datetime(config["end"], "end")
            if event_start < end and event_end > start:
                conflicts.append(event)
        for block in TimeBlock.objects.filter(owner=user, status="active"):
            config = block.configuration or {}
            if not config.get("start") or not config.get("end"):
                continue
            block_start = _parse_datetime(config["start"], "start")
            block_end = _parse_datetime(config["end"], "end")
            if block_start < end and block_end > start:
                conflicts.append(block)
        return conflicts

    @classmethod
    def create_event(cls, user, payload: dict) -> Event:
        start = _parse_datetime(payload.get("start"), "start")
        end = _parse_datetime(payload.get("end"), "end")
        conflicts = cls.conflicts(user, start, end)
        if conflicts and not payload.get("allow_conflicts", False):
            raise ValidationError(
                {"conflicts": [str(item.pk) for item in conflicts]}
            )
        return Event.objects.create(
            owner=user,
            name=str(payload.get("name", "event")),
            title=str(payload.get("title", "Scheduled event")),
            description=str(payload.get("description", "")),
            status="scheduled",
            category=str(payload.get("category", "calendar")),
            configuration={
                **payload,
                "start": start.isoformat(),
                "end": end.isoformat(),
            },
        )
