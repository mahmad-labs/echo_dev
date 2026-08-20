from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from echo.apps.chat.models import Conversation, Message
from echo.apps.core.command_service import CommandError, CommandResult, EchoCommandService
from echo.apps.knowledge.services import KnowledgeAgentService
from echo.apps.memory.services import MemoryAgentService
from echo.apps.tool_manager.execution import ToolExecutor

from .contracts import AgentContext, AgentResult
from .models import AgentCommunication, AgentTask
from .registry import AgentDefinition, AgentRegistry
from .intent_router import UniversalIntentRouter

logger = logging.getLogger(__name__)



def _owned(model, user):
    qs = model.objects.all()
    if user.is_staff:
        return qs
    fields = {field.name for field in model._meta.fields}
    if "owner" in fields:
        return qs.filter(owner=user)
    if "user" in fields:
        return qs.filter(user=user)
    return qs.none()


def _permission_names(user) -> list[str]:
    if user.is_superuser:
        return ["*"]
    names = set(user.get_all_permissions())
    try:
        names.update(user.roles.values_list("permission_links__permission__codename", flat=True))
    except Exception:
        pass
    return sorted(str(item) for item in names if item)


def _ensure_conversation(user, prompt: str, conversation_id: str | None, source: str, section: str) -> Conversation:
    if conversation_id:
        try:
            conversation = _owned(Conversation, user).filter(pk=conversation_id).first()
        except (TypeError, ValueError):
            conversation = None
        if conversation:
            return conversation
    return Conversation.objects.create(
        owner=user, user=user, name=prompt[:80], title=prompt[:80],
        description=f"Started through Echo Agent Manager ({source}).", status="active",
        conversation_type="voice" if source == "voice" else "workspace",
        current_model=getattr(settings, "AI_PROVIDER_MODEL", ""), last_message_at=timezone.now(),
        data={"origin": section, "input_mode": source, "orchestrated": True},
    )


def _save_message(user, conversation: Conversation, role: str, content: str, **data) -> Message:
    message = Message.objects.create(
        owner=user, conversation=conversation, name=f"{role}_message", title=(content[:80] or role.title()),
        status="completed", sender=role, role=role, content=content, rendered_content=content, data=data,
    )
    conversation.last_message_at = timezone.now()
    conversation.save(update_fields=["last_message_at", "updated_at"])
    return message


class AgentContextBuilder:
    @classmethod
    def build(
        cls,
        user,
        prompt: str,
        *,
        conversation: Conversation | None = None,
        voice_session_id: str = "",
        task: AgentTask | None = None,
        project_id: str = "",
    ) -> AgentContext:
        from echo.apps.internet.models import BrowserObservation, BrowserSession, ComputerObservation, ComputerSession

        scopes: set[str] = set()
        if task and task.agent_id:
            try:
                scopes.update(AgentRegistry.get(task.agent.identifier).context_scopes)
            except Exception:
                pass
        # Manager context is intentionally demand-driven. A task that does not declare
        # memory/knowledge/browser/computer access never receives those domains.
        need_browser = bool(scopes & {"browser", "page", "observations"})
        need_computer = bool(scopes & {"computer", "observations"})
        browser = _owned(BrowserSession, user).exclude(status__in=("completed", "ended", "closed")).order_by("-last_activity_at").first() if need_browser else None
        computer = _owned(ComputerSession, user).exclude(status__in=("completed", "ended", "closed")).order_by("-last_activity_at").first() if need_computer else None
        observations: list[dict[str, Any]] = []
        current_page: dict[str, Any] = {}
        if browser:
            latest = _owned(BrowserObservation, user).filter(session=browser).order_by("-sequence").first()
            if latest:
                current_page = {
                    "environment": "browser", "url": latest.url, "title": latest.page_title,
                    "visible_text": latest.visible_text[:4000], "viewport": latest.viewport,
                    "observation_id": str(latest.pk),
                }
                observations.append(current_page)
        if computer:
            latest_pc = _owned(ComputerObservation, user).filter(session=computer).order_by("-sequence").first()
            if latest_pc:
                observations.append({
                    "environment": "desktop", "observation_id": str(latest_pc.pk),
                    "window_info": latest_pc.window_info, "ocr_text": latest_pc.ocr_text[:3000],
                    "viewport": latest_pc.viewport,
                })

        conversation_id = str(conversation.pk) if conversation else ""
        conversation_project_id = str((conversation.data or {}).get("current_project_id") or "") if conversation else ""
        effective_project_id = str(project_id or (task.project_id if task and task.project_id else "") or conversation_project_id)
        project_context: dict[str, Any] = {}
        if effective_project_id and "project" in scopes:
            try:
                from echo.apps.projects.models import Project
                project = _owned(Project, user).filter(pk=effective_project_id).first()
                if project:
                    project_context = {
                        "id": str(project.pk), "title": project.title or project.name,
                        "description": project.description[:4000], "status": project.status,
                        "configuration": project.configuration or {}, "updated_at": project.updated_at.isoformat(),
                    }
                else:
                    effective_project_id = ""
            except Exception:
                effective_project_id = ""
        memories: list[dict[str, Any]] = []
        knowledge: list[dict[str, Any]] = []
        if "memory" in scopes:
            memory_agent = AgentRegistry.ensure_record(user, "memory")
            if task:
                AgentMessageBus.send(user=user, task=task, sender=None, recipient=memory_agent, message_type="context_request", payload={"query": prompt, "limit": 6, "purpose": "orchestration_context"})
            memories = MemoryAgentService.retrieve(user, prompt, limit=6, reason="agent_manager", conversation_id=conversation_id)
            if task:
                AgentMessageBus.send(user=user, task=task, sender=memory_agent, recipient=None, message_type="context_result", payload={"count": len(memories), "memories": memories})
        if "knowledge" in scopes:
            knowledge_agent = AgentRegistry.ensure_record(user, "knowledge")
            if task:
                AgentMessageBus.send(user=user, task=task, sender=None, recipient=knowledge_agent, message_type="context_request", payload={"query": prompt, "limit": 8, "purpose": "orchestration_context"})
            knowledge = KnowledgeAgentService.search(user, prompt, limit=8)
            if task:
                AgentMessageBus.send(user=user, task=task, sender=knowledge_agent, recipient=None, message_type="context_result", payload={"count": len(knowledge), "knowledge": knowledge})

        approvals = []
        if "approvals" in scopes:
            try:
                from echo.apps.internet.models import ComputerUseOperation
                for item in _owned(ComputerUseOperation, user).filter(status="waiting_user").order_by("-updated_at")[:6]:
                    approvals.append({"type": "computer_use", "id": str(item.pk), "attention": (item.configuration or {}).get("attention")})
            except Exception:
                pass
        execution_state = {}
        if "execution" in scopes:
            available_tools = [item["name"] for item in ToolExecutor.definitions() if item.get("availability") and (not item.get("agent_access") or (task and task.agent_id and task.agent.identifier in item.get("agent_access", [])))]
            available_agents = [item.identifier for item in AgentRegistry.definitions() if item.runtime_status()[0]]
            execution_state = {
                "agent_task_status": task.status if task else "",
                "current_agent": task.agent.identifier if task and task.agent_id else "manager",
                "available_tools": available_tools,
                "available_agents": available_agents,
            }
            if observations:
                desktop = next((item for item in reversed(observations) if item.get("environment") == "desktop"), None)
                if desktop:
                    execution_state["active_window"] = desktop.get("window_info") or {}

        return AgentContext(
            user_id=str(user.pk), conversation_id=conversation_id, voice_session_id=str(voice_session_id or ""),
            task_id=str(task.pk) if task else "", project_id=effective_project_id, project_context=project_context,
            browser_session_id=str(browser.pk) if browser else "", computer_session_id=str(computer.pk) if computer else "",
            current_page=current_page, recent_observations=observations,
            relevant_memories=memories, relevant_knowledge=knowledge,
            permissions=_permission_names(user) if "permissions" in scopes else [], approvals=approvals,
            execution_state=execution_state,
            variables=(
                {"prompt": prompt, "routing": dict((task.input_payload or {}).get("routing") or {}), "intent": str((task.input_payload or {}).get("intent") or "")}
                if "variables" in scopes and task else {"prompt": prompt} if "variables" in scopes else {}
            ),
        )


class AgentMessageBus:
    @classmethod
    def send(cls, *, user, task: AgentTask, sender, recipient, message_type: str, payload: dict[str, Any]) -> AgentCommunication:
        return AgentCommunication.objects.create(
            owner=user, name=message_type, title=f"{sender.identifier if sender else 'manager'} → {recipient.identifier if recipient else 'manager'}",
            status="completed", category="orchestration", task=task, sender_agent=sender, recipient_agent=recipient,
            message_type=message_type, correlation_id=task.correlation_id, payload=payload, processed_at=timezone.now(),
        )


class BuiltinAgents:
    @staticmethod
    def memory(*, user, prompt, context, task, source, section) -> AgentResult:
        correction = re.search(r"\b(?:correct|update|change)\s+(?:my\s+)?memory(?:\s+about)?\s+(.+?)\s+(?:to|so that it says)\s+(.+)$", prompt, re.I)
        if correction:
            query, replacement = correction.group(1).strip(), correction.group(2).strip().rstrip(".")
            rows = (ToolExecutor.execute_named("memory.search", user, {"query": query, "limit": 3, "reason": "memory_correction", "conversation_id": context.conversation_id}, agent="memory", task_id=str(task.pk)).output or {}).get("memories", [])
            if len(rows) != 1:
                return AgentResult(status="waiting", result={"content": "I need you to identify exactly which memory to correct.", "route": "memory.update", "needs_confirmation": True, "data": {"matches": rows}})
            updated = ToolExecutor.execute_named("memory.update", user, {"memory_id": rows[0]["id"], "content": replacement, "summary": replacement[:255]}, agent="memory", task_id=str(task.pk)).output or {}
            memory = updated.get("memory") or {}
            return AgentResult(status="completed", result={"content": "I corrected that memory.", "route": "memory.update", "data": {"memory_id": str(memory.get("id") or rows[0]["id"])}})

        deletion = re.search(r"\b(?:forget|delete|remove)\s+(?:the\s+)?(?:memory\s+)?(?:that|about)?\s*(.+)$", prompt, re.I)
        if deletion:
            query = deletion.group(1).strip().rstrip(".")
            rows = (ToolExecutor.execute_named("memory.search", user, {"query": query, "limit": 3, "reason": "memory_deletion", "conversation_id": context.conversation_id}, agent="memory", task_id=str(task.pk)).output or {}).get("memories", [])
            if len(rows) != 1:
                return AgentResult(status="waiting", result={"content": "I need you to identify exactly which memory to remove.", "route": "memory.delete", "needs_confirmation": True, "data": {"matches": rows}})
            ToolExecutor.execute_named("memory.delete", user, {"memory_id": rows[0]["id"]}, agent="memory", task_id=str(task.pk))
            return AgentResult(status="completed", result={"content": "I removed that memory.", "route": "memory.delete", "data": {"memory_id": rows[0]["id"]}})

        match = re.search(r"\bremember\s+(?:that\s+)?(.+)", prompt, re.I)
        if match:
            content = match.group(1).strip().rstrip(".")
            # Voice keeps the existing approval policy; text can explicitly store.
            if source == "voice":
                return AgentResult(status="waiting", result={"content": "I captured that as a memory candidate. Approve it before I store it as permanent memory.", "route": "memory.candidate", "memory_candidate": content, "data": {"candidate": content}}, next_actions=[{"type": "approval", "action": "memory.store"}])
            stored = ToolExecutor.execute_named("memory.store", user, {"content": content, "source_type": source, "source_id": str(task.pk), "metadata": {"conversation_id": context.conversation_id}}, agent="memory", task_id=str(task.pk)).output or {}
            memory = stored.get("memory") or {}
            created = bool(stored.get("created"))
            return AgentResult(status="completed", result={"content": "I remembered that." if created else "I already had that memory, so I refreshed it.", "route": "memory.store", "data": {"memory_id": str(memory.get("id") or ""), "created": created}})
        rows = (ToolExecutor.execute_named("memory.search", user, {"query": prompt, "limit": 8, "reason": "memory_agent", "conversation_id": context.conversation_id}, agent="memory", task_id=str(task.pk)).output or {}).get("memories", [])
        if not rows:
            return AgentResult(status="completed", result={"content": "I could not find a matching approved memory.", "route": "memory.search", "data": {"memories": []}})
        summary = "\n".join(f"• {row['title']}: {row['content'][:240]}" for row in rows[:6])
        return AgentResult(status="completed", result={"content": f"Here are the relevant memories:\n{summary}", "route": "memory.search", "data": {"memories": rows}})

    @staticmethod
    def knowledge(*, user, prompt, context, task, source, section) -> AgentResult:
        query = re.sub(r"^(?:search|find)(?:\s+my)?\s+knowledge(?:\s+(?:for|about))?\s*", "", prompt, flags=re.I).strip() or prompt
        rows = (ToolExecutor.execute_named("knowledge.search", user, {"query": query, "limit": 10}, agent="knowledge", task_id=str(task.pk)).output or {}).get("results", [])
        if not rows:
            return AgentResult(status="completed", result={"content": "I could not find matching knowledge in your workspace.", "route": "knowledge.search", "data": {"sources": []}})
        if getattr(settings, "AI_PROVIDER_BASE_URL", "") and getattr(settings, "AI_PROVIDER_API_KEY", ""):
            from echo.apps.ai_engine.runtime import AIExecutionService
            messages = [
                {"role": "system", "content": "Answer only from the supplied Echo knowledge sources. Be concise, cite titles, and state uncertainty. Do not invent missing facts."},
                {"role": "user", "content": f"Question: {prompt}\n\nSources: {rows}"},
            ]
            request_record, response_record, _ = AIExecutionService.generate(user, messages, model=getattr(settings, "AI_PROVIDER_MODEL", "") or None)
            content = response_record.content
            latency = request_record.latency
        else:
            content = "Matching knowledge:\n" + "\n".join(f"• {row['title']}: {row['excerpt'][:260]}" for row in rows[:6])
            latency = 0
        return AgentResult(status="completed", result={"content": content, "route": "knowledge.search", "latency": latency, "data": {"sources": rows}}, confidence=max((row.get("semantic_score", 0) for row in rows), default=0))

    @staticmethod
    def planner(*, user, prompt, context, task, source, section) -> AgentResult:
        from echo.apps.planner.engine import PlanningEngine
        from echo.apps.planner.models import Goal, PlanStep

        lowered = prompt.casefold()
        assignments: list[tuple[str, str]] = []
        if re.search(r"\b(?:continue|resume)\b.*\bproject\b", lowered):
            assignments.extend([
                ("projects", "Load the current project state"),
                ("memory", "Retrieve relevant user and project memories"),
                ("knowledge", "Retrieve relevant project knowledge"),
                ("planner", "Determine the safest useful next actions"),
            ])
        elif re.search(r"\b(?:research|investigate|look up)\b", lowered):
            assignments.append(("browser", "Research the objective using verified browser evidence"))
            if re.search(r"\b(?:compare|analyze|analyse|summarize|summarise)\b", lowered):
                assignments.append(("knowledge", "Structure and compare the verified findings"))
            if re.search(r"\b(?:save|store|add)\b.*\bknowledge\b|\bremember\b.*\b(?:findings|main points|research)\b", lowered):
                assignments.append(("knowledge", "Store approved external findings in the knowledge base"))
            if re.search(r"\b(?:create|prepare|write|generate)\b.*\breport\b", lowered):
                assignments.append(("documents", "Create a report from verified research evidence"))
        elif re.search(r"\b(?:document|file|pdf)\b", lowered):
            assignments.extend([("documents", "Extract and analyze the requested document"), ("knowledge", "Make useful document knowledge retrievable")])
        else:
            assignments = [
                ("planner", "Confirm requirements and acceptance criteria"),
                ("planner", "Prepare dependencies and implementation inputs"),
                ("planner", "Execute the work and capture evidence"),
                ("planner", "Validate the result against acceptance criteria"),
            ]
        # Preserve order but remove duplicate adjacent/identical assignments.
        seen = set()
        normalized_assignments = []
        for agent_id, title in assignments:
            key = (agent_id, title.casefold())
            if key not in seen:
                seen.add(key)
                normalized_assignments.append((agent_id, title))
        goal = Goal.objects.create(
            owner=user, name=prompt[:255], title=prompt[:255], description=prompt, status="active", category="agent_goal",
            configuration={
                "outcome": prompt,
                "constraints": ["Use owner-scoped context", "Verify environment actions before reporting success", "Pause for required human approval"],
                "success_criteria": ["Requested objective completed with verified results"],
                "milestones": [title for _agent, title in normalized_assignments],
                "agent_sequence": [agent_id for agent_id, _title in normalized_assignments],
            },
        )
        plan = PlanningEngine.build(goal, user)
        steps = list(PlanStep.objects.filter(owner=user, configuration__plan_id=str(plan.pk)).order_by("created_at"))
        step_payload = []
        for index, item in enumerate(steps):
            agent_id = normalized_assignments[index][0] if index < len(normalized_assignments) else "planner"
            item.configuration = {**(item.configuration or {}), "assigned_agent": agent_id}
            item.save(update_fields=["configuration", "updated_at"])
            step_payload.append({"id": str(item.pk), "title": item.title, "status": item.status, "assigned_agent": agent_id})
        return AgentResult(
            status="completed",
            result={
                "content": f"I created a {len(steps)}-step coordinated plan for this objective.",
                "route": "planner.plan",
                "data": {"goal_id": str(goal.pk), "plan_id": str(plan.pk), "steps": step_payload, "agent_sequence": [item[0] for item in normalized_assignments]},
            },
        )

    @staticmethod
    def browser(*, user, prompt, context, task, source, section) -> AgentResult:
        from echo.apps.internet.computer_use import ComputerUseCommandRouter
        routed = ComputerUseCommandRouter.handle(user, prompt, conversation=_owned(Conversation, user).filter(pk=context.conversation_id).first() if context.conversation_id else None, source=source)
        if not routed:
            return AgentResult(status="failed", result={"content": "I could not map that request to a safe browser operation.", "route": "browser.unhandled", "data": {}}, errors=[{"code": "browser_unhandled"}])
        data = dict(routed.get("data") or {})
        operation_id = data.get("operation_id")
        execution_status = str(data.get("execution_status") or "")
        if operation_id:
            try:
                from echo.apps.internet.models import ComputerUseOperation
                operation = _owned(ComputerUseOperation, user).filter(pk=operation_id).first()
                if operation:
                    operation.configuration = {
                        **(operation.configuration or {}), "agent_task_id": str(task.pk),
                        "agent_parent_task_id": str(task.parent_task_id or ""),
                        "agent_post_actions": list((task.input_payload or {}).get("post_actions") or []),
                    }
                    operation.save(update_fields=["configuration", "updated_at"])
                    task.current_tool = operation.current_tool or "browser.operation"
                    task.current_operation = operation.current_operation or "Browser operation running"
                    task.save(update_fields=["current_tool", "current_operation", "updated_at"])
            except Exception:
                pass
        status_value = "running" if execution_status in {"queued", "running", "cancelling"} else ("waiting" if execution_status == "waiting_user" else str(routed.get("status") or "completed"))
        return AgentResult(status=status_value, result={"content": str(routed.get("content") or ""), "route": str(routed.get("route") or "computer_use"), "data": data, "needs_confirmation": bool(routed.get("needs_confirmation", False))})

    @staticmethod
    def computer(*, user, prompt, context, task, source, section) -> AgentResult:
        from echo.apps.internet.desktop_control import ComputerControlCommandRouter
        routed = ComputerControlCommandRouter.handle(user, prompt, route_metadata=dict(context.variables.get("routing") or {}))
        if not routed:
            return AgentResult(status="failed", result={"content": "I could not map that request to an authorized computer-control action.", "route": "computer.unhandled", "data": {}}, errors=[{"code": "computer_unhandled"}])
        return AgentResult(status=str(routed.get("status") or "completed"), result={"content": str(routed.get("content") or ""), "route": str(routed.get("route") or "computer"), "data": dict(routed.get("data") or {}), "needs_confirmation": bool(routed.get("needs_confirmation", False))})

    @staticmethod
    def command(*, user, prompt, context, task, source, section) -> AgentResult:
        result = EchoCommandService(user, source=source, section=section)._route(prompt, _owned(Conversation, user).get(pk=context.conversation_id))
        return AgentResult(status=result.status, result={"content": result.content, "route": result.route, "data": result.data, "requires_configuration": result.requires_configuration, "configure_url": result.configure_url, "needs_confirmation": result.needs_confirmation, "memory_candidate": result.memory_candidate, "latency": result.latency})


AGENT_DEFINITIONS = (
    AgentDefinition("memory", "Memory Agent", "Retrieves and manages durable owner-specific memories under Echo memory policy.", ("memory.retrieve", "memory.store", "memory.update", "memory.delete", "memory.deduplicate"), required_tools=("memory.search", "memory.store", "memory.update", "memory.delete", "memory.deduplicate"), required_permissions=("memory.read",), context_scopes=("conversation", "project", "memory", "permissions", "execution"), handler=BuiltinAgents.memory),
    AgentDefinition("knowledge", "Knowledge Agent", "Central semantic and document knowledge retrieval/ingestion interface.", ("knowledge.search", "knowledge.retrieve", "knowledge.ingest", "knowledge.update"), required_tools=("knowledge.search", "knowledge.ingest"), required_permissions=("knowledge.read",), context_scopes=("conversation", "project", "knowledge", "memory", "permissions", "execution"), handler=BuiltinAgents.knowledge),
    AgentDefinition("planner", "Planner Agent", "Decomposes objectives and persists executable plans.", ("plan.create", "plan.decompose", "plan.coordinate"), context_scopes=("conversation", "project", "memory", "knowledge", "browser", "computer", "page", "observations", "permissions", "approvals", "execution", "variables"), handler=BuiltinAgents.planner),
    AgentDefinition("browser", "Browser Agent", "General browser computer-use through DOM/accessibility/screenshot observation and verified actions.", ("browser.observe", "browser.act", "browser.verify", "browser.media"), required_tools=("browser.open_url", "browser.click", "browser.scroll"), required_permissions=("tools.execute",), context_scopes=("conversation", "project", "memory", "knowledge", "browser", "page", "observations", "permissions", "approvals", "execution"), handler=BuiltinAgents.browser),
    AgentDefinition("computer", "Computer Agent", "Authorized desktop screen/input control with UI-tree and vision fallback.", ("computer.observe", "computer.act", "computer.verify", "computer.applications", "computer.system_locations", "computer.windows", "computer.multi_step"), required_tools=("computer.observe", "computer.click", "computer.scroll", "computer.execute_task"), required_permissions=("tools.execute",), context_scopes=("conversation", "computer", "observations", "permissions", "approvals", "execution", "variables"), handler=BuiltinAgents.computer),
    AgentDefinition("documents", "Document Agent", "Processes, analyzes and routes document content into Echo knowledge.", ("documents.analyze", "documents.extract", "documents.index"), context_scopes=("conversation", "project", "knowledge", "permissions", "execution"), handler=BuiltinAgents.command),
    AgentDefinition("projects", "Project Agent", "Retrieves and updates project context and coordinates project continuation.", ("projects.create", "projects.continue", "projects.context"), context_scopes=("conversation", "project", "memory", "knowledge", "permissions", "execution"), handler=BuiltinAgents.command),
    AgentDefinition("tasks", "Task Agent", "Creates, retrieves, completes and coordinates user tasks.", ("tasks.create", "tasks.list", "tasks.complete"), context_scopes=("conversation", "project", "memory", "permissions", "execution"), handler=BuiltinAgents.command),
    AgentDefinition("workflow", "Workflow Agent", "Starts and coordinates existing Echo workflow executions.", ("workflow.execute", "workflow.monitor"), context_scopes=("conversation", "project", "memory", "knowledge", "permissions", "approvals", "execution"), handler=BuiltinAgents.command),
    AgentDefinition("chat", "Chat Agent", "Conversational fallback over existing Echo AI and domain services.", ("chat.respond",), context_scopes=("conversation", "project", "memory", "knowledge", "browser", "computer", "page", "permissions", "approvals", "execution"), handler=BuiltinAgents.command),
)
for _definition in AGENT_DEFINITIONS:
    AgentRegistry.register(_definition)


@dataclass(frozen=True)
class RouteDecision:
    agent: str
    complex: bool = False
    child_prompts: tuple[str, ...] = ()
    post_actions: tuple[str, ...] = ()
    intent: str = ""
    confidence: float = 1.0
    clarification: str = ""
    metadata: dict[str, Any] | None = None


class AgentManagerOrchestrator:
    """Single coordination entry point for text, voice and other Echo input channels."""

    def __init__(self, user, *, source: str = "text", section: str = "home", voice_session_id: str = ""):
        self.user = user
        self.source = source
        self.section = section
        self.voice_session_id = str(voice_session_id or "")

    @staticmethod
    def _is_browser(prompt: str) -> bool:
        lowered = prompt.casefold()
        return any(token in lowered for token in ("http://", "https://", ".com", ".org", "website", "browser", "youtube", "google", "github", "gmail", "wikipedia", "reddit", "linkedin", "upwork", "scroll", "click", "open the first", "open that", "play it", "pause", "watch and listen", "video"))

    @staticmethod
    def _is_computer(prompt: str) -> bool:
        lowered = prompt.casefold()
        return any(token in lowered for token in ("downloads folder", "documents folder", "desktop folder", "current screen", "screen", "mouse", "keyboard", "active window"))

    def decide(self, prompt: str) -> RouteDecision:
        lowered = prompt.casefold().strip()
        # Preserve explicit voice lifecycle commands at the shared command layer.
        normalized = re.sub(r"[^a-z ]+", " ", lowered)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        if normalized in {"echo", "hey echo", "hello echo", "stop", "echo stop", "stop listening", "echo stop listening", "echo shut down", "shut down", "shutdown voice", "shut down voice", "disable voice", "echo disable voice", "activate voice", "enable voice"}:
            return RouteDecision("chat", intent="voice_control")

        # Deterministic universal computer-use routing runs before broad browser or AI
        # heuristics. It never converts an unresolved local OPEN command into search.
        routed = UniversalIntentRouter.classify(prompt, user=self.user)
        if routed:
            if routed.agent == "clarify":
                return RouteDecision("chat", intent=routed.intent, confidence=routed.confidence, clarification=routed.clarification)
            return RouteDecision(routed.agent, intent=routed.intent, confidence=routed.confidence, metadata=dict(routed.metadata or {}))
        external_capture = bool(re.search(r"\bremember\b.*\b(?:main points|findings|research|video|page|article|source)\b", lowered))
        research_capture = bool(re.search(r"\b(?:research|investigate|look up)\b", lowered) and re.search(r"\b(?:save|store|add)\b.*\bknowledge\b", lowered))
        if external_capture or research_capture:
            post = ["knowledge.ingest"]
            if re.search(r"\b(?:create|prepare|write|generate)\b.*\breport\b", lowered):
                post.append("documents.report")
            return RouteDecision("browser", complex=True, post_actions=tuple(post))
        if re.search(r"\bremember\s+(?:that\s+)?", lowered) or "what do you remember" in lowered or "search my memory" in lowered or re.search(r"\b(?:forget|delete|remove|correct|update|change)\b.*\bmemory\b", lowered) or re.search(r"^\s*forget\s+", lowered):
            return RouteDecision("memory")
        if any(phrase in lowered for phrase in ("search my knowledge", "find in my knowledge", "what do i already know", "knowledge base")):
            return RouteDecision("knowledge")
        if re.search(r"\b(?:research|investigate|look up)\b", lowered):
            post = ("documents.report",) if re.search(r"\b(?:create|prepare|write|generate)\b.*\breport\b", lowered) else ()
            return RouteDecision("browser", complex=True, post_actions=post)
        if any(phrase in lowered for phrase in ("plan my day", "plan my work", "create a plan", "decompose", "plan this")):
            return RouteDecision("planner")
        if re.search(r"\b(?:create|add|make|schedule|list|show|mark|complete|finish)\b.*\btask", lowered) or "show my active tasks" in lowered:
            return RouteDecision("tasks")
        if re.search(r"\b(?:analyze|summarize|review|read)\b.*\b(?:document|file|pdf)\b", lowered):
            return RouteDecision("documents")
        if re.search(r"\b(?:create|start|continue|resume|open)\b.*\bproject\b", lowered):
            # Continuing/resuming an existing project is a coordinated objective: the
            # Planner receives the same project-scoped Memory and Knowledge context
            # before the Project Agent loads the concrete project state. Simple project
            # creation/opening remains direct.
            coordinated = bool(re.search(r"\b(?:continue|resume)\b", lowered))
            return RouteDecision("projects", complex=coordinated)
        if re.search(r"\b(?:start|run|execute)\b.*\bworkflow\b", lowered):
            return RouteDecision("workflow")
        if cls._is_computer(prompt):
            return RouteDecision("computer")
        if cls._is_browser(prompt):
            # The browser's own planner performs observe/act/observe/replan. The Agent
            # Manager can attach structured post-actions that only run after a verified
            # environment result exists.
            post_actions = []
            if re.search(r"\b(?:save|store|add)\b.*\bknowledge\b|\bremember\b.*\b(?:main points|findings|research|video)\b", lowered):
                post_actions.append("knowledge.ingest")
            if re.search(r"\b(?:create|prepare|write|generate)\b.*\breport\b", lowered):
                post_actions.append("documents.report")
            return RouteDecision(
                "browser",
                complex=len(re.findall(r"\b(?:and|then|after that)\b", lowered)) >= 2 or bool(post_actions),
                post_actions=tuple(post_actions),
            )
        return RouteDecision("chat")

    def _task(self, conversation: Conversation, prompt: str, agent_identifier: str, *, parent=None, status="running") -> AgentTask:
        agent = AgentRegistry.ensure_record(self.user, agent_identifier)
        return AgentTask.objects.create(
            owner=self.user, agent=agent, parent_task=parent, conversation=conversation,
            name=prompt[:255], title=prompt[:255], description=prompt, request_text=prompt,
            status=status, category="orchestrated", started_at=timezone.now() if status == "running" else None,
            current_operation="Routing request" if status == "running" else "Queued",
            input_payload={"source": self.source, "section": self.section, "voice_session_id": self.voice_session_id},
        )

    def _complete_task(self, task: AgentTask, result: AgentResult) -> None:
        task.status = result.status if result.status in {"queued", "running", "completed", "failed", "waiting", "cancelled"} else "completed"
        task.output_payload = result.as_dict()
        task.progress = 100 if task.status == "completed" else max(task.progress, 15 if task.status in {"queued", "running"} else task.progress)
        task.current_operation = (
            "Completed" if task.status == "completed" else
            "Waiting for user" if task.status == "waiting" else
            "Running in background" if task.status in {"queued", "running"} else
            "Cancelled" if task.status == "cancelled" else "Failed"
        )
        task.error_message = "; ".join(str(item.get("detail") or item.get("code") or item) for item in result.errors)[:4000]
        task.completed_at = timezone.now() if task.status in {"completed", "failed", "cancelled"} else None
        task.save(update_fields=["status", "output_payload", "progress", "current_operation", "error_message", "completed_at", "updated_at"])

    def _run_agent(self, task: AgentTask, prompt: str, context: AgentContext) -> AgentResult:
        definition = AgentRegistry.get(task.agent.identifier)
        if not definition.handler:
            return AgentResult(status="failed", errors=[{"code": "agent_unavailable", "detail": f"{definition.name} is unavailable."}])
        available_tools = set(ToolExecutor.available_handlers())
        missing_tools = [item for item in definition.required_tools if item not in available_tools]
        if missing_tools:
            logger.error("agent_dependency_missing", extra={"echo_event": {"agent": definition.identifier, "task_id": str(task.pk), "missing_tools": missing_tools}})
            return AgentResult(
                status="failed",
                result={"content": f"{definition.name} is unavailable because required tools are not registered.", "route": f"agent.{definition.identifier}.dependency_unavailable", "data": {"missing_tools": missing_tools}},
                errors=[{"code": "missing_tool", "detail": f"Required tools are unavailable: {', '.join(missing_tools)}"}],
            )
        granted = set(_permission_names(self.user))
        missing_permissions = [item for item in definition.required_permissions if "*" not in granted and item not in granted and not self.user.has_perm(item)]
        if missing_permissions:
            return AgentResult(
                status="failed",
                result={"content": f"{definition.name} is not authorized for this account.", "route": f"agent.{definition.identifier}.permission_denied", "data": {}},
                errors=[{"code": "permission_denied", "detail": f"Required permissions: {', '.join(missing_permissions)}"}],
            )
        logger.info("agent_selected", extra={"echo_event": {"agent": definition.identifier, "task_id": str(task.pk), "source": self.source}})
        task.current_operation = f"{definition.name} working"
        task.progress = max(task.progress, 15)
        task.save(update_fields=["current_operation", "progress", "updated_at"])
        AgentMessageBus.send(user=self.user, task=task, sender=None, recipient=task.agent, message_type="assignment", payload={"prompt": prompt, "context": context.scoped(definition.context_scopes)})
        try:
            result = definition.handler(user=self.user, prompt=prompt, context=context, task=task, source=self.source, section=self.section)
        except Exception as exc:
            result = AgentResult(status="failed", errors=[{"code": exc.__class__.__name__, "detail": str(exc)}], result={"content": f"{definition.name} failed: {exc}", "route": f"agent.{definition.identifier}.failed", "data": {}})
        AgentMessageBus.send(user=self.user, task=task, sender=task.agent, recipient=None, message_type="result", payload=result.as_dict())
        logger.info("agent_result", extra={"echo_event": {"agent": definition.identifier, "task_id": str(task.pk), "status": result.status, "error_count": len(result.errors)}})
        self._complete_task(task, result)
        return result

    def _resolve_project_for_prompt(self, prompt: str, conversation: Conversation):
        """Resolve an unambiguous owner-scoped project before coordinated planning.

        Conversation context wins. Natural-language project names are used only when a
        single match exists; ambiguous matches remain unresolved for the Project Agent
        to present to the user instead of guessing.
        """
        try:
            from django.db.models import Q
            from echo.apps.projects.models import Project

            current_id = str((conversation.data or {}).get("current_project_id") or "").strip()
            if current_id:
                current = _owned(Project, self.user).filter(pk=current_id).first()
                if current:
                    return current
            match = re.search(r"\b(?:continue|resume|open)\s+(?:my\s+|the\s+)?(.+?)\s+project\b", prompt, re.I)
            if not match:
                return None
            phrase = re.sub(r"\s+", " ", match.group(1)).strip(" .,:;-_")
            if not phrase or phrase.casefold() in {"this", "current", "active"}:
                return None
            matches = list(
                _owned(Project, self.user)
                .filter(Q(title__icontains=phrase) | Q(name__icontains=phrase))
                .order_by("-updated_at")[:2]
            )
            return matches[0] if len(matches) == 1 else None
        except Exception:
            return None

    @staticmethod
    def _to_command_result(agent_result: AgentResult, task: AgentTask, conversation: Conversation, message: Message | None = None) -> CommandResult:
        payload = agent_result.result or {}
        data = dict(payload.get("data") or {})
        data.update({"agent_task_id": str(task.pk), "agent": task.agent.identifier if task.agent else "", "agent_result": agent_result.as_dict()})
        result = CommandResult(
            content=str(payload.get("content") or ("Completed." if agent_result.status == "completed" else "The operation could not be completed.")),
            route=str(payload.get("route") or f"agent.{task.agent.identifier if task.agent else 'manager'}"),
            status=agent_result.status,
            conversation=conversation,
            message=message,
            data=data,
            requires_configuration=bool(payload.get("requires_configuration", False)),
            configure_url=str(payload.get("configure_url") or ""),
            needs_confirmation=bool(payload.get("needs_confirmation", False)),
            memory_candidate=str(payload.get("memory_candidate") or ""),
            latency=int(payload.get("latency") or 0),
        )
        return result

    def execute(self, prompt: str, *, conversation_id: str | None = None) -> CommandResult:
        prompt = str(prompt or "").strip()
        if not prompt:
            raise CommandError("Enter a command for Echo.")
        if len(prompt) > 20_000:
            raise CommandError("Command is too long.")
        conversation = _ensure_conversation(self.user, prompt, conversation_id, self.source, self.section)
        user_message = _save_message(self.user, conversation, "user", prompt, input_mode=self.source, section=self.section, orchestrated=True)
        normalized_control = re.sub(r"\s+", " ", re.sub(r"[^a-z ]+", " ", prompt.casefold())).strip()
        cancellation_phrases = {"cancel that", "stop what you are doing", "stop what you re doing", "cancel current task", "cancel the current task", "stop", "echo stop"}
        if normalized_control in cancellation_phrases:
            cancelled = self.cancel_latest(self.user)
            # A bare voice "Stop" is contextual: cancel active work first. If Echo has
            # nothing cancellable, let the normal voice-control route interpret it as
            # "stop listening" and return to wake-word mode. Explicit cancellation
            # phrases always produce a cancellation result.
            bare_voice_stop = self.source == "voice" and normalized_control in {"stop", "echo stop"}
            if cancelled or not bare_voice_stop:
                content = "Cancellation requested." if cancelled else "There is no cancellable Echo operation running."
                assistant = _save_message(self.user, conversation, "assistant", content, route="agent.cancel", status="completed", cancelled_task_id=str(cancelled.pk) if cancelled else None)
                return CommandResult(
                    content=content, route="agent.cancel", status="completed", conversation=conversation, message=assistant,
                    data={"user_message_id": str(user_message.pk), "cancelled_task_id": str(cancelled.pk) if cancelled else None},
                )
        decision = self.decide(prompt)
        if decision.clarification:
            assistant = _save_message(self.user, conversation, "assistant", decision.clarification, route="agent.clarification", status="waiting", intent=decision.intent, confidence=decision.confidence)
            return CommandResult(
                content=decision.clarification, route="agent.clarification", status="waiting", conversation=conversation, message=assistant,
                data={"user_message_id": str(user_message.pk), "intent": decision.intent, "confidence": decision.confidence, "needs_clarification": True},
                needs_confirmation=True,
            )
        resolved_project = self._resolve_project_for_prompt(prompt, conversation) if decision.agent in {"projects", "planner"} or decision.complex else None

        # The manager owns a durable parent record for every user objective. Delegated
        # agent work is represented by child tasks, so coordination/cancellation/status
        # remain visible even when the specialized capability executes asynchronously.
        parent = AgentTask.objects.create(
            owner=self.user, agent=None, conversation=conversation, project=resolved_project, name=prompt[:255], title=prompt[:255],
            description=prompt, request_text=prompt, status="running", category="orchestration_root",
            started_at=timezone.now(), current_operation="Selecting agent", progress=5,
            input_payload={"source": self.source, "section": self.section, "voice_session_id": self.voice_session_id, "intent": decision.intent, "routing": dict(decision.metadata or {}), "routing_confidence": decision.confidence},
        )
        if resolved_project:
            conversation.data = {**(conversation.data or {}), "current_project_id": str(resolved_project.pk)}
            conversation.save(update_fields=["data", "updated_at"])
        if decision.complex and decision.agent != "planner":
            planner_task = self._task(conversation, prompt, "planner", parent=parent)
            if resolved_project:
                planner_task.project = resolved_project
                planner_task.save(update_fields=["project", "updated_at"])
            planner_context = AgentContextBuilder.build(
                self.user, prompt, conversation=conversation, voice_session_id=self.voice_session_id, task=planner_task
            )
            planner_result = self._run_agent(planner_task, prompt, planner_context)
            AgentMessageBus.send(
                user=self.user, task=planner_task, sender=planner_task.agent, recipient=None,
                message_type="plan_ready", payload={"for_agent": decision.agent, "plan": planner_result.as_dict()},
            )
        task = self._task(conversation, prompt, decision.agent, parent=parent)
        if decision.metadata:
            task.input_payload = {**(task.input_payload or {}), "routing": dict(decision.metadata), "intent": decision.intent, "routing_confidence": decision.confidence}
            task.save(update_fields=["input_payload", "updated_at"])
        if resolved_project:
            task.project = resolved_project
            task.save(update_fields=["project", "updated_at"])
        if decision.post_actions:
            task.input_payload = {**(task.input_payload or {}), "post_actions": list(decision.post_actions)}
            task.save(update_fields=["input_payload", "updated_at"])
        parent.current_operation = f"Delegated to {task.agent.title or task.agent.identifier}" if task.agent else "Delegated"
        parent.progress = 10
        parent.save(update_fields=["current_operation", "progress", "updated_at"])

        context = AgentContextBuilder.build(self.user, prompt, conversation=conversation, voice_session_id=self.voice_session_id, task=task)
        result = self._run_agent(task, prompt, context)
        result_data = dict((result.result or {}).get("data") or {})
        resolved_project_id = str(result_data.get("project_id") or "").strip()
        if resolved_project_id:
            try:
                from echo.apps.projects.models import Project
                project = _owned(Project, self.user).filter(pk=resolved_project_id).first()
                if project:
                    task.project = project
                    task.save(update_fields=["project", "updated_at"])
                    parent.project = project
                    conversation.data = {**(conversation.data or {}), "current_project_id": str(project.pk)}
                    conversation.save(update_fields=["data", "updated_at"])
            except Exception:
                pass
        self._complete_task(parent, result)
        parent.output_payload = {**(parent.output_payload or {}), "child_task_id": str(task.pk), "agent": decision.agent}
        parent.save(update_fields=["output_payload", "project", "updated_at"])

        assistant = _save_message(self.user, conversation, "assistant", str(result.result.get("content") or ""), route=str(result.result.get("route") or f"agent.{decision.agent}"), status=result.status, agent_task_id=str(task.pk), parent_agent_task_id=str(parent.pk), agent=decision.agent, command_data=result.result.get("data") or {})
        command = self._to_command_result(result, task, conversation, assistant)
        command.data.setdefault("user_message_id", str(user_message.pk))
        command.data.setdefault("parent_agent_task_id", str(parent.pk))
        command.data.setdefault("child_agent_task_id", str(task.pk))
        return command

    @classmethod
    def cancel_latest(cls, user) -> AgentTask | None:
        task = _owned(AgentTask, user).filter(status__in=("queued", "running", "waiting")).order_by("-updated_at").first()
        if not task:
            return None
        root = task.parent_task or task
        targets = [root, *list(root.child_tasks.filter(status__in=("queued", "running", "waiting")))]
        for item in targets:
            item.cancel_requested = True
            if item.status in {"queued", "waiting"}:
                item.status = "cancelled"
                item.completed_at = timezone.now()
            item.current_operation = "Cancellation requested"
            item.save(update_fields=["cancel_requested", "status", "completed_at", "current_operation", "updated_at"])
            payload = item.output_payload or {}
            result_payload = payload.get("result") if isinstance(payload.get("result"), dict) else {}
            data_payload = result_payload.get("data") if isinstance(result_payload.get("data"), dict) else {}
            operation_id = str(payload.get("operation_id") or data_payload.get("operation_id") or "")
            if operation_id:
                try:
                    from echo.apps.internet.computer_use import ComputerUseOperationService
                    ComputerUseOperationService.cancel(user, operation_id)
                except Exception:
                    pass
        return root
