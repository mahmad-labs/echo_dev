from echo.common.health_checks import app_database_health

from celery import shared_task


@shared_task(bind=True, autoretry_for=(), max_retries=0)
def run_computer_use_operation(self, operation_id: str):
    from .computer_use import ComputerUseOperationService
    operation = ComputerUseOperationService.run(operation_id)
    return {"operation_id": str(operation.pk), "status": operation.status, "progress": operation.progress}


@shared_task
def health_task():
    return app_database_health("internet")
