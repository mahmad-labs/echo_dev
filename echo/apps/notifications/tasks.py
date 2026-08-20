from echo.common.health_checks import app_database_health

from celery import shared_task

from .dispatcher import NotificationDispatcher
from .models import Notification


@shared_task(bind=True, autoretry_for=(RuntimeError,), retry_backoff=True, max_retries=5)
def deliver_notification(self, notification_id: str, channel: str = "database"):
    notification = Notification.objects.get(pk=notification_id)
    result = NotificationDispatcher.deliver(notification, channel)
    return result.__dict__


@shared_task
def health_task():
    return app_database_health("notifications")
