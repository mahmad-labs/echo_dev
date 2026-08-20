from echo.common.health_checks import app_database_health

from celery import shared_task
from django.contrib.auth import get_user_model

from .executor import WorkflowExecutor
from .models import Workflow, WorkflowExecution


@shared_task(bind=True, autoretry_for=(RuntimeError,), retry_backoff=True, max_retries=3)
def execute_workflow(
    self,
    workflow_id: str,
    user_id: str,
    inputs: dict | None = None,
    execution_id: str | None = None,
):
    user = get_user_model().objects.get(pk=user_id)
    workflow = Workflow.objects.get(pk=workflow_id, owner=user)
    execution = None
    if execution_id:
        execution = WorkflowExecution.objects.get(pk=execution_id, owner=user)
    execution = WorkflowExecutor.execute(workflow, user, inputs or {}, execution=execution)
    return {"execution_id": str(execution.pk), "status": execution.status}


@shared_task
def health_task():
    return app_database_health("workflow_engine")
