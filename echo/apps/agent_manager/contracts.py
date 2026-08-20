from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AgentContext:
    """Permission-scoped context shared between Echo agents.

    The orchestrator builds one authoritative context and each agent receives only
    the scopes declared in its registry definition. This prevents accidental
    cross-domain exposure while still allowing structured handoffs.
    """

    user_id: str
    conversation_id: str = ""
    voice_session_id: str = ""
    task_id: str = ""
    project_id: str = ""
    project_context: dict[str, Any] = field(default_factory=dict)
    browser_session_id: str = ""
    computer_session_id: str = ""
    current_page: dict[str, Any] = field(default_factory=dict)
    recent_observations: list[dict[str, Any]] = field(default_factory=list)
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    relevant_memories: list[dict[str, Any]] = field(default_factory=list)
    relevant_knowledge: list[dict[str, Any]] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)
    approvals: list[dict[str, Any]] = field(default_factory=list)
    execution_state: dict[str, Any] = field(default_factory=dict)
    variables: dict[str, Any] = field(default_factory=dict)

    def scoped(self, scopes: tuple[str, ...] | list[str]) -> dict[str, Any]:
        allowed = set(scopes)
        base = {"user_id": self.user_id}
        mapping = {
            "conversation": ("conversation_id", self.conversation_id),
            "voice": ("voice_session_id", self.voice_session_id),
            "task": ("task_id", self.task_id),
            "project": ("project_id", self.project_id),
            "browser": ("browser_session_id", self.browser_session_id),
            "computer": ("computer_session_id", self.computer_session_id),
            "page": ("current_page", self.current_page),
            "observations": ("recent_observations", self.recent_observations),
            "tool_results": ("tool_results", self.tool_results),
            "memory": ("relevant_memories", self.relevant_memories),
            "knowledge": ("relevant_knowledge", self.relevant_knowledge),
            "permissions": ("permissions", self.permissions),
            "approvals": ("approvals", self.approvals),
            "execution": ("execution_state", self.execution_state),
            "variables": ("variables", self.variables),
        }
        for scope, (key, value) in mapping.items():
            if scope in allowed:
                base[key] = value
        if "project" in allowed:
            base["project_context"] = self.project_context
        return base


@dataclass(frozen=True)
class AgentResult:
    status: str
    result: dict[str, Any] = field(default_factory=dict)
    errors: list[dict[str, Any]] = field(default_factory=list)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    next_actions: list[dict[str, Any]] = field(default_factory=list)
    confidence: float | None = None

    def as_dict(self) -> dict[str, Any]:
        payload = {
            "status": self.status,
            "result": self.result,
            "errors": self.errors,
            "artifacts": self.artifacts,
            "metadata": self.metadata,
            "next_actions": self.next_actions,
        }
        if self.confidence is not None:
            payload["confidence"] = max(0.0, min(float(self.confidence), 1.0))
        return payload
