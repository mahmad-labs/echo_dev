from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

from django.core.exceptions import ValidationError
from django.utils import timezone

from echo.apps.tool_manager.execution import ToolExecutor
from echo.apps.tool_manager.models import Tool

from .models import Checkpoint, ExecutionEvent, Workflow, WorkflowExecution


class WorkflowExecutor:
    """Run an acyclic workflow definition and persist every state transition."""

    @staticmethod
    def _ordered_steps(definition: dict[str, Any]) -> list[dict[str, Any]]:
        steps = definition.get("steps", [])
        if not isinstance(steps, list) or not steps:
            raise ValidationError({"steps": "At least one workflow step is required."})
        by_id: dict[str, dict[str, Any]] = {}
        incoming: dict[str, int] = {}
        outgoing: dict[str, list[str]] = defaultdict(list)
        for index, step in enumerate(steps):
            if not isinstance(step, dict):
                raise ValidationError({"steps": f"Step {index} must be an object."})
            step_id = str(step.get("id") or f"step-{index + 1}")
            if step_id in by_id:
                raise ValidationError({"steps": f"Duplicate step id {step_id!r}."})
            normalized = {**step, "id": step_id}
            by_id[step_id] = normalized
            dependencies = [str(item) for item in step.get("depends_on", [])]
            incoming[step_id] = len(dependencies)
            for dependency in dependencies:
                outgoing[dependency].append(step_id)
        missing = sorted(set(outgoing) - set(by_id))
        if missing:
            raise ValidationError({"steps": f"Unknown dependencies: {', '.join(missing)}"})

        queue = deque(sorted(step_id for step_id, count in incoming.items() if count == 0))
        ordered: list[dict[str, Any]] = []
        while queue:
            step_id = queue.popleft()
            ordered.append(by_id[step_id])
            for child in sorted(outgoing[step_id]):
                incoming[child] -= 1
                if incoming[child] == 0:
                    queue.append(child)
        if len(ordered) != len(by_id):
            raise ValidationError({"steps": "Workflow dependencies contain a cycle."})
        return ordered

    @classmethod
    def execute(
        cls,
        workflow: Workflow,
        user,
        inputs: dict[str, Any] | None = None,
        *,
        execution: WorkflowExecution | None = None,
    ) -> WorkflowExecution:
        definition = workflow.configuration or {}
        ordered_steps = cls._ordered_steps(definition)
        if execution is None:
            execution = WorkflowExecution.objects.create(
                owner=user,
                name=workflow.name,
                title=f"Execution: {workflow.title or workflow.name or workflow.pk}",
                status="queued",
                category=workflow.category,
                configuration={"workflow_id": str(workflow.pk)},
            )
        elif execution.owner_id != user.pk or str((execution.configuration or {}).get("workflow_id")) != str(workflow.pk):
            raise ValidationError("The queued execution does not belong to this workflow and user.")

        execution.status = "running"
        execution.configuration = {
            **(execution.configuration or {}),
            "workflow_id": str(workflow.pk),
            "inputs": inputs or {},
            "started_at": timezone.now().isoformat(),
            "results": {},
        }
        execution.save(update_fields=["status", "configuration", "updated_at"])
        context: dict[str, Any] = {"inputs": inputs or {}, "results": {}}
        try:
            for position, step in enumerate(ordered_steps, start=1):
                step_id = step["id"]
                ExecutionEvent.objects.create(
                    owner=user,
                    name=step_id,
                    title=f"Starting {step_id}",
                    status="running",
                    category="workflow.step",
                    configuration={"execution_id": str(execution.pk), "position": position},
                )
                tool_id = step.get("tool_id")
                if not tool_id:
                    raise ValidationError({"steps": f"Step {step_id!r} has no tool_id."})
                tool = Tool.objects.filter(owner=user, pk=tool_id, status="active").first()
                if not tool:
                    raise ValidationError({"steps": f"Tool {tool_id!r} is unavailable."})
                payload = {**context["inputs"], **step.get("input", {}), "results": context["results"]}
                result = ToolExecutor.execute(tool, user, payload, agent="workflow", task_id=str(execution.pk), correlation_id=str(execution.pk))
                context["results"][step_id] = result.output
                Checkpoint.objects.create(
                    owner=user,
                    name=step_id,
                    title=f"Checkpoint {step_id}",
                    status="completed",
                    category="workflow.checkpoint",
                    configuration={
                        "execution_id": str(execution.pk),
                        "step_id": step_id,
                        "context": context,
                    },
                )
                ExecutionEvent.objects.create(
                    owner=user,
                    name=step_id,
                    title=f"Completed {step_id}",
                    status="completed",
                    category="workflow.step",
                    configuration={"execution_id": str(execution.pk), "position": position},
                )
        except Exception as exc:
            execution.status = "failed"
            execution.configuration = {
                **execution.configuration,
                "finished_at": timezone.now().isoformat(),
                "results": context["results"],
                "error": str(exc),
                "error_type": exc.__class__.__name__,
            }
            execution.save(update_fields=["status", "configuration", "updated_at"])
            raise

        execution.status = "completed"
        execution.configuration = {
            **execution.configuration,
            "finished_at": timezone.now().isoformat(),
            "results": context["results"],
        }
        execution.save(update_fields=["status", "configuration", "updated_at"])
        return execution
