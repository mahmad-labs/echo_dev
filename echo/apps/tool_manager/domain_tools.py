from __future__ import annotations

from typing import Any


def _memory_search(payload: dict[str, Any], context):
    from echo.apps.memory.services import MemoryAgentService
    rows = MemoryAgentService.retrieve(
        context.user,
        str(payload.get("query") or ""),
        limit=int(payload.get("limit") or 8),
        reason=str(payload.get("reason") or "tool"),
        conversation_id=str(payload.get("conversation_id") or ""),
    )
    return {"memories": rows, "count": len(rows)}


def _memory_store(payload: dict[str, Any], context):
    from echo.apps.memory.services import MemoryAgentService
    memory, created = MemoryAgentService.remember(
        context.user,
        str(payload.get("content") or ""),
        summary=str(payload.get("summary") or ""),
        category=str(payload.get("category") or ""),
        memory_type=str(payload.get("memory_type") or ""),
        source_type=str(payload.get("source_type") or context.agent or "agent"),
        source_id=str(payload.get("source_id") or context.task_id or ""),
        importance=float(payload.get("importance", 0.6)),
        confidence=float(payload.get("confidence", 0.9)),
        metadata=dict(payload.get("metadata") or {}),
    )
    return {"memory": MemoryAgentService.serialize(memory), "created": created}


def _memory_update(payload: dict[str, Any], context):
    from echo.apps.memory.services import MemoryAgentService
    memory = MemoryAgentService.update(
        context.user,
        str(payload.get("memory_id") or ""),
        content=str(payload.get("content") or ""),
        summary=str(payload.get("summary") or ""),
    )
    return {"memory": MemoryAgentService.serialize(memory)}


def _memory_delete(payload: dict[str, Any], context):
    from echo.apps.memory.services import MemoryAgentService
    memory_id = str(payload.get("memory_id") or "")
    MemoryAgentService.delete(context.user, memory_id)
    return {"deleted": True, "memory_id": memory_id}


def _memory_deduplicate(payload: dict[str, Any], context):
    from echo.apps.memory.services import MemoryAgentService
    return MemoryAgentService.deduplicate(context.user)


def _knowledge_search(payload: dict[str, Any], context):
    from echo.apps.knowledge.services import KnowledgeAgentService
    rows = KnowledgeAgentService.search(context.user, str(payload.get("query") or ""), limit=int(payload.get("limit") or 12))
    return {"results": rows, "count": len(rows)}


def _knowledge_ingest(payload: dict[str, Any], context):
    from echo.apps.knowledge.services import KnowledgeAgentService
    document = KnowledgeAgentService.ingest(
        context.user,
        title=str(payload.get("title") or ""),
        content=str(payload.get("content") or ""),
        source_type=str(payload.get("source_type") or context.agent or "agent"),
        source_id=str(payload.get("source_id") or context.task_id or ""),
        category=str(payload.get("category") or "research"),
        metadata=dict(payload.get("metadata") or {}),
    )
    return {"document_id": str(document.pk), "title": document.title or document.name, "category": document.category, "updated_at": document.updated_at.isoformat()}


def register_domain_tools() -> None:
    from .execution import ToolExecutor

    object_output = {"type": "object"}
    memory_agents = ("memory", "planner", "chat", "projects", "workflow")
    knowledge_agents = ("knowledge", "planner", "chat", "projects", "documents", "browser", "workflow")
    ToolExecutor.register(
        "memory.search", _memory_search, description="Retrieve owner-scoped durable Echo memory.", category="memory",
        input_schema={"type": "object", "properties": {"query": {"type": "string", "minLength": 1}, "limit": {"type": "integer", "minimum": 1, "maximum": 50}, "reason": {"type": "string"}, "conversation_id": {"type": "string"}}, "required": ["query"], "additionalProperties": False},
        output_schema=object_output, permissions=("memory.read",), agent_access=memory_agents,
    )
    ToolExecutor.register(
        "memory.store", _memory_store, description="Store or deduplicate an approved durable user/project memory.", category="memory",
        input_schema={"type": "object", "properties": {"content": {"type": "string", "minLength": 1, "maxLength": 20000}, "summary": {"type": "string", "maxLength": 500}, "category": {"type": "string"}, "memory_type": {"type": "string"}, "source_type": {"type": "string"}, "source_id": {"type": "string"}, "importance": {"type": "number", "minimum": 0, "maximum": 1}, "confidence": {"type": "number", "minimum": 0, "maximum": 1}, "metadata": {"type": "object"}}, "required": ["content"], "additionalProperties": False},
        output_schema=object_output, permissions=("memory.write",), risk_level="medium", agent_access=memory_agents,
    )
    ToolExecutor.register(
        "memory.update", _memory_update, description="Correct an existing owner-scoped memory.", category="memory",
        input_schema={"type": "object", "properties": {"memory_id": {"type": "string", "minLength": 1}, "content": {"type": "string", "minLength": 1, "maxLength": 20000}, "summary": {"type": "string", "maxLength": 500}}, "required": ["memory_id", "content"], "additionalProperties": False},
        output_schema=object_output, permissions=("memory.write",), risk_level="medium", agent_access=("memory",),
    )
    ToolExecutor.register(
        "memory.delete", _memory_delete, description="Delete a specific owner-scoped memory after an explicit user delete request.", category="memory",
        input_schema={"type": "object", "properties": {"memory_id": {"type": "string", "minLength": 1}}, "required": ["memory_id"], "additionalProperties": False},
        output_schema=object_output, permissions=("memory.write",), risk_level="high", agent_access=("memory",),
    )
    ToolExecutor.register(
        "memory.deduplicate", _memory_deduplicate, description="Remove exact duplicate owner-scoped memories.", category="memory",
        input_schema={"type": "object", "additionalProperties": False}, output_schema=object_output, permissions=("memory.write",), risk_level="medium", agent_access=("memory",),
    )
    ToolExecutor.register(
        "knowledge.search", _knowledge_search, description="Search owner-scoped Echo knowledge using lexical and semantic retrieval.", category="knowledge",
        input_schema={"type": "object", "properties": {"query": {"type": "string", "minLength": 1}, "limit": {"type": "integer", "minimum": 1, "maximum": 50}}, "required": ["query"], "additionalProperties": False},
        output_schema=object_output, permissions=("knowledge.read",), agent_access=knowledge_agents,
    )
    ToolExecutor.register(
        "knowledge.ingest", _knowledge_ingest, description="Ingest verified external or user-provided information into owner-scoped Echo knowledge.", category="knowledge",
        input_schema={"type": "object", "properties": {"title": {"type": "string", "maxLength": 255}, "content": {"type": "string", "minLength": 1}, "source_type": {"type": "string"}, "source_id": {"type": "string"}, "category": {"type": "string"}, "metadata": {"type": "object"}}, "required": ["content"], "additionalProperties": False},
        output_schema=object_output, permissions=("knowledge.write",), risk_level="medium", agent_access=knowledge_agents,
    )
