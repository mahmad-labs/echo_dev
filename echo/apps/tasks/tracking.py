from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import Task, TaskActivity, TimeEntry


class TimeTrackingService:
    @staticmethod
    @transaction.atomic
    def start(task: Task, user) -> TimeEntry:
        active = TimeEntry.objects.filter(
            owner=user,
            status="running",
            configuration__task_id=str(task.pk),
        ).first()
        if active:
            return active
        entry = TimeEntry.objects.create(
            owner=user,
            name=f"timer-{task.pk}",
            title=f"Timer: {task.title or task.name}",
            status="running",
            category="time",
            configuration={"task_id": str(task.pk), "started_at": timezone.now().isoformat()},
        )
        TaskActivity.objects.create(
            owner=user,
            name="timer_started",
            title=f"Timer started for {task.title or task.name}",
            status="recorded",
            category="time",
            configuration={"task_id": str(task.pk), "time_entry_id": str(entry.pk)},
        )
        return entry

    @staticmethod
    @transaction.atomic
    def stop(entry: TimeEntry, user) -> TimeEntry:
        if entry.owner_id != user.pk:
            raise ValidationError("The time entry does not belong to this user.")
        if entry.status != "running":
            raise ValidationError("The time entry is not running.")
        started_at = (entry.configuration or {}).get("started_at")
        if not started_at:
            raise ValidationError("The time entry has no start timestamp.")
        started = datetime.fromisoformat(started_at)
        if timezone.is_naive(started):
            started = timezone.make_aware(started)
        finished = timezone.now()
        seconds = max(0, Decimal(str((finished - started).total_seconds())))
        entry.status = "completed"
        entry.configuration = {
            **entry.configuration,
            "finished_at": finished.isoformat(),
            "duration_seconds": str(seconds.quantize(Decimal("0.001"))),
        }
        entry.save(update_fields=["status", "configuration", "updated_at"])
        return entry
