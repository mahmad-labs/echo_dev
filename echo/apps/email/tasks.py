from echo.common.health_checks import app_database_health

from celery import shared_task

from .imap_sync import IMAPSyncService
from .models import EmailAccount


@shared_task(bind=True, autoretry_for=(RuntimeError,), retry_backoff=True, max_retries=3)
def sync_email_account(self, account_id: str, limit: int = 50):
    account = EmailAccount.objects.get(pk=account_id)
    return IMAPSyncService.sync(account, limit)


@shared_task
def health_task():
    return app_database_health("email")
