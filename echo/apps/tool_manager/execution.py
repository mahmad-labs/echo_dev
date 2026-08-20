from __future__ import annotations

import inspect
import json
import logging
import operator
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from .models import Tool, ToolExecution, ToolPermission

logger = logging.getLogger(__name__)


class ToolExecutionError(RuntimeError):
    def __init__(self, message: str, *, tool: str = "", error_type: str = "tool_execution_error", details: Any = None):
        super().__init__(message)
        self.tool = tool
        self.error_type = error_type
        self.details = details

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": "error",
            "success": False,
            "tool": self.tool,
            "error": str(self),
            "error_type": self.error_type,
            "details": self.details,
        }


@dataclass(frozen=True)
class ExecutionResult:
    execution_id: str
    status: str
    output: Any
    tool: str = ""
    success: bool = True
    error: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "status": self.status,
            "tool": self.tool,
            "execution_id": self.execution_id,
            "result": self.output,
            "error": self.error,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    category: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    permissions: tuple[str, ...]
    result_format: str
    handler: Callable[..., Any]
    availability: bool | Callable[[], bool] = True
    execution_mode: str = "sync"
    timeout: int = 60
    risk_level: str = "low"
    confirmation: str = "none"
    cancellable: bool = False
    agent_access: tuple[str, ...] = ()
    source: str = ""

    def is_available(self) -> bool:
        if callable(self.availability):
            try:
                return bool(self.availability())
            except Exception:
                return False
        return bool(self.availability)

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "permissions": list(self.permissions),
            "result_format": self.result_format,
            "availability": self.is_available(),
            "execution_mode": self.execution_mode,
            "timeout": self.timeout,
            "risk_level": self.risk_level,
            "confirmation": self.confirmation,
            "confirmation_required": self.confirmation != "none",
            "cancellable": self.cancellable,
            "agent_access": list(self.agent_access),
            "source": self.source,
        }


@dataclass(frozen=True)
class ToolContext:
    user: Any
    tool: Tool
    execution: ToolExecution
    agent: str = ""
    task_id: str = ""
    correlation_id: str = ""


class ToolExecutor:
    """Authoritative registry and execution boundary for every Echo tool.

    Planner, agents, workflows and APIs all discover tools from this class. Tool
    families are lazily bootstrapped by :class:`ToolRegistry`, so available tools do
    not depend on Django import ordering or incidental module side effects.
    """

    _registry: dict[str, ToolDefinition] = {}
    _duplicates: list[dict[str, str]] = []
    _ensuring = False

    @classmethod
    def _ensure_registry(cls) -> None:
        if cls._ensuring:
            return
        cls._ensuring = True
        try:
            from .registry import ToolRegistry
            ToolRegistry.bootstrap()
        finally:
            cls._ensuring = False

    @classmethod
    def register(
        cls,
        name: str,
        handler: Callable[..., Any],
        *,
        description: str = "",
        category: str = "",
        input_schema: dict[str, Any] | None = None,
        output_schema: dict[str, Any] | None = None,
        permissions: tuple[str, ...] = ("tools.execute",),
        result_format: str = "json",
        availability: bool | Callable[[], bool] = True,
        execution_mode: str = "sync",
        timeout: int = 60,
        risk_level: str = "low",
        confirmation: str = "none",
        cancellable: bool = False,
        agent_access: tuple[str, ...] = (),
    ) -> None:
        normalized = str(name or "").strip().lower()
        if not re.fullmatch(r"[a-z][a-z0-9_.-]{1,95}", normalized):
            raise ValueError("Tool handler names must be 2-96 safe characters.")
        if not callable(handler):
            raise ValueError(f"Tool {normalized!r} must have a callable handler.")
        category = str(category or normalized.split(".", 1)[0]).strip().lower()
        if risk_level not in {"low", "medium", "high", "critical"}:
            raise ValueError("risk_level must be low, medium, high or critical")
        if confirmation not in {"none", "required", "strong"}:
            raise ValueError("confirmation must be none, required or strong")
        definition = ToolDefinition(
            name=normalized,
            description=description or normalized.replace(".", " ").replace("_", " ").title(),
            category=category,
            input_schema=dict(input_schema or {"type": "object", "additionalProperties": True}),
            output_schema=dict(output_schema or {"type": "object"}),
            permissions=tuple(permissions or ("tools.execute",)),
            result_format=result_format,
            handler=handler,
            availability=availability,
            execution_mode=execution_mode,
            timeout=max(1, int(timeout or 60)),
            risk_level=risk_level,
            confirmation=confirmation,
            cancellable=bool(cancellable),
            agent_access=tuple(agent_access or ()),
            source=getattr(handler, "__module__", ""),
        )
        previous = cls._registry.get(normalized)
        if previous:
            previous_qn = getattr(previous.handler, "__qualname__", "")
            new_qn = getattr(definition.handler, "__qualname__", "")
            if (
                previous.source == definition.source
                and previous_qn == new_qn
                and previous.input_schema == definition.input_schema
                and previous.output_schema == definition.output_schema
            ):
                return
            cls._duplicates.append({"name": normalized, "existing_source": previous.source, "new_source": definition.source})
            raise ValueError(f"Duplicate tool registration for {normalized!r} from {previous.source!r} and {definition.source!r}.")
        cls._registry[normalized] = definition

    @classmethod
    def available_handlers(cls) -> tuple[str, ...]:
        """Return every registered handler, regardless of runtime availability.

        Kept for compatibility with structural validators. Runtime planners and
        public discovery surfaces should use :meth:`runtime_handlers` instead.
        """
        cls._ensure_registry()
        return tuple(sorted(cls._registry))

    @classmethod
    def runtime_handlers(cls) -> tuple[str, ...]:
        """Return only handlers whose configured runtime capability probe passes."""
        cls._ensure_registry()
        return tuple(sorted(name for name, definition in cls._registry.items() if definition.is_available()))

    @classmethod
    def definitions(cls) -> list[dict[str, Any]]:
        cls._ensure_registry()
        return [cls._registry[name].as_dict() for name in sorted(cls._registry)]

    @classmethod
    def definition(cls, name: str) -> ToolDefinition:
        cls._ensure_registry()
        normalized = str(name or "").strip().lower()
        definition = cls._registry.get(normalized)
        if definition is None:
            raise ValidationError({
                "status": "error",
                "error_type": "unknown_handler",
                "handler": normalized,
                "available_handlers": list(sorted(cls._registry)),
            })
        return definition

    @classmethod
    def validation_report(cls) -> dict[str, Any]:
        cls._ensure_registry()
        from .registry import ToolRegistry
        issues: list[dict[str, Any]] = []
        for name, definition in sorted(cls._registry.items()):
            if not callable(definition.handler):
                issues.append({"type": "missing_handler", "tool": name})
            try:
                cls._validate_schema_definition(definition.input_schema, path=f"{name}.input_schema")
                cls._validate_schema_definition(definition.output_schema, path=f"{name}.output_schema")
            except ValidationError as exc:
                issues.append({"type": "invalid_schema", "tool": name, "detail": str(exc)})
        issues.extend({"type": "duplicate_tool", **item} for item in cls._duplicates)
        for provider, error in ToolRegistry.errors().items():
            issues.append({"type": "provider_error", "provider": provider, "detail": error})
        return {
            "ok": not issues,
            "registered_tools": list(sorted(cls._registry)),
            "count": len(cls._registry),
            "issues": issues,
            "providers": [item.name for item in ToolRegistry.providers()],
        }

    @classmethod
    def _validate_schema_definition(cls, schema: dict[str, Any], *, path: str) -> None:
        if not isinstance(schema, dict):
            raise ValidationError(f"{path} must be an object")
        schema_type = schema.get("type")
        if schema_type and schema_type not in {"object", "array", "string", "number", "integer", "boolean", "null"}:
            raise ValidationError(f"{path}.type is unsupported: {schema_type}")
        properties = schema.get("properties")
        if properties is not None and not isinstance(properties, dict):
            raise ValidationError(f"{path}.properties must be an object")
        required = schema.get("required")
        if required is not None:
            if not isinstance(required, list) or any(not isinstance(item, str) or not item for item in required):
                raise ValidationError(f"{path}.required must be an array of non-empty strings")
            if isinstance(properties, dict):
                missing = [item for item in required if item not in properties]
                if missing:
                    raise ValidationError(f"{path}.required references undefined properties: {', '.join(missing)}")
        if isinstance(properties, dict):
            for name, child in properties.items():
                if not isinstance(name, str) or not name:
                    raise ValidationError(f"{path}.properties contains an invalid property name")
                if not isinstance(child, dict):
                    raise ValidationError(f"{path}.properties.{name} must be an object")
                cls._validate_schema_definition(child, path=f"{path}.properties.{name}")
        items = schema.get("items")
        if items is not None:
            if not isinstance(items, dict):
                raise ValidationError(f"{path}.items must be an object")
            cls._validate_schema_definition(items, path=f"{path}.items")
        if "enum" in schema and not isinstance(schema["enum"], list):
            raise ValidationError(f"{path}.enum must be an array")
        if "additionalProperties" in schema and not isinstance(schema["additionalProperties"], (bool, dict)):
            raise ValidationError(f"{path}.additionalProperties must be boolean or an object schema")

    @classmethod
    def _validate_value(cls, value: Any, schema: dict[str, Any], *, path: str = "input") -> None:
        if not schema:
            return
        if "enum" in schema and value not in schema["enum"]:
            raise ValidationError({path: f"must be one of: {', '.join(map(str, schema['enum']))}"})
        expected = schema.get("type")
        valid = {
            "object": isinstance(value, dict),
            "array": isinstance(value, list),
            "string": isinstance(value, str),
            "number": isinstance(value, (int, float)) and not isinstance(value, bool),
            "integer": isinstance(value, int) and not isinstance(value, bool),
            "boolean": isinstance(value, bool),
            "null": value is None,
        }
        if expected and expected in valid and not valid[expected]:
            raise ValidationError({path: f"must be of type {expected}"})
        if isinstance(value, str):
            if "minLength" in schema and len(value) < int(schema["minLength"]):
                raise ValidationError({path: f"must contain at least {schema['minLength']} characters"})
            if "maxLength" in schema and len(value) > int(schema["maxLength"]):
                raise ValidationError({path: f"must contain at most {schema['maxLength']} characters"})
            if schema.get("format") == "uri":
                from urllib.parse import urlparse
                parsed = urlparse(value)
                if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                    raise ValidationError({path: "must be a valid HTTP or HTTPS URL"})
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if "minimum" in schema and value < schema["minimum"]:
                raise ValidationError({path: f"must be >= {schema['minimum']}"})
            if "maximum" in schema and value > schema["maximum"]:
                raise ValidationError({path: f"must be <= {schema['maximum']}"})
        if isinstance(value, dict):
            required = schema.get("required") or []
            missing = [item for item in required if item not in value]
            if missing:
                raise ValidationError({path: f"missing required fields: {', '.join(missing)}"})
            properties = schema.get("properties") or {}
            if schema.get("additionalProperties") is False:
                extras = sorted(set(value) - set(properties))
                if extras:
                    raise ValidationError({path: f"unexpected fields: {', '.join(extras)}"})
            for key, child in properties.items():
                if key in value and isinstance(child, dict):
                    cls._validate_value(value[key], child, path=f"{path}.{key}")
        if isinstance(value, list):
            if "minItems" in schema and len(value) < int(schema["minItems"]):
                raise ValidationError({path: f"must contain at least {schema['minItems']} items"})
            if "maxItems" in schema and len(value) > int(schema["maxItems"]):
                raise ValidationError({path: f"must contain at most {schema['maxItems']} items"})
            if isinstance(schema.get("items"), dict):
                for index, item in enumerate(value):
                    cls._validate_value(item, schema["items"], path=f"{path}[{index}]")

    @classmethod
    def _check_permission(cls, tool: Tool, user, definition: ToolDefinition | None = None) -> None:
        if user.is_staff:
            return
        configuration = tool.configuration or {}
        required = configuration.get("required_permission")
        required_permissions = configuration.get("required_permissions")
        # Registry permissions are authoritative. Persisted Tool records may add a
        # stricter requirement, but can never replace or weaken the definition.
        requirements = list(definition.permissions if definition else ("tools.execute",))
        if isinstance(required_permissions, (list, tuple)):
            requirements.extend(str(item) for item in required_permissions if item)
        elif required:
            requirements.append(str(required))
        requirements = tuple(dict.fromkeys(item for item in requirements if item))

        explicit_permissions = list(ToolPermission.objects.filter(owner=user, status="active"))
        for permission_codename in requirements:
            role_granted = user.roles.filter(permission_links__permission__codename=permission_codename).exists()
            # A per-tool execution grant can satisfy only the generic tools.execute
            # gate. It must never satisfy domain permissions such as memory.write
            # or knowledge.read, otherwise a narrow ToolPermission becomes an
            # unintended privilege-escalation path.
            explicit_granted = permission_codename == "tools.execute" and any(
                str((permission.data or {}).get("tool_id", "")) == str(tool.pk)
                and "execute" in permission.permission_levels.casefold()
                for permission in explicit_permissions
            )
            if not (user.has_perm(permission_codename) or role_granted or explicit_granted):
                raise PermissionDenied(f"Permission {permission_codename!r} is required.")

    @classmethod
    def ensure_owned_tool(cls, name: str, user) -> Tool:
        definition = cls.definition(name)
        tool = Tool.objects.filter(owner=user, name=definition.name, status="active").first()
        desired = {
            "handler": definition.name,
            "input_schema": definition.input_schema,
            "output_schema": definition.output_schema,
            "required_permissions": list(definition.permissions),
            "result_format": definition.result_format,
            "confirmation": definition.confirmation,
            "cancellable": definition.cancellable,
            "execution_mode": definition.execution_mode,
            "timeout": definition.timeout,
            "risk_level": definition.risk_level,
            "agent_access": list(definition.agent_access),
            "registry_source": definition.source,
        }
        if tool:
            config = dict(tool.configuration or {})
            if any(config.get(key) != value for key, value in desired.items()) or tool.category != definition.category or tool.description != definition.description:
                tool.configuration = {**config, **desired}
                tool.description = definition.description
                tool.category = definition.category
                tool.save(update_fields=["configuration", "description", "category", "updated_at"])
            return tool
        return Tool.objects.create(
            owner=user,
            name=definition.name,
            title=definition.name.replace(".", " › ").replace("_", " ").title(),
            description=definition.description,
            status="active",
            category=definition.category,
            configuration=desired,
        )

    @classmethod
    def _invoke_handler(cls, definition: ToolDefinition, payload: dict[str, Any], context: ToolContext):
        try:
            parameters = inspect.signature(definition.handler).parameters
        except (TypeError, ValueError):
            parameters = {}
        if len(parameters) >= 2:
            return definition.handler(payload, context)
        return definition.handler(payload)

    @classmethod
    def execute(
        cls,
        tool: Tool,
        user,
        payload: Mapping[str, Any] | None = None,
        *,
        agent: str = "",
        task_id: str = "",
        correlation_id: str = "",
    ) -> ExecutionResult:
        configuration = tool.configuration or {}
        handler_name = str(configuration.get("handler") or tool.name).strip().lower()
        definition = cls.definition(handler_name)
        if not definition.is_available():
            raise ToolExecutionError(
                f"Tool {handler_name!r} is currently unavailable.",
                tool=handler_name,
                error_type="tool_unavailable",
            )
        normalized_agent = str(agent or "").strip().lower()
        if normalized_agent and definition.agent_access and normalized_agent not in definition.agent_access:
            raise PermissionDenied(f"Agent {normalized_agent!r} is not allowed to execute {handler_name!r}.")
        cls._check_permission(tool, user, definition)

        safe_payload = dict(payload or {})
        cls._validate_value(safe_payload, definition.input_schema, path="input")
        execution = ToolExecution.objects.create(
            owner=user,
            name=handler_name,
            title=f"Execution of {tool.title or tool.name or tool.pk}",
            status="running",
            category=tool.category,
            configuration={
                "tool_id": str(tool.pk),
                "input": safe_payload,
                "started_at": timezone.now().isoformat(),
                "handler": handler_name,
                "agent": normalized_agent,
                "task_id": str(task_id or ""),
                "correlation_id": str(correlation_id or ""),
                "execution_mode": definition.execution_mode,
                "risk_level": definition.risk_level,
            },
        )
        context = ToolContext(
            user=user,
            tool=tool,
            execution=execution,
            agent=normalized_agent,
            task_id=str(task_id or ""),
            correlation_id=str(correlation_id or ""),
        )
        logger.info("tool_execution_started", extra={"echo_event": {"tool": handler_name, "agent": normalized_agent, "task_id": str(task_id or ""), "execution_id": str(execution.pk)}})
        try:
            output = cls._invoke_handler(definition, safe_payload, context)
            json.dumps(output, default=str)
            cls._validate_value(output, definition.output_schema, path="output")
        except Exception as exc:
            if isinstance(exc, ToolExecutionError):
                error_type = exc.error_type
                error_details = exc.details
            elif isinstance(exc, ValidationError):
                error_type = "validation_error"
                error_details = getattr(exc, "message_dict", None) or getattr(exc, "messages", None)
            elif isinstance(exc, PermissionDenied):
                error_type = "permission_denied"
                error_details = None
            elif getattr(exc, "reason", None):
                error_type = str(getattr(exc, "reason")).strip().lower() or exc.__class__.__name__.lower()
                error_details = {"reason": getattr(exc, "reason", ""), "detail": getattr(exc, "detail", str(exc))}
            else:
                error_type = exc.__class__.__name__.lower()
                error_details = None
            execution.status = "failed"
            execution.configuration = {
                **execution.configuration,
                "finished_at": timezone.now().isoformat(),
                "error": str(exc),
                "error_type": error_type,
                "error_details": error_details,
            }
            execution.save(update_fields=["status", "configuration", "updated_at"])
            logger.exception("tool_execution_failed", extra={"echo_event": {"tool": handler_name, "agent": normalized_agent, "task_id": str(task_id or ""), "execution_id": str(execution.pk), "error_type": error_type}})
            if isinstance(exc, ToolExecutionError):
                raise
            raise ToolExecutionError(str(exc), tool=handler_name, error_type=error_type, details=error_details) from exc

        execution.status = "completed"
        execution.configuration = {
            **execution.configuration,
            "finished_at": timezone.now().isoformat(),
            "output": output,
        }
        execution.save(update_fields=["status", "configuration", "updated_at"])
        logger.info("tool_execution_completed", extra={"echo_event": {"tool": handler_name, "agent": normalized_agent, "task_id": str(task_id or ""), "execution_id": str(execution.pk)}})
        return ExecutionResult(
            str(execution.pk),
            execution.status,
            output,
            tool=handler_name,
            metadata={"agent": normalized_agent, "task_id": str(task_id or ""), "execution_mode": definition.execution_mode, "risk_level": definition.risk_level},
        )

    @classmethod
    def execute_named(
        cls,
        name: str,
        user,
        payload: Mapping[str, Any] | None = None,
        *,
        agent: str = "",
        task_id: str = "",
        correlation_id: str = "",
    ) -> ExecutionResult:
        return cls.execute(
            cls.ensure_owned_tool(name, user),
            user,
            payload,
            agent=agent,
            task_id=task_id,
            correlation_id=correlation_id,
        )

    @classmethod
    def execute_safe(cls, name: str, user, payload: Mapping[str, Any] | None = None, **kwargs) -> dict[str, Any]:
        try:
            return cls.execute_named(name, user, payload, **kwargs).as_dict()
        except ValidationError as exc:
            details = getattr(exc, "message_dict", None) or getattr(exc, "messages", None)
            error_type = "validation_error"
            if isinstance(details, dict) and "error_type" in details:
                value = details.get("error_type")
                if isinstance(value, (list, tuple)) and value:
                    value = value[0]
                if value:
                    error_type = str(value)
            message = "Unknown tool handler." if error_type == "unknown_handler" else "Tool request validation failed."
            return {"status": "error", "success": False, "tool": str(name or ""), "error_type": error_type, "error": message, "details": details}
        except PermissionDenied as exc:
            return {"status": "error", "success": False, "tool": str(name or ""), "error_type": "permission_denied", "error": str(exc), "details": None}
        except ToolExecutionError as exc:
            return exc.as_dict()


def _text_search(payload: dict[str, Any]) -> dict[str, Any]:
    text = str(payload.get("text", ""))
    query = str(payload.get("query", ""))
    if not query:
        raise ValueError("query is required")
    flags = re.IGNORECASE if payload.get("case_insensitive", True) else 0
    matches = [
        {"start": match.start(), "end": match.end(), "value": match.group(0)}
        for match in re.finditer(re.escape(query), text, flags)
    ]
    return {"count": len(matches), "matches": matches}


def _json_merge(payload: dict[str, Any]) -> dict[str, Any]:
    base = payload.get("base", {})
    overlay = payload.get("overlay", {})
    if not isinstance(base, dict) or not isinstance(overlay, dict):
        raise ValueError("base and overlay must be objects")

    def merge(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
        result = dict(left)
        for key, value in right.items():
            if isinstance(value, dict) and isinstance(result.get(key), dict):
                result[key] = merge(result[key], value)
            else:
                result[key] = value
        return result

    return merge(base, overlay)


def _calculate(payload: dict[str, Any]) -> dict[str, str]:
    operations = {
        "add": operator.add,
        "subtract": operator.sub,
        "multiply": operator.mul,
        "divide": operator.truediv,
    }
    operation = str(payload.get("operation", "")).lower()
    if operation not in operations:
        raise ValueError(f"operation must be one of: {', '.join(operations)}")
    left = Decimal(str(payload.get("left")))
    right = Decimal(str(payload.get("right")))
    if operation == "divide" and right == 0:
        raise ValueError("division by zero")
    return {"result": str(operations[operation](left, right))}


def register_core_tools() -> None:
    """Register Tool Manager-owned deterministic primitives.

    Even foundational tools use the same explicit registry bootstrap as browser,
    computer, agent, memory, and knowledge tools. This prevents import ordering
    from becoming an implicit capability-discovery mechanism.
    """

    ToolExecutor.register(
        "text.search",
        _text_search,
        description="Find literal text matches in supplied text.",
        category="text",
        input_schema={"type": "object", "required": ["text", "query"], "properties": {"text": {"type": "string"}, "query": {"type": "string"}}, "additionalProperties": True},
        output_schema={"type": "object"},
        permissions=("tools.execute",),
        agent_access=("chat", "planner", "workflow"),
    )
    ToolExecutor.register(
        "json.merge",
        _json_merge,
        description="Merge two JSON objects recursively.",
        category="json",
        input_schema={"type": "object", "properties": {"base": {"type": "object"}, "overlay": {"type": "object"}}, "additionalProperties": False},
        output_schema={"type": "object"},
        permissions=("tools.execute",),
        agent_access=("planner", "workflow"),
    )
    ToolExecutor.register(
        "math.calculate",
        _calculate,
        description="Perform basic decimal arithmetic.",
        category="math",
        input_schema={
            "type": "object",
            "required": ["operation", "left", "right"],
            "properties": {
                "operation": {"enum": ["add", "subtract", "multiply", "divide"]},
                "left": {},
                "right": {},
            },
            "additionalProperties": False,
        },
        output_schema={"type": "object", "required": ["result"], "properties": {"result": {"type": "string"}}, "additionalProperties": False},
        permissions=("tools.execute",),
        agent_access=("chat", "planner", "workflow"),
    )
