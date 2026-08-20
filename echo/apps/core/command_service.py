from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from typing import Any

from django.conf import settings
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from echo.apps.ai_engine.runtime import AIExecutionService
from echo.apps.chat.models import Conversation, Message


class CommandError(RuntimeError):
    pass


def _human_datetime(value) -> str:
    """Return a compact, platform-independent local date/time label."""
    local = timezone.localtime(value)
    hour = local.strftime("%I").lstrip("0") or "0"
    return f"{local.strftime('%b')} {local.day}, {hour}:{local.strftime('%M %p')}"


@dataclass
class CommandResult:
    content: str
    route: str = "chat"
    status: str = "completed"
    conversation: Conversation | None = None
    message: Message | None = None
    data: dict[str, Any] = field(default_factory=dict)
    requires_configuration: bool = False
    configure_url: str = ""
    needs_confirmation: bool = False
    memory_candidate: str = ""
    latency: int = 0

    def as_dict(self) -> dict[str, Any]:
        payload = {
            "ok": self.status == "completed",
            "status": self.status,
            "content": self.content,
            "route": self.route,
            "data": self.data,
            "requires_configuration": self.requires_configuration,
            "needs_confirmation": self.needs_confirmation,
            "memory_candidate": bool(self.memory_candidate),
            "latency": self.latency,
        }
        if self.conversation:
            payload["conversation_id"] = str(self.conversation.pk)
        if self.message:
            payload["message_id"] = str(self.message.pk)
        if self.configure_url:
            payload["configure_url"] = self.configure_url
        return payload


class EchoCommandService:
    """Route natural-language requests into Echo's existing capabilities.

    The router intentionally handles high-confidence operational commands with
    deterministic application services. Ambiguous requests are sent to the configured
    AI provider with owner-scoped context. It never fabricates tool execution or an AI
    response when a provider is unavailable.
    """

    TASK_CREATE_RE = re.compile(
        r"\b(?:create|add|make|schedule)\s+(?:a\s+)?task(?:\s+for\s+me)?(?:\s+to|\s+called|\s+named)?\s+(.+)",
        re.IGNORECASE,
    )
    TASK_COMPLETE_RE = re.compile(
        r"\b(?:mark|set|complete|finish)\s+(?:the\s+)?(.+?)(?:\s+task)?\s+(?:as\s+)?(?:complete|completed|done)\b",
        re.IGNORECASE,
    )
    REMEMBER_RE = re.compile(r"\bremember\s+(?:that\s+)?(.+)", re.IGNORECASE)
    RESEARCH_RE = re.compile(r"\b(?:research|investigate|look\s+up)\s+(.+)", re.IGNORECASE)
    WORKFLOW_RE = re.compile(r"\b(?:start|run|execute)\s+(?:the\s+)?(.+?)\s+workflow\b", re.IGNORECASE)
    PROJECT_CREATE_RE = re.compile(r"\b(?:create|start|make)\s+(?:a\s+)?project(?:\s+(?:called|named|for))?\s+(.+)", re.IGNORECASE)
    PROJECT_CONTINUE_RE = re.compile(r"\b(?:continue|resume|open)\s+(?:my\s+|the\s+)?(.+?)\s+project\b", re.IGNORECASE)
    AGENT_RE = re.compile(r"\b(?:ask|run|start|delegate\s+to)\s+(?:an?\s+)?agent(?:\s+to)?\s+(.+)", re.IGNORECASE)
    DOCUMENT_ANALYZE_RE = re.compile(r"\b(?:analyze|summarize|review)\s+(?:this|the|my)?\s*(?:document|file|pdf)?(?:\s+(.+))?", re.IGNORECASE)

    SECTION_ALIASES = {
        "home": "home",
        "dashboard": "home",
        "chat": "chat",
        "conversation": "chat",
        "voice": "voice",
        "project": "projects",
        "projects": "projects",
        "task": "tasks",
        "tasks": "tasks",
        "planner": "planner",
        "plan": "planner",
        "knowledge": "knowledge",
        "memory": "memory",
        "document": "documents",
        "documents": "documents",
        "browser": "browser",
        "research": "browser",
        "workflow": "workflows",
        "workflows": "workflows",
        "agent": "agents",
        "agents": "agents",
        "calendar": "calendar",
        "email": "email",
        "analytics": "analytics",
        "settings": "settings",
        "notifications": "notifications",
        "activity": "notifications",
        "code": "code",
    }

    def __init__(self, user, *, source: str = "text", section: str = "home"):
        self.user = user
        self.source = source
        self.section = section if section in self.SECTION_ALIASES.values() else "home"

    def _owned(self, model):
        names = {field.name for field in model._meta.fields}
        queryset = model.objects.all()
        if self.user.is_staff:
            return queryset
        if "owner" in names:
            return queryset.filter(owner=self.user)
        if "user" in names:
            return queryset.filter(user=self.user)
        if "actor" in names:
            return queryset.filter(actor=self.user)
        return queryset.none()

    def _ensure_conversation(self, prompt: str, conversation_id: str | None = None) -> Conversation:
        conversation = None
        if conversation_id:
            try:
                conversation = self._owned(Conversation).filter(pk=conversation_id).first()
            except (TypeError, ValueError):
                conversation = None
        if conversation:
            return conversation
        return Conversation.objects.create(
            owner=self.user,
            user=self.user,
            name=prompt[:80],
            title=prompt[:80],
            description=f"Started from Echo {self.source}",
            status="active",
            conversation_type="voice" if self.source == "voice" else "workspace",
            current_model=settings.AI_PROVIDER_MODEL,
            last_message_at=timezone.now(),
            data={"origin": self.section, "input_mode": self.source},
        )

    def _save_message(self, conversation: Conversation, role: str, content: str, **data) -> Message:
        message = Message.objects.create(
            owner=self.user,
            conversation=conversation,
            name=f"{role}_message",
            title=(content[:80] or role.title()),
            status="completed",
            sender=role,
            role=role,
            content=content,
            rendered_content=content,
            data=data,
        )
        conversation.last_message_at = timezone.now()
        conversation.save(update_fields=["last_message_at", "updated_at"])
        return message

    @staticmethod
    def _strip_time_words(value: str) -> str:
        patterns = (
            r"\s+today\b",
            r"\s+tomorrow\b",
            r"\s+next\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
            r"\s+at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?\b",
            r"\s+by\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?\b",
        )
        clean = value.strip().rstrip(".")
        for pattern in patterns:
            clean = re.sub(pattern, "", clean, flags=re.IGNORECASE)
        return re.sub(r"\s+", " ", clean).strip()

    @staticmethod
    def _parse_due_at(text: str):
        now = timezone.localtime()
        lowered = text.lower()
        due_date = None
        if "tomorrow" in lowered:
            due_date = now.date() + timedelta(days=1)
        elif "today" in lowered:
            due_date = now.date()
        else:
            weekdays = {
                "monday": 0,
                "tuesday": 1,
                "wednesday": 2,
                "thursday": 3,
                "friday": 4,
                "saturday": 5,
                "sunday": 6,
            }
            for name, target in weekdays.items():
                if f"next {name}" in lowered:
                    delta = (target - now.weekday()) % 7
                    due_date = now.date() + timedelta(days=delta or 7)
                    break
        if not due_date:
            return None
        hour, minute = 17, 0
        match = re.search(r"\b(?:at|by)\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", lowered)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2) or 0)
            suffix = match.group(3)
            if suffix == "pm" and hour < 12:
                hour += 12
            elif suffix == "am" and hour == 12:
                hour = 0
            hour = max(0, min(hour, 23))
            minute = max(0, min(minute, 59))
        naive = datetime.combine(due_date, time(hour, minute))
        return timezone.make_aware(naive, timezone.get_current_timezone())

    def _create_task(self, prompt: str, match: re.Match, conversation: Conversation) -> CommandResult:
        from echo.apps.tasks.models import Task, TaskActivity

        raw_title = match.group(1).strip()
        title = self._strip_time_words(raw_title)
        if not title:
            raise CommandError("Tell Echo what the task should be called.")
        due_at = self._parse_due_at(raw_title)
        priority = "high" if any(word in prompt.lower() for word in ("urgent", "important", "high priority")) else "normal"
        task = Task.objects.create(
            owner=self.user,
            name=title,
            title=title,
            description=f"Created through {self.source} command.",
            status="active",
            category="voice" if self.source == "voice" else "command",
            configuration={
                "due_at": due_at.isoformat() if due_at else None,
                "priority": priority,
                "source": self.source,
                "conversation_id": str(conversation.pk),
            },
            data={"command": prompt},
        )
        TaskActivity.objects.create(
            owner=self.user,
            name="task_created",
            title=f"Created {title}",
            description=f"Task created through Echo {self.source}.",
            status="completed",
            category="creation",
            configuration={"task_id": str(task.pk), "conversation_id": str(conversation.pk)},
        )
        due_phrase = f" for {_human_datetime(due_at)}" if due_at else ""
        return CommandResult(
            content=f"Created the task “{title}”{due_phrase}.",
            route="tasks.create",
            data={"task_id": str(task.pk), "task_title": title, "due_at": due_at.isoformat() if due_at else None},
        )

    def _list_tasks(self) -> CommandResult:
        from echo.apps.tasks.models import Task

        tasks = list(self._owned(Task).exclude(status__in=("completed", "archived")).order_by("-updated_at")[:8])
        if not tasks:
            return CommandResult(content="You have no active tasks.", route="tasks.list", data={"tasks": []})
        lines = [f"{index}. {task.title or task.name}" for index, task in enumerate(tasks, 1)]
        return CommandResult(
            content="Your active tasks are:\n" + "\n".join(lines),
            route="tasks.list",
            data={"tasks": [{"id": str(task.pk), "title": task.title or task.name, "status": task.status} for task in tasks]},
        )

    def _complete_task(self, match: re.Match) -> CommandResult:
        from echo.apps.tasks.models import Task, TaskActivity

        phrase = match.group(1).strip()
        queryset = self._owned(Task).exclude(status__in=("completed", "archived"))
        exact = queryset.filter(Q(title__iexact=phrase) | Q(name__iexact=phrase)).first()
        matches = list(queryset.filter(Q(title__icontains=phrase) | Q(name__icontains=phrase)).order_by("-updated_at")[:4])
        task = exact or (matches[0] if len(matches) == 1 else None)
        if not task:
            if matches:
                return CommandResult(
                    content="I found several matching tasks. Choose one before I change its status.",
                    route="tasks.complete",
                    status="waiting",
                    needs_confirmation=True,
                    data={"matches": [{"id": str(item.pk), "title": item.title or item.name} for item in matches]},
                )
            return CommandResult(content=f"I could not find an active task matching “{phrase}”.", route="tasks.complete", status="not_found")
        task.status = "completed"
        configuration = dict(task.configuration or {})
        configuration["completed_at"] = timezone.now().isoformat()
        task.configuration = configuration
        task.save(update_fields=["status", "configuration", "updated_at"])
        TaskActivity.objects.create(
            owner=self.user,
            name="task_completed",
            title=f"Completed {task.title or task.name}",
            status="completed",
            category="completion",
            configuration={"task_id": str(task.pk), "source": self.source},
        )
        return CommandResult(
            content=f"Marked “{task.title or task.name}” complete.",
            route="tasks.complete",
            data={"task_id": str(task.pk)},
        )

    def _plan_day(self, conversation: Conversation) -> CommandResult:
        from echo.apps.planner.models import ExecutionPlan, PlanStep
        from echo.apps.tasks.models import Task

        tasks = list(self._owned(Task).exclude(status__in=("completed", "archived")).order_by("-updated_at")[:6])
        plan = ExecutionPlan.objects.create(
            owner=self.user,
            name=f"Work plan {timezone.localdate().isoformat()}",
            title=f"Work plan for {timezone.localdate().strftime('%A, %B')} {timezone.localdate().day}",
            description="A task-backed plan generated by Echo from the current execution queue.",
            status="active",
            category="daily",
            configuration={"conversation_id": str(conversation.pk), "source": self.source, "task_count": len(tasks)},
        )
        step_payload = []
        for index, task in enumerate(tasks, 1):
            step = PlanStep.objects.create(
                owner=self.user,
                name=task.title or task.name,
                title=task.title or task.name,
                description=task.description,
                status="active",
                category="task",
                configuration={"plan_id": str(plan.pk), "task_id": str(task.pk), "order": index},
            )
            step_payload.append({"id": str(step.pk), "title": step.title, "task_id": str(task.pk)})
        if not tasks:
            content = "I created an empty work plan. Add tasks and Echo can sequence them into the plan."
        else:
            content = "I created today’s plan from your active tasks:\n" + "\n".join(
                f"{index}. {task.title or task.name}" for index, task in enumerate(tasks, 1)
            )
        return CommandResult(content=content, route="planner.create", data={"plan_id": str(plan.pk), "steps": step_payload})

    def _start_workflow(self, match: re.Match) -> CommandResult:
        from echo.apps.workflow_engine.models import Workflow, WorkflowExecution, ExecutionEvent

        phrase = match.group(1).strip()
        matches = list(self._owned(Workflow).filter(Q(title__icontains=phrase) | Q(name__icontains=phrase)).order_by("-updated_at")[:4])
        if not matches:
            return CommandResult(content=f"No workflow matched “{phrase}”.", route="workflows.start", status="not_found")
        if len(matches) > 1:
            return CommandResult(
                content="I found several matching workflows. Choose the one to run.",
                route="workflows.start",
                status="waiting",
                needs_confirmation=True,
                data={"matches": [{"id": str(item.pk), "title": item.title or item.name} for item in matches]},
            )
        workflow = matches[0]
        execution = WorkflowExecution.objects.create(
            owner=self.user,
            name=f"Run: {workflow.title or workflow.name}",
            title=f"Run: {workflow.title or workflow.name}",
            description="Queued through Echo command routing.",
            status="queued",
            category="command",
            configuration={"workflow_id": str(workflow.pk), "source": self.source, "approval_state": "not_required"},
        )
        ExecutionEvent.objects.create(
            owner=self.user,
            name="workflow_queued",
            title=f"Queued {workflow.title or workflow.name}",
            status="completed",
            category="queue",
            configuration={"workflow_id": str(workflow.pk), "execution_id": str(execution.pk)},
        )
        from echo.apps.workflow_engine.tasks import execute_workflow

        task = None
        dispatch_error = ""
        try:
            task = execute_workflow.delay(str(workflow.pk), str(self.user.pk), {}, str(execution.pk))
        except Exception as exc:
            dispatch_error = str(exc)
        execution.refresh_from_db()
        if dispatch_error and execution.status == "queued":
            execution.status = "failed"
            execution.configuration = {
                **(execution.configuration or {}),
                "error": dispatch_error,
                "error_type": "DispatchError",
                "finished_at": timezone.now().isoformat(),
            }
            execution.save(update_fields=["status", "configuration", "updated_at"])
        status_value = execution.status
        if status_value == "completed":
            content = f"Completed the workflow “{workflow.title or workflow.name}”."
        elif status_value == "failed":
            content = f"The workflow “{workflow.title or workflow.name}” failed: {(execution.configuration or {}).get('error', 'execution error')}"
        else:
            content = f"Started the workflow “{workflow.title or workflow.name}”."
        return CommandResult(
            content=content,
            route="workflows.start",
            status="failed" if status_value == "failed" else "completed",
            data={
                "workflow_id": str(workflow.pk),
                "execution_id": str(execution.pk),
                "execution_status": status_value,
                "task_id": str(getattr(task, "id", "") or ""),
            },
        )

    def _research(self, query: str) -> CommandResult:
        from echo.apps.internet.models import SearchQuery, SearchResult
        from echo.apps.internet.search_provider import ConfiguredSearchProvider, SearchProviderError

        query = query.strip().rstrip(".")
        search = SearchQuery.objects.create(
            owner=self.user,
            user=self.user,
            name=query[:255],
            title=query[:255],
            description="Research requested through Echo command routing.",
            status="running" if settings.INTERNET_SEARCH_ENDPOINT else "waiting",
            query=query,
            search_type="web",
            language="en",
            safe_search="strict",
            requested_at=timezone.now(),
            data={"source": self.source},
        )
        if not settings.INTERNET_SEARCH_ENDPOINT:
            return CommandResult(
                content="The research request is saved, but a search provider must be connected before Echo can execute it.",
                route="browser.research",
                status="waiting",
                requires_configuration=True,
                configure_url=reverse("workspace", kwargs={"section": "settings"}),
                data={"search_query_id": str(search.pk)},
            )
        try:
            records = ConfiguredSearchProvider().search(query, limit=8)
        except SearchProviderError as exc:
            search.status = "failed"
            search.data = {**(search.data or {}), "error": str(exc)}
            search.save(update_fields=["status", "data", "updated_at"])
            return CommandResult(content=f"Research could not complete: {exc}", route="browser.research", status="failed", data={"search_query_id": str(search.pk)})
        results = []
        for index, record in enumerate(records, 1):
            result = SearchResult.objects.create(
                owner=self.user,
                name=str(record.get("title") or record.get("name") or query)[:255],
                title=str(record.get("title") or record.get("name") or query)[:255],
                description=str(record.get("snippet") or record.get("description") or ""),
                status="completed",
                query=query,
                url=str(record.get("url") or ""),
                snippet=str(record.get("snippet") or record.get("description") or ""),
                domain=str(record.get("domain") or "")[:255],
                rank=index,
                relevance_score=float(record.get("score") or 0),
                retrieved_at=timezone.now(),
                data={"search_query_id": str(search.pk), "provider_record": record},
            )
            results.append({"id": str(result.pk), "title": result.title, "url": result.url, "snippet": result.snippet})
        search.status = "completed"
        search.save(update_fields=["status", "updated_at"])
        return CommandResult(content=f"Research completed with {len(results)} results for “{query}”.", route="browser.research", data={"search_query_id": str(search.pk), "results": results})

    def _create_project(self, match: re.Match, conversation: Conversation) -> CommandResult:
        from echo.apps.projects.models import Project, ProjectActivity

        title = match.group(1).strip().rstrip(".")
        if not title:
            return CommandResult(content="Tell me what the project should be called.", route="projects.create", status="waiting")
        project = Project.objects.create(
            owner=self.user,
            name=title[:255],
            title=title[:255],
            description="Created through Echo's universal command center.",
            status="active",
            category="workspace",
            configuration={"conversation_id": str(conversation.pk), "source": self.source},
        )
        ProjectActivity.objects.create(
            owner=self.user,
            name="project_created",
            title=f"Created {project.title}",
            status="completed",
            category="creation",
            configuration={"project_id": str(project.pk), "conversation_id": str(conversation.pk)},
        )
        return CommandResult(
            content=f"Created the project “{project.title}”.",
            route="projects.create",
            data={"project_id": str(project.pk), "url": reverse("workspace", kwargs={"section": "projects"})},
        )

    def _continue_project(self, match: re.Match) -> CommandResult:
        from echo.apps.projects.models import Project, ProjectActivity
        from echo.apps.tasks.models import Task

        phrase = match.group(1).strip()
        projects = list(self._owned(Project).filter(Q(title__icontains=phrase) | Q(name__icontains=phrase)).order_by("-updated_at")[:4])
        if not projects:
            return CommandResult(content=f"I could not find a project matching “{phrase}”.", route="projects.continue", status="not_found")
        if len(projects) > 1:
            return CommandResult(
                content="I found several matching projects. Choose one to continue.",
                route="projects.continue",
                status="waiting",
                needs_confirmation=True,
                data={"matches": [{"id": str(item.pk), "title": item.title or item.name} for item in projects]},
            )
        project = projects[0]
        task_candidates = self._owned(Task).exclude(status__in=("completed", "archived")).order_by("-updated_at")[:100]
        tasks = [item for item in task_candidates if str((item.configuration or {}).get("project_id") or "") == str(project.pk)][:6]
        activity = list(self._owned(ProjectActivity).filter(configuration__project_id=str(project.pk)).order_by("-created_at")[:5])
        project.configuration = {**(project.configuration or {}), "last_opened_at": timezone.now().isoformat()}
        project.save(update_fields=["configuration", "updated_at"])
        lines = [f"Project: {project.title or project.name}"]
        if project.description:
            lines.append(project.description[:500])
        if tasks:
            lines.append("Active tasks: " + "; ".join(item.title or item.name for item in tasks))
        if activity:
            lines.append("Recent activity: " + "; ".join(item.title or item.name for item in activity[:3]))
        return CommandResult(
            content="\n".join(lines),
            route="projects.continue",
            data={
                "project_id": str(project.pk),
                "tasks": [{"id": str(item.pk), "title": item.title or item.name, "status": item.status} for item in tasks],
                "url": reverse("workspace", kwargs={"section": "projects"}),
            },
        )

    def _delegate_agent(self, match: re.Match, conversation: Conversation) -> CommandResult:
        from echo.apps.agent_manager.models import Agent, AgentTask

        instruction = match.group(1).strip().rstrip(".")
        agents = list(self._owned(Agent).filter(status="active").order_by("-updated_at")[:2])
        if not agents:
            return CommandResult(
                content="The request is saved, but no active agent is configured to accept it.",
                route="agents.delegate",
                status="waiting",
                requires_configuration=True,
                configure_url=reverse("workspace", kwargs={"section": "agents"}),
            )
        if len(agents) > 1:
            return CommandResult(
                content="Choose which active agent should receive this assignment.",
                route="agents.delegate",
                status="waiting",
                needs_confirmation=True,
                data={"matches": [{"id": str(item.pk), "title": item.title or item.name} for item in agents]},
            )
        agent = agents[0]
        task = AgentTask.objects.create(
            owner=self.user,
            name=instruction[:255],
            title=instruction[:255],
            description=instruction,
            status="queued",
            category="command",
            configuration={"agent_id": str(agent.pk), "conversation_id": str(conversation.pk), "source": self.source},
        )
        return CommandResult(
            content=f"Queued the assignment for {agent.title or agent.name}. Its execution remains visible in Agents.",
            route="agents.delegate",
            data={"agent_id": str(agent.pk), "agent_task_id": str(task.pk), "url": reverse("workspace", kwargs={"section": "agents"})},
        )

    def _analyze_document(self, match: re.Match) -> CommandResult:
        from echo.apps.documents.models import Document, DocumentContent

        phrase = str(match.group(1) or "").strip().rstrip(".")
        queryset = self._owned(Document).order_by("-updated_at")
        if phrase:
            queryset = queryset.filter(Q(title__icontains=phrase) | Q(name__icontains=phrase))
        document = queryset.first()
        if not document:
            return CommandResult(content="Upload a document first, then ask Echo to analyze it.", route="documents.analyze", status="waiting", data={"url": reverse("workspace", kwargs={"section": "documents"})})
        if document.status in {"uploaded", "processing"}:
            return CommandResult(content=f"“{document.title or document.name}” is still being processed. Echo will surface it when indexing completes.", route="documents.analyze", status="waiting", data={"document_id": str(document.pk), "document_status": document.status})
        if document.status == "failed":
            return CommandResult(content=f"Echo could not process “{document.title or document.name}”: {(document.configuration or {}).get('processing_error', 'extraction failed')}", route="documents.analyze", status="failed", data={"document_id": str(document.pk)})
        content_id = str((document.configuration or {}).get("document_content_id") or "")
        content = self._owned(DocumentContent).filter(pk=content_id).first() if content_id else None
        if not content or not content.description:
            return CommandResult(content=f"No extracted content is available for “{document.title or document.name}”.", route="documents.analyze", status="failed", data={"document_id": str(document.pk)})
        source_text = content.description[:40_000]
        if settings.AI_PROVIDER_BASE_URL and settings.AI_PROVIDER_API_KEY:
            messages = [
                {"role": "system", "content": "Analyze only the supplied document text. Give a concise executive summary, key findings, risks, and next actions. Do not invent missing facts."},
                {"role": "user", "content": f"Document: {document.title or document.name}\n\n{source_text}"},
            ]
            request_record, response_record, _ = AIExecutionService.generate(self.user, messages, model=settings.AI_PROVIDER_MODEL or None)
            answer = response_record.content
            latency = request_record.latency
        else:
            paragraphs = [item.strip() for item in source_text.split("\n\n") if item.strip()]
            preview = "\n\n".join(paragraphs[:4])[:1800]
            answer = f"Indexed document: {document.title or document.name}\n\n{preview}"
            latency = 0
        return CommandResult(
            content=answer,
            route="documents.analyze",
            data={"document_id": str(document.pk), "knowledge_document_id": (document.configuration or {}).get("knowledge_document_id"), "url": reverse("workspace", kwargs={"section": "documents"})},
            latency=latency,
        )

    def _navigate(self, prompt: str) -> CommandResult | None:
        match = re.search(r"\b(?:open|go\s+to|show\s+me)\s+(?:my\s+|the\s+)?([a-z\s]+?)\s*(?:workspace|page|screen)?\s*$", prompt, re.IGNORECASE)
        if not match:
            return None
        phrase = match.group(1).strip().lower()
        section = self.SECTION_ALIASES.get(phrase) or self.SECTION_ALIASES.get(phrase.rstrip("s"))
        if not section:
            return None
        return CommandResult(
            content=f"Opening {section.title()}.",
            route="navigation",
            data={"section": section, "url": reverse("workspace", kwargs={"section": section})},
        )

    def _knowledge_context(self, prompt: str) -> list[dict[str, str]]:
        from echo.apps.knowledge.models import KnowledgeDocument
        from echo.apps.memory.models import Memory

        stop_words = {"what", "know", "about", "this", "that", "show", "find", "tell", "echo", "have", "does", "from", "with", "your", "project"}
        terms = [term for term in re.findall(r"[a-zA-Z0-9_-]{3,}", prompt.lower()) if term not in stop_words][:8]
        expression = Q()
        for term in terms:
            expression |= Q(title__icontains=term) | Q(name__icontains=term) | Q(description__icontains=term)
        memory_expression = Q()
        for term in terms:
            memory_expression |= Q(title__icontains=term) | Q(summary__icontains=term) | Q(content__icontains=term)
        if not terms or "what do i know" in prompt.lower() or "knowledge base" in prompt.lower():
            knowledge_rows = self._owned(KnowledgeDocument).order_by("-updated_at")[:5]
            memory_rows = self._owned(Memory).order_by("-importance_score", "-updated_at")[:5]
        else:
            knowledge_rows = self._owned(KnowledgeDocument).filter(expression).order_by("-updated_at")[:5]
            memory_rows = self._owned(Memory).filter(memory_expression).order_by("-importance_score", "-updated_at")[:5]
        context = []
        for row in knowledge_rows:
            context.append({"type": "knowledge", "id": str(row.pk), "title": row.title or row.name, "content": row.description[:1200]})
        for row in memory_rows:
            context.append({"type": "memory", "id": str(row.pk), "title": row.title or row.summary or row.name, "content": (row.content or row.description)[:1200]})
        return context

    def _knowledge_answer(self, prompt: str) -> CommandResult | None:
        lowered = prompt.lower()
        is_knowledge_request = any(
            phrase in lowered
            for phrase in ("what do i know", "knowledge base", "search my knowledge", "find in my knowledge", "what have you learned", "what do you remember")
        )
        if not is_knowledge_request:
            return None
        context = self._knowledge_context(prompt)
        if not context:
            return CommandResult(content="I could not find matching knowledge or approved memory in your workspace.", route="knowledge.search", data={"sources": []})
        if settings.AI_PROVIDER_BASE_URL and settings.AI_PROVIDER_API_KEY:
            messages = [
                {
                    "role": "system",
                    "content": "Answer only from the supplied Echo workspace sources. State uncertainty and do not invent missing facts. Cite sources by their provided title.",
                },
                {"role": "user", "content": f"Question: {prompt}\n\nWorkspace sources:\n{context}"},
            ]
            request_record, response_record, _ = AIExecutionService.generate(self.user, messages, model=settings.AI_PROVIDER_MODEL or None)
            return CommandResult(content=response_record.content, route="knowledge.search", data={"sources": context}, latency=request_record.latency)
        lines = [f"• {item['title']}: {item['content'][:240]}" for item in context[:6]]
        return CommandResult(
            content="Here is the matching workspace context:\n" + "\n".join(lines),
            route="knowledge.search",
            data={"sources": context},
        )

    def _general_ai(self, prompt: str, conversation: Conversation) -> CommandResult:
        if not settings.AI_PROVIDER_BASE_URL or not settings.AI_PROVIDER_API_KEY:
            return CommandResult(
                content="Your message is saved, but Echo needs an OpenAI-compatible AI provider for a generated response.",
                route="chat.generate",
                status="waiting",
                requires_configuration=True,
                configure_url=reverse("workspace", kwargs={"section": "settings"}),
            )
        history = Message.objects.filter(owner=self.user, conversation=conversation).order_by("created_at")[:30]
        context = self._knowledge_context(prompt)
        messages = [
            {
                "role": "system",
                "content": (
                    "You are Echo, an enterprise AI operating partner. Be direct and useful. "
                    "Use supplied workspace context when relevant. Never claim an action ran unless the command result says it ran. "
                    "Do not expose hidden chain-of-thought; provide concise execution status and conclusions."
                ),
            }
        ]
        if context:
            messages.append({"role": "system", "content": f"Owner-scoped workspace context: {context}"})
        messages.extend({"role": item.role or "user", "content": item.content} for item in history)
        request_record, response_record, _ = AIExecutionService.generate(self.user, messages, model=settings.AI_PROVIDER_MODEL or None)
        return CommandResult(content=response_record.content, route="chat.generate", latency=request_record.latency)


    def _computer_use(self, prompt: str, conversation: Conversation) -> CommandResult | None:
        from echo.apps.internet.computer_use import ComputerUseCommandRouter

        routed = ComputerUseCommandRouter.handle(
            self.user, prompt, conversation=conversation, source=self.source
        )
        if not routed:
            return None
        return CommandResult(
            content=str(routed.get("content") or ""),
            route=str(routed.get("route") or "computer_use"),
            status=str(routed.get("status") or "completed"),
            data=dict(routed.get("data") or {}),
            needs_confirmation=bool(routed.get("needs_confirmation", False)),
        )

    def _route(self, prompt: str, conversation: Conversation) -> CommandResult:
        lowered = prompt.lower().strip()
        normalized_voice_stop = re.sub(r"[^a-z ]+", " ", lowered)
        normalized_voice_stop = re.sub(r"\s+", " ", normalized_voice_stop).strip()
        if self.source == "voice" and normalized_voice_stop in {"echo", "hey echo", "hello echo"}:
            return CommandResult(content="I'm listening.", route="voice.wake", data={"voice_active": True})
        if self.source == "voice" and normalized_voice_stop in {
            "activate voice", "enable voice", "echo activate voice", "echo enable voice",
        }:
            return CommandResult(
                content="Voice is active.",
                route="voice.activate",
                data={"voice_action": "activate"},
            )
        if self.source == "voice" and normalized_voice_stop in {
            "stop", "echo stop", "stop listening", "echo stop listening",
            "disable voice", "echo disable voice", "go to sleep", "echo go to sleep",
        }:
            return CommandResult(
                content="I'll wait for you to say Echo.",
                route="voice.disable",
                data={"voice_action": "disable"},
            )
        if self.source == "voice" and normalized_voice_stop in {
            "shutdown voice", "shut down voice", "echo shutdown voice", "echo shut down voice",
            "shutdown echo voice", "shut down echo voice",
        }:
            return CommandResult(
                content="Voice is shut down.",
                route="voice.shutdown",
                data={"voice_action": "shutdown"},
            )
        if normalized_voice_stop in {"resume that", "continue that", "resume the browser task", "continue the browser task"}:
            from echo.apps.internet.models import ComputerUseOperation
            from echo.apps.internet.computer_use import ComputerUseOperationService
            operation = self._owned(ComputerUseOperation).filter(status__in=("waiting_user", "failed", "cancelled")).order_by("-updated_at").first()
            if not operation:
                return CommandResult(content="There is no interrupted computer-use task to resume.", route="computer_use.resume", status="not_found")
            operation, queue_id = ComputerUseOperationService.resume(self.user, operation.pk)
            return CommandResult(content="Resuming the computer-use task.", route="computer_use.resume", data={"operation_id": str(operation.pk), "queue_task_id": queue_id, "execution_status": operation.status})
        if normalized_voice_stop in {"cancel that", "stop what you are doing", "stop what you re doing", "cancel current task"}:
            from echo.apps.internet.models import ComputerUseOperation
            from echo.apps.internet.computer_use import ComputerUseOperationService
            operation = self._owned(ComputerUseOperation).filter(status__in=("queued", "running", "waiting_user", "cancelling")).order_by("-updated_at").first()
            if not operation:
                return CommandResult(content="There is no active computer-use task to cancel.", route="computer_use.cancel", status="not_found")
            operation = ComputerUseOperationService.cancel(self.user, operation.pk)
            return CommandResult(content="Cancellation requested.", route="computer_use.cancel", data={"operation_id": str(operation.pk), "execution_status": operation.status})
        navigation = self._navigate(prompt)
        if navigation:
            return navigation
        computer_use = self._computer_use(prompt, conversation)
        if computer_use:
            return computer_use
        project_continue = self.PROJECT_CONTINUE_RE.search(prompt)
        if project_continue:
            return self._continue_project(project_continue)
        project_create = self.PROJECT_CREATE_RE.search(prompt)
        if project_create:
            return self._create_project(project_create, conversation)
        document_analysis = self.DOCUMENT_ANALYZE_RE.search(prompt)
        if document_analysis and any(word in lowered for word in ("document", "file", "pdf")):
            return self._analyze_document(document_analysis)
        agent = self.AGENT_RE.search(prompt)
        if agent:
            return self._delegate_agent(agent, conversation)
        task_create = self.TASK_CREATE_RE.search(prompt)
        if task_create:
            return self._create_task(prompt, task_create, conversation)
        task_complete = self.TASK_COMPLETE_RE.search(prompt)
        if task_complete:
            return self._complete_task(task_complete)
        if any(phrase in lowered for phrase in ("show my active tasks", "list my tasks", "what are my tasks", "show active tasks")):
            return self._list_tasks()
        if any(phrase in lowered for phrase in ("plan my day", "plan my work", "prepare my day", "organize my work today")):
            return self._plan_day(conversation)
        workflow = self.WORKFLOW_RE.search(prompt)
        if workflow:
            return self._start_workflow(workflow)
        research = self.RESEARCH_RE.search(prompt)
        if research:
            return self._research(research.group(1))
        knowledge = self._knowledge_answer(prompt)
        if knowledge:
            return knowledge
        remember = self.REMEMBER_RE.search(prompt)
        if remember and self.source == "voice":
            candidate = remember.group(1).strip().rstrip(".")
            return CommandResult(
                content="I captured that as a memory candidate. Review and approve it before Echo stores it as permanent memory.",
                route="memory.candidate",
                status="waiting",
                memory_candidate=candidate,
                data={"candidate": candidate},
            )
        return self._general_ai(prompt, conversation)

    def execute(self, prompt: str, *, conversation_id: str | None = None) -> CommandResult:
        prompt = str(prompt or "").strip()
        if not prompt:
            raise CommandError("Enter a command for Echo.")
        if len(prompt) > 20_000:
            raise CommandError("Command is too long.")
        conversation = self._ensure_conversation(prompt, conversation_id)
        user_message = self._save_message(conversation, "user", prompt, input_mode=self.source, section=self.section)
        try:
            result = self._route(prompt, conversation)
        except Exception as exc:
            self._save_message(conversation, "system", f"Command failed: {exc}", route="error")
            raise
        result.conversation = conversation
        assistant = self._save_message(
            conversation,
            "assistant",
            result.content,
            route=result.route,
            status=result.status,
            command_data=result.data,
            requires_configuration=result.requires_configuration,
        )
        result.message = assistant
        result.data.setdefault("user_message_id", str(user_message.pk))
        return result
