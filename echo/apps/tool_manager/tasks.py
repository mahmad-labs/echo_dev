from celery import shared_task
from django.contrib.auth import get_user_model

from .execution import ToolExecutor
from .models import Tool


@shared_task(bind=True, autoretry_for=(RuntimeError,), retry_backoff=True, max_retries=3)
def execute_tool(self, tool_id: str, user_id: str, payload: dict | None = None):
    user = get_user_model().objects.get(pk=user_id)
    tool = Tool.objects.get(pk=tool_id, owner=user)
    result = ToolExecutor.execute(tool, user, payload or {})
    return result.as_dict()


@shared_task
def health_task():
    report = ToolExecutor.validation_report()
    return {"status": "healthy" if report["ok"] else "failed", "component": "tool_manager", "count": report["count"], "issues": report["issues"]}
