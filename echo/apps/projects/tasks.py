from echo.common.health_checks import app_database_health

from celery import shared_task
from django.contrib.auth import get_user_model

from .portability import ProjectPortabilityService


@shared_task
def export_projects(user_id: str):
    user = get_user_model().objects.get(pk=user_id)
    return ProjectPortabilityService.export(user)


@shared_task
def health_task():
    return app_database_health("projects")
