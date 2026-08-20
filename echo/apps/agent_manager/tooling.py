from __future__ import annotations

from typing import Any

from echo.apps.tool_manager.execution import ToolContext, ToolExecutor


def _agent_execute(payload: dict[str, Any], context: ToolContext) -> dict[str, Any]:
    """Delegate a workflow/tool step through the central Agent Manager."""
    prompt = str(payload.get("prompt") or payload.get("objective") or "").strip()
    if not prompt:
        raise ValueError("prompt is required")
    if len(prompt) > 20_000:
        raise ValueError("prompt is too long")
    conversation_id = str(payload.get("conversation_id") or "").strip() or None
    source = str(payload.get("source") or "workflow").strip()[:32] or "workflow"
    section = str(payload.get("section") or "workflow").strip()[:64] or "workflow"
    from .orchestration import AgentManagerOrchestrator
    result = AgentManagerOrchestrator(context.user, source=source, section=section).execute(prompt, conversation_id=conversation_id)
    return {
        "status": result.status,
        "route": result.route,
        "content": result.content,
        "conversation_id": str(result.conversation.pk) if result.conversation else None,
        "agent_task_id": (result.data or {}).get("parent_agent_task_id") or (result.data or {}).get("agent_task_id"),
        "data": result.data or {},
    }


def register_agent_tools() -> None:
    ToolExecutor.register(
        "agent.execute",
        _agent_execute,
        description="Delegate an objective to Echo's central Agent Manager and return its structured result.",
        category="orchestration",
        input_schema={
            "type": "object",
            "required": ["prompt"],
            "properties": {
                "prompt": {"type": "string", "minLength": 1, "maxLength": 20000},
                "conversation_id": {"type": "string"},
                "source": {"type": "string"},
                "section": {"type": "string"},
            },
            "additionalProperties": False,
        },
        output_schema={"type": "object"},
        permissions=("tools.execute",),
        result_format="json",
        execution_mode="orchestrated",
        timeout=900,
        risk_level="medium",
        cancellable=True,
        agent_access=("workflow", "planner", "chat", "voice"),
    )
