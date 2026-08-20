from echo.common.health_checks import app_database_health

from celery import shared_task

@shared_task
def health_task():
    return app_database_health("settings")
