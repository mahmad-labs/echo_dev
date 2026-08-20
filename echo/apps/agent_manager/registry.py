from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any, Protocol

from django.utils import timezone

from .contracts import AgentContext, AgentResult
from .models import Agent


class AgentHandler(Protocol):
    def __call__(self, *, user: Any, prompt: str, context: AgentContext, task: Any, source: str, section: str) -> AgentResult: ...


@dataclass(frozen=True)
class AgentDefinition:
    identifier: str
    name: str
    description: str
    capabilities: tuple[str, ...]
    required_tools: tuple[str, ...] = ()
    required_permissions: tuple[str, ...] = ()
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    context_scopes: tuple[str, ...] = ()
    handler: AgentHandler | None = None
    version: str = "1"

    def runtime_status(self) -> tuple[bool, list[str]]:
        if self.handler is None:
            return False, []
        from echo.apps.tool_manager.execution import ToolExecutor
        unavailable = []
        for tool_name in self.required_tools:
            try:
                if not ToolExecutor.definition(tool_name).is_available():
                    unavailable.append(tool_name)
            except Exception:
                unavailable.append(tool_name)
        return not unavailable, unavailable

    def public(self) -> dict[str, Any]:
        runtime_available, unavailable_tools = self.runtime_status()
        return {
            "identifier": self.identifier,
            "name": self.name,
            "description": self.description,
            "capabilities": list(self.capabilities),
            "required_tools": list(self.required_tools),
            "required_permissions": list(self.required_permissions),
            "input_schema": self.input_schema or {"type": "object"},
            "output_schema": self.output_schema or {"type": "object"},
            "context_scopes": list(self.context_scopes),
            "version": self.version,
            "available": runtime_available,
            "unavailable_tools": unavailable_tools,
        }


class AgentRegistry:
    _definitions: dict[str, AgentDefinition] = {}
    _duplicates: list[dict[str, str]] = []
    _loaded = False
    _loading = False
    _lock = threading.RLock()

    @classmethod
    def ensure_loaded(cls) -> None:
        with cls._lock:
            if cls._loaded or cls._loading:
                return
            cls._loading = True
            try:
                from . import orchestration  # noqa: F401
                cls._loaded = True
            finally:
                cls._loading = False

    @classmethod
    def register(cls, definition: AgentDefinition) -> None:
        key = definition.identifier.strip().lower()
        if not key:
            raise ValueError("Agent identifier is required.")
        previous = cls._definitions.get(key)
        if previous:
            if previous == definition:
                return
            cls._duplicates.append({"identifier": key, "existing": previous.name, "new": definition.name})
            raise ValueError(f"Duplicate Echo agent registration: {key}")
        cls._definitions[key] = definition

    @classmethod
    def get(cls, identifier: str) -> AgentDefinition:
        cls.ensure_loaded()
        key = str(identifier or "").strip().lower()
        if key not in cls._definitions:
            raise KeyError(f"Unknown Echo agent: {key}")
        return cls._definitions[key]

    @classmethod
    def definitions(cls) -> tuple[AgentDefinition, ...]:
        cls.ensure_loaded()
        return tuple(cls._definitions[key] for key in sorted(cls._definitions))

    @classmethod
    def validation_report(cls) -> dict[str, Any]:
        cls.ensure_loaded()
        from echo.apps.tool_manager.execution import ToolExecutor
        available_tools = set(ToolExecutor.available_handlers())
        issues: list[dict[str, Any]] = []
        warnings: list[dict[str, Any]] = []
        allowed_scopes = {"conversation", "project", "memory", "knowledge", "browser", "computer", "page", "observations", "permissions", "approvals", "execution", "variables"}
        for definition in cls.definitions():
            if definition.handler is None:
                issues.append({"type": "unreachable_agent", "agent": definition.identifier})
            missing = [tool for tool in definition.required_tools if tool not in available_tools]
            if missing:
                issues.append({"type": "missing_tool", "agent": definition.identifier, "tools": missing})
            unavailable = [tool for tool in definition.required_tools if tool in available_tools and not ToolExecutor.definition(tool).is_available()]
            if unavailable:
                warnings.append({"type": "tool_unavailable", "agent": definition.identifier, "tools": unavailable})
            invalid_scopes = [scope for scope in definition.context_scopes if scope not in allowed_scopes]
            if invalid_scopes:
                issues.append({"type": "invalid_context_scope", "agent": definition.identifier, "scopes": invalid_scopes})
        issues.extend({"type": "duplicate_agent", **item} for item in cls._duplicates)
        return {"ok": not issues, "registered_agents": [item.identifier for item in cls.definitions()], "count": len(cls._definitions), "issues": issues, "warnings": warnings}

    @classmethod
    def ensure_record(cls, user, identifier: str) -> Agent:
        definition = cls.get(identifier)
        runtime_available, unavailable_tools = definition.runtime_status()
        defaults = {
            "name": definition.identifier,
            "title": definition.name,
            "description": definition.description,
            "status": "active",
            "category": "builtin",
            "version": definition.version,
            "capabilities": list(definition.capabilities),
            "required_tools": list(definition.required_tools),
            "required_permissions": list(definition.required_permissions),
            "input_schema": definition.input_schema or {"type": "object"},
            "output_schema": definition.output_schema or {"type": "object"},
            "available": runtime_available,
            "health_status": "healthy" if runtime_available else "degraded" if definition.handler is not None else "unavailable",
            "last_health_check": timezone.now(),
            "configuration": {"context_scopes": list(definition.context_scopes), "unavailable_tools": unavailable_tools},
        }
        agent, _ = Agent.objects.update_or_create(owner=user, identifier=definition.identifier, defaults=defaults)
        return agent

    @classmethod
    def materialize_all(cls, user) -> list[Agent]:
        return [cls.ensure_record(user, item.identifier) for item in cls.definitions()]
