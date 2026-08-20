from __future__ import annotations

from django.core.exceptions import PermissionDenied
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from echo.apps.tool_manager.execution import ToolExecutionError, ToolExecutor
from echo.common.viewsets import SecuredModelViewSet

from .models import AgentCommunication, AgentTask
from .orchestration import AgentManagerOrchestrator, AgentMessageBus
from .registry import AgentRegistry


def _owned(model, user):
    query = model.objects.all()
    return query if user.is_staff else query.filter(owner=user)


def _task_payload(task: AgentTask, *, include_children: bool = True) -> dict:
    payload = {
        "id": str(task.pk),
        "parent_task_id": str(task.parent_task_id) if task.parent_task_id else None,
        "agent": task.agent.identifier if task.agent else "manager",
        "agent_name": task.agent.title if task.agent else "Agent Manager",
        "status": task.status,
        "priority": task.priority,
        "request": task.request_text,
        "current_operation": task.current_operation,
        "current_tool": task.current_tool,
        "progress": int(task.progress or 0),
        "cancellable": task.cancellable,
        "cancel_requested": task.cancel_requested,
        "result": task.output_payload,
        "error": task.error_message or None,
        "correlation_id": str(task.correlation_id),
        "created_at": task.created_at,
        "started_at": task.started_at,
        "completed_at": task.completed_at,
    }
    if include_children:
        payload["children"] = [_task_payload(child, include_children=False) for child in task.child_tasks.select_related("agent").order_by("created_at")]
    return payload


class AgentRegistryView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        records = {item.identifier: item for item in AgentRegistry.materialize_all(request.user)}
        agents = []
        for definition in AgentRegistry.definitions():
            record = records[definition.identifier]
            item = definition.public()
            item.update({
                "id": str(record.pk), "health_status": record.health_status,
                "last_health_check": record.last_health_check, "available": bool(record.available),
            })
            agents.append(item)
        return Response({"agents": agents})


class AgentTaskListView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        query = _owned(AgentTask, request.user).select_related("agent", "parent_task").filter(parent_task__isnull=True)
        state = str(request.query_params.get("status") or "").strip()
        if state:
            query = query.filter(status=state)
        active = str(request.query_params.get("active") or "").lower()
        if active in {"1", "true", "yes"}:
            query = query.filter(status__in=("queued", "running", "waiting", "cancelling"))
        return Response({"tasks": [_task_payload(item) for item in query.order_by("-updated_at")[:50]]})


class AgentTaskDetailView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, pk):
        task = _owned(AgentTask, request.user).select_related("agent", "parent_task").filter(pk=pk).first()
        if not task:
            return Response({"detail": "Agent task was not found."}, status=status.HTTP_404_NOT_FOUND)
        root = task.parent_task or task
        communications = _owned(AgentCommunication, request.user).filter(task__in=[root, *list(root.child_tasks.all())]).select_related("sender_agent", "recipient_agent").order_by("created_at")[:200]
        return Response({
            "task": _task_payload(root),
            "communications": [{
                "id": str(item.pk), "task_id": str(item.task_id) if item.task_id else None,
                "type": item.message_type,
                "sender": item.sender_agent.identifier if item.sender_agent else "manager",
                "recipient": item.recipient_agent.identifier if item.recipient_agent else "manager",
                "payload": item.payload, "created_at": item.created_at,
            } for item in communications],
        })


class AgentTaskCancelView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, pk):
        task = _owned(AgentTask, request.user).filter(pk=pk).first()
        if not task:
            return Response({"detail": "Agent task was not found."}, status=status.HTTP_404_NOT_FOUND)
        root = task.parent_task or task
        if root.status in {"completed", "failed", "cancelled"}:
            return Response({"task": _task_payload(root)})
        targets = [root, *list(root.child_tasks.filter(status__in=("queued", "running", "waiting", "cancelling")))]
        for item in targets:
            item.cancel_requested = True
            item.current_operation = "Cancellation requested"
            if item.status in {"queued", "waiting"}:
                item.status = "cancelled"
                item.completed_at = timezone.now()
            item.save(update_fields=["cancel_requested", "current_operation", "status", "completed_at", "updated_at"])
            data = (item.output_payload or {}).get("result", {}).get("data", {})
            operation_id = data.get("operation_id")
            if operation_id:
                try:
                    from echo.apps.internet.computer_use import ComputerUseOperationService
                    ComputerUseOperationService.cancel(request.user, operation_id)
                except Exception:
                    pass
        return Response({"task": _task_payload(root)})


class AgentTaskApproveView(APIView):
    """Approve one explicitly waiting action; never grants blanket future approval."""

    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, pk):
        task = _owned(AgentTask, request.user).select_related("agent", "parent_task").filter(pk=pk).first()
        if not task:
            return Response({"detail": "Agent task was not found."}, status=status.HTTP_404_NOT_FOUND)
        if task.parent_task_id is None:
            task = task.child_tasks.filter(status="waiting").select_related("agent").order_by("-updated_at").first() or task
        if task.status != "waiting":
            raise ValidationError({"task": "Only a waiting agent task can be approved."})
        data = (task.output_payload or {}).get("result", {}).get("data", {})
        pending = data.get("pending_action") if isinstance(data, dict) else None
        operation_id = data.get("operation_id") if isinstance(data, dict) else None
        try:
            if isinstance(pending, dict) and pending.get("tool"):
                tool_name = str(pending["tool"]).strip().lower()
                # Desktop approvals are deliberately one-action grants. Never allow a
                # task payload to turn this endpoint into a generic tool-confirmation
                # bypass for unrelated or future actions.
                if not tool_name.startswith("computer."):
                    raise ValidationError({"task": "Only a pending Computer Control action can be approved here."})
                definition = ToolExecutor.definition(tool_name)
                if definition.confirmation != "required":
                    raise ValidationError({"task": "This Computer Control action does not require approval."})
                payload = dict(pending.get("input") or {})
                payload["confirmed"] = True
                execution = ToolExecutor.execute_named(tool_name, request.user, payload, agent="computer", task_id=str(task.pk), correlation_id=str(task.correlation_id or ""))
                task.output_payload = {
                    "status": "completed",
                    "result": {"content": "The approved action completed and was verified.", "route": f"{tool_name}.approved", "data": {"execution_id": execution.execution_id, "output": execution.output}},
                    "errors": [], "artifacts": [], "metadata": {"approved_at": timezone.now().isoformat()}, "next_actions": [],
                }
                task.status = "completed"
                task.progress = 100
                task.current_operation = "Approved action completed"
                task.completed_at = timezone.now()
                task.save(update_fields=["output_payload", "status", "progress", "current_operation", "completed_at", "updated_at"])
                AgentMessageBus.send(user=request.user, task=task, sender=None, recipient=task.agent, message_type="approval", payload={"tool": tool_name, "execution_id": execution.execution_id, "approved": True})
            elif operation_id:
                from echo.apps.internet.computer_use import ComputerUseOperationService
                operation, queue_id = ComputerUseOperationService.resume(request.user, operation_id)
                task.status = "running"
                task.current_operation = "Approved browser operation resumed"
                task.current_tool = operation.current_tool
                task.save(update_fields=["status", "current_operation", "current_tool", "updated_at"])
                AgentMessageBus.send(user=request.user, task=task, sender=None, recipient=task.agent, message_type="approval", payload={"operation_id": operation_id, "queue_task_id": queue_id, "approved": True})
            else:
                raise ValidationError({"task": "This waiting task has no approvable action."})
        except (ToolExecutionError, PermissionDenied) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        root = task.parent_task or task
        if task.status == "completed" and root.pk != task.pk:
            root.status = "completed"
            root.progress = 100
            root.current_operation = "Completed"
            root.completed_at = timezone.now()
            root.output_payload = task.output_payload
            root.save(update_fields=["status", "progress", "current_operation", "completed_at", "output_payload", "updated_at"])
        return Response({"task": _task_payload(root)}, status=status.HTTP_202_ACCEPTED if task.status == "running" else status.HTTP_200_OK)


__all__ = (
    "SecuredModelViewSet", "AgentRegistryView", "AgentTaskListView", "AgentTaskDetailView",
    "AgentTaskCancelView", "AgentTaskApproveView",
)
