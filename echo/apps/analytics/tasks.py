from echo.common.health_checks import app_database_health

from celery import shared_task
from django.contrib.auth import get_user_model

from .collector import AnalyticsCollector


@shared_task
def aggregate_usage(user_id: str, days: int = 30):
    user = get_user_model().objects.get(pk=user_id)
    aggregate = AnalyticsCollector.aggregate(user, days)
    return {"aggregate_id": str(aggregate.pk), "status": aggregate.status}


@shared_task
def health_task():
    return app_database_health("analytics")
