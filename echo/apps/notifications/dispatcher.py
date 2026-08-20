from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from .models import DeliveryLog, Notification, NotificationPreference


@dataclass(frozen=True)
class DeliveryResult:
    notification_id: str
    channel: str
    status: str


class NotificationDispatcher:
    """Deliver notifications through configured channels and persist delivery evidence."""

    @staticmethod
    def _preference_allows(notification: Notification, channel: str) -> bool:
        preference = NotificationPreference.objects.filter(
            owner=notification.owner,
            category=channel,
            status="active",
        ).first()
        return preference is None or bool((preference.configuration or {}).get("enabled", True))

    @classmethod
    @transaction.atomic
    def deliver(cls, notification: Notification, channel: str = "database") -> DeliveryResult:
        channel = channel.strip().lower()
        if not cls._preference_allows(notification, channel):
            status_value = "suppressed"
            details: dict[str, Any] = {"reason": "user_preference"}
        else:
            status_value = "delivered"
            details = {"delivered_at": timezone.now().isoformat()}
            if channel == "database":
                notification.status = "delivered"
                notification.save(update_fields=["status", "updated_at"])
            elif channel == "email":
                recipient = (notification.configuration or {}).get("recipient")
                if not recipient and notification.owner:
                    recipient = notification.owner.email
                if not recipient:
                    raise ValueError("An email recipient is required.")
                sent = send_mail(
                    notification.title or "Echo notification",
                    notification.description,
                    None,
                    [recipient],
                    fail_silently=False,
                )
                if sent != 1:
                    raise RuntimeError("Email backend did not confirm delivery.")
                details["recipient"] = recipient
                notification.status = "delivered"
                notification.save(update_fields=["status", "updated_at"])
            else:
                raise ValueError(f"Unsupported notification channel: {channel}")

        DeliveryLog.objects.create(
            owner=notification.owner,
            name=channel,
            title=f"Delivery for {notification.pk}",
            status=status_value,
            category=channel,
            configuration={"notification_id": str(notification.pk), **details},
        )
        return DeliveryResult(str(notification.pk), channel, status_value)
