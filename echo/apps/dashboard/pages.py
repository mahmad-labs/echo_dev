from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.db import models
from django.db.utils import OperationalError, ProgrammingError
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from echo.apps.core.command_service import CommandError
from echo.apps.agent_manager.orchestration import AgentManagerOrchestrator
from echo.apps.chat.models import Conversation, Message
from echo.apps.voice.models import SpeechTranscript, VoiceSession
from echo.apps.voice.providers import VoiceProviderRegistry
from echo.apps.voice.services import VoiceProfileService, VoiceSessionService


NAV_GROUPS = (
    (
        "Workspace",
        (
            ("home", "Home", "home"),
            ("chat", "Chat", "spark"),
            ("voice", "Voice", "mic"),
            ("projects", "Projects", "projects"),
            ("planner", "Planner", "planner"),
            ("tasks", "Tasks", "check"),
        ),
    ),
    (
        "Intelligence",
        (
            ("knowledge", "Knowledge", "knowledge"),
            ("memory", "Memory", "memory"),
            ("documents", "Documents", "document"),
            ("browser", "Browser", "globe"),
            ("analytics", "Analytics", "analytics"),
        ),
    ),
    (
        "Operations",
        (
            ("agents", "Agents", "agents"),
            ("workflows", "Workflows", "workflow"),
            ("calendar", "Calendar", "calendar"),
            ("email", "Email", "mail"),
            ("code", "Code", "code"),
        ),
    ),
    (
        "System",
        (
            ("notifications", "Activity", "bell"),
            ("settings", "Settings", "settings"),
        ),
    ),
)

SECTION_META = {
    "home": {
        "title": "Good morning",
        "eyebrow": "Adaptive workspace",
        "description": "Echo has assembled the context that matters now.",
        "icon": "home",
        "accent": "iris",
        "suggestions": (
            "Plan my highest-impact work",
            "Summarize what changed",
            "Find anything that needs attention",
        ),
    },
    "chat": {
        "title": "Conversation space",
        "eyebrow": "Think with Echo",
        "description": "A continuous workspace for questions, decisions, and creation.",
        "icon": "spark",
        "accent": "blue",
        "suggestions": ("Start a strategy session", "Turn notes into an action plan", "Challenge my assumptions"),
    },
    "voice": {
        "title": "Voice with Echo",
        "eyebrow": "A continuous conversation",
        "description": "Speak naturally, watch the live transcript, and continue the same conversation by voice or text.",
        "icon": "mic",
        "accent": "iris",
        "suggestions": ("Plan my work for today", "Show my active tasks", "What do I know about this project?"),
    },
    "knowledge": {
        "title": "Knowledge fabric",
        "eyebrow": "Connected understanding",
        "description": "Explore sources, relationships, and the knowledge Echo can use.",
        "icon": "knowledge",
        "accent": "sage",
        "suggestions": ("Map this topic", "Find conflicting sources", "Create a knowledge brief"),
    },
    "memory": {
        "title": "Workspace memory",
        "eyebrow": "What Echo remembers",
        "description": "Inspect, connect, and control the context carried across your work.",
        "icon": "memory",
        "accent": "rose",
        "suggestions": ("What have you learned about this project?", "Find related decisions", "Forget outdated context"),
    },
    "projects": {
        "title": "Project cockpit",
        "eyebrow": "Autonomous coordination",
        "description": "Outcomes, momentum, risks, and next moves in one living view.",
        "icon": "projects",
        "accent": "amber",
        "suggestions": ("Create a project plan", "Surface delivery risks", "Prepare a progress update"),
    },
    "planner": {
        "title": "Planning canvas",
        "eyebrow": "From intent to execution",
        "description": "Turn ambiguous goals into sequenced, dependency-aware plans.",
        "icon": "planner",
        "accent": "violet",
        "suggestions": ("Break down a goal", "Replan around this blocker", "Build a decision tree"),
    },
    "tasks": {
        "title": "Execution queue",
        "eyebrow": "Focus, not lists",
        "description": "A priority-aware view of what deserves attention and why.",
        "icon": "check",
        "accent": "mint",
        "suggestions": ("Prioritize my tasks", "Create tasks from this conversation", "Protect a focus block"),
    },
    "analytics": {
        "title": "Intelligence signals",
        "eyebrow": "Patterns over panels",
        "description": "Understand movement, anomalies, and the reasons behind the numbers.",
        "icon": "analytics",
        "accent": "cyan",
        "suggestions": ("Explain the biggest change", "Detect an anomaly", "Generate an executive brief"),
    },
    "browser": {
        "title": "Research browser",
        "eyebrow": "Search with memory",
        "description": "Investigate the web while Echo tracks sources, claims, and open questions.",
        "icon": "globe",
        "accent": "blue",
        "suggestions": ("Research a topic", "Compare trusted sources", "Monitor a website"),
    },
    "documents": {
        "title": "Document studio",
        "eyebrow": "Read, write, transform",
        "description": "A focused space where documents become active working context.",
        "icon": "document",
        "accent": "sand",
        "suggestions": ("Draft a document", "Summarize uploaded files", "Compare two versions"),
    },
    "settings": {
        "title": "System controls",
        "eyebrow": "Make Echo yours",
        "description": "Models, integrations, permissions, preferences, and trust controls.",
        "icon": "settings",
        "accent": "slate",
        "suggestions": ("Review connected services", "Audit permissions", "Configure an AI provider"),
    },
    "notifications": {
        "title": "Activity stream",
        "eyebrow": "Only what matters",
        "description": "Decisions, approvals, completions, and exceptions across Echo.",
        "icon": "bell",
        "accent": "rose",
        "suggestions": ("Summarize unread activity", "Show pending approvals", "Mute low-value updates"),
    },
    "email": {
        "title": "Communication studio",
        "eyebrow": "Inbox, understood",
        "description": "Threads organized by intent, urgency, and the action they require.",
        "icon": "mail",
        "accent": "sky",
        "suggestions": ("Draft a thoughtful reply", "Summarize important threads", "Find messages awaiting me"),
    },
    "calendar": {
        "title": "Time architecture",
        "eyebrow": "Protect what matters",
        "description": "Meetings, commitments, focus, and energy in one adaptive timeline.",
        "icon": "calendar",
        "accent": "amber",
        "suggestions": ("Find time for deep work", "Resolve scheduling conflicts", "Prepare me for today"),
    },
    "agents": {
        "title": "Agent constellation",
        "eyebrow": "Delegated intelligence",
        "description": "Specialized agents, their capabilities, assignments, and judgment boundaries.",
        "icon": "agents",
        "accent": "violet",
        "suggestions": ("Create a research agent", "Review agent performance", "Delegate this objective"),
    },
    "workflows": {
        "title": "Automation studio",
        "eyebrow": "Work that moves itself",
        "description": "Design, observe, and govern workflows as living systems.",
        "icon": "workflow",
        "accent": "mint",
        "suggestions": ("Automate a repeated process", "Diagnose a failed run", "Add an approval gate"),
    },
    "code": {
        "title": "Code workspace",
        "eyebrow": "Understand before changing",
        "description": "Explore systems, reason across files, and ship carefully with Echo.",
        "icon": "code",
        "accent": "cyan",
        "suggestions": ("Explain this codebase", "Review recent changes", "Plan a safe refactor"),
    },
}

DATA_SOURCES = {
    "home": (
        ("tasks", "Task", "tasks", "check"),
        ("projects", "Project", "projects", "projects"),
        ("documents", "Document", "documents", "document"),
        ("chat", "Conversation", "chat", "spark"),
    ),
    "chat": (("chat", "Conversation", "conversations", "spark"), ("chat", "Message", "messages", "message")),
    "voice": (("voice", "VoiceSession", "sessions", "mic"), ("voice", "SpeechTranscript", "transcripts", "message"), ("voice", "SpeechSynthesis", "responses", "pulse")),
    "knowledge": (("knowledge", "KnowledgeCollection", "collections", "collection"), ("knowledge", "KnowledgeDocument", "documents", "knowledge"), ("vector_database", "VectorIndex", "indexes", "nodes")),
    "memory": (("memory", "Memory", "memories", "memory"), ("memory", "MemoryRelationship", "relationships", "nodes"), ("memory", "WorkingMemory", "working_memory", "activity")),
    "projects": (("projects", "Project", "projects", "projects"), ("projects", "ProjectMilestone", "milestones", "flag"), ("projects", "ProjectActivity", "activity", "activity")),
    "planner": (("planner", "Goal", "goals", "target"), ("planner", "ExecutionPlan", "plans", "planner"), ("planner", "PlanStep", "steps", "check")),
    "tasks": (("tasks", "Task", "tasks", "check"), ("tasks", "Reminder", "reminders", "bell"), ("tasks", "TimeEntry", "time_entries", "clock")),
    "analytics": (("analytics", "MetricPoint", "metrics", "analytics"), ("analytics", "Report", "reports", "document"), ("analytics", "AnalyticsEvent", "events", "activity")),
    "browser": (("internet", "ComputerUseOperation", "operations", "activity"), ("internet", "BrowserSession", "sessions", "globe"), ("internet", "MediaUnderstanding", "media", "spark"), ("internet", "SearchQuery", "queries", "search")),
    "documents": (("documents", "Document", "documents", "document"), ("documents", "ProcessingJob", "jobs", "activity"), ("documents", "DocumentVersion", "versions", "history")),
    "settings": (("settings", "IntegrationSetting", "integrations", "plug"), ("settings", "UserSetting", "preferences", "sliders"), ("settings", "ConfigurationAudit", "audits", "shield")),
    "notifications": (("notifications", "Notification", "notifications", "bell"), ("notifications", "DeliveryLog", "deliveries", "send"), ("dashboard", "RecentActivity", "activity", "activity")),
    "email": (("email", "EmailThread", "threads", "mail"), ("email", "EmailDraft", "drafts", "edit"), ("email", "EmailAccount", "accounts", "at")),
    "calendar": (("calendar", "Event", "events", "calendar"), ("calendar", "TimeBlock", "blocks", "clock"), ("calendar", "AvailabilityRule", "availability", "shield")),
    "agents": (("agent_manager", "Agent", "agents", "agents"), ("agent_manager", "AgentTask", "assignments", "check"), ("agent_manager", "AgentPerformance", "performance", "analytics")),
    "workflows": (("workflow_engine", "Workflow", "workflows", "workflow"), ("workflow_engine", "WorkflowExecution", "executions", "pulse"), ("tool_manager", "Tool", "tools", "tool")),
    "code": (("code_assistant", "CodeProject", "projects", "code"), ("code_assistant", "SourceFile", "files", "file-code"), ("code_assistant", "CodeIssue", "issues", "alert")),
}

CREATE_TARGETS = {
    "chat": ("chat", "Conversation"),
    "knowledge": ("knowledge", "KnowledgeDocument"),
    "memory": ("memory", "Memory"),
    "projects": ("projects", "Project"),
    "planner": ("planner", "Goal"),
    "tasks": ("tasks", "Task"),
    "analytics": ("analytics", "Report"),
    "browser": ("internet", "SearchQuery"),
    "documents": ("documents", "Document"),
    "notifications": ("notifications", "Notification"),
    "email": ("email", "EmailDraft"),
    "calendar": ("calendar", "Event"),
    "agents": ("agent_manager", "Agent"),
    "workflows": ("workflow_engine", "Workflow"),
    "code": ("code_assistant", "CodeProject"),
}

SEARCH_TARGETS = (
    ("projects", "Project", "projects"),
    ("tasks", "Task", "tasks"),
    ("chat", "Conversation", "chat"),
    ("voice", "SpeechTranscript", "voice"),
    ("documents", "Document", "documents"),
    ("knowledge", "KnowledgeDocument", "knowledge"),
    ("memory", "Memory", "memory"),
    ("email", "EmailThread", "email"),
    ("calendar", "Event", "calendar"),
    ("workflow_engine", "Workflow", "workflows"),
    ("agent_manager", "Agent", "agents"),
    ("code_assistant", "CodeProject", "code"),
)


def _owned(model, user):
    field_names = {field.name for field in model._meta.fields}
    queryset = model.objects.all()
    if user.is_staff:
        return queryset
    if "owner" in field_names:
        return queryset.filter(owner=user)
    if "user" in field_names:
        return queryset.filter(user=user)
    if "actor" in field_names:
        return queryset.filter(actor=user)
    return queryset.none()


def _record_payload(record, section: str, icon: str) -> dict:
    configuration = getattr(record, "configuration", {}) or {}
    data = getattr(record, "data", {}) or {}
    title = getattr(record, "title", "") or getattr(record, "name", "") or str(record)
    description = (
        getattr(record, "description", "")
        or getattr(record, "summary", "")
        or getattr(record, "content", "")
        or getattr(record, "request_text", "")
        or getattr(record, "current_operation", "")
        or configuration.get("summary", "")
        or data.get("summary", "")
        or "No additional context yet."
    )
    return {
        "id": str(record.pk),
        "title": str(title),
        "description": str(description)[:240],
        "status": str(getattr(record, "status", "active") or "active"),
        "created_at": getattr(record, "created_at", None),
        "updated_at": getattr(record, "updated_at", None),
        "section": section,
        "icon": icon,
        "category": str(getattr(record, "category", "") or ""),
        "progress": int(getattr(record, "progress", 0) or configuration.get("progress", data.get("progress", 0)) or 0),
    }


def _query_source(app_label: str, model_name: str, section: str, icon: str, user, limit: int = 12):
    model = apps.get_model(app_label, model_name)
    queryset = _owned(model, user)
    try:
        records = list(queryset.order_by("-updated_at")[:limit])
        count = queryset.count()
    except (OperationalError, ProgrammingError):
        records, count = [], 0
    return {
        "key": model_name,
        "label": model._meta.verbose_name_plural.title(),
        "count": count,
        "icon": icon,
        "records": [_record_payload(record, section, icon) for record in records],
    }


def _all_counts(user) -> dict:
    counts = {}
    for section, sources in DATA_SOURCES.items():
        total = 0
        for app_label, model_name, _key, _icon in sources:
            try:
                total += _owned(apps.get_model(app_label, model_name), user).count()
            except (OperationalError, ProgrammingError):
                pass
        counts[section] = total
    return counts


def _presence(user) -> dict:
    status_rows = []
    running = 0
    pending = 0
    source_specs = (
        ("ai_engine", "AIRequest", "Reasoning", "spark"),
        ("workflow_engine", "WorkflowExecution", "Workflow", "workflow"),
        ("tool_manager", "ToolExecution", "Tool", "tool"),
        ("agent_manager", "AgentTask", "Agent", "agents"),
        ("internet", "ComputerUseOperation", "Computer use", "globe"),
    )
    for app_label, model_name, label, icon in source_specs:
        model = apps.get_model(app_label, model_name)
        try:
            queryset = _owned(model, user).filter(status__in=("running", "pending", "queued", "waiting"))
            for record in queryset.order_by("-updated_at")[:3]:
                record_status = getattr(record, "status", "active")
                running += int(record_status == "running")
                pending += int(record_status != "running")
                status_rows.append({
                    "title": getattr(record, "title", "") or getattr(record, "name", "") or label,
                    "type": label,
                    "status": record_status,
                    "icon": icon,
                })
        except (OperationalError, ProgrammingError):
            continue
    provider_ready = bool(settings.AI_PROVIDER_BASE_URL and settings.AI_PROVIDER_API_KEY)
    return {
        "state": "Working" if running else "Ready",
        "detail": f"{running} active · {pending} queued" if (running or pending) else "Context synchronized",
        "running": running,
        "pending": pending,
        "provider_ready": provider_ready,
        "items": status_rows[:5],
    }


def _timeline(user, limit: int = 8):
    combined = []
    for app_label, model_name, label, icon, section in (
        ("dashboard", "RecentActivity", "Activity", "activity", "notifications"),
        ("notifications", "Notification", "Notification", "bell", "notifications"),
        ("projects", "ProjectActivity", "Project", "projects", "projects"),
        ("workflow_engine", "ExecutionEvent", "Workflow", "workflow", "workflows"),
        ("ai_engine", "AIRequest", "AI", "spark", "chat"),
        ("internet", "ComputerUseOperation", "Computer use", "globe", "browser"),
        ("internet", "BrowserAction", "Browser action", "activity", "browser"),
        ("agent_manager", "AgentTask", "Agent", "spark", "agents"),
    ):
        try:
            records = _owned(apps.get_model(app_label, model_name), user).order_by("-updated_at")[:limit]
            for record in records:
                item = _record_payload(record, section, icon)
                item["type"] = label
                combined.append(item)
        except (OperationalError, ProgrammingError):
            continue
    combined.sort(key=lambda item: item.get("updated_at") or timezone.now(), reverse=True)
    return combined[:limit]



def _safe_recent(app_label: str, model_name: str, user, *, limit: int = 8, statuses: tuple[str, ...] | None = None):
    try:
        queryset = _owned(apps.get_model(app_label, model_name), user)
        if statuses:
            queryset = queryset.filter(status__in=statuses)
        return list(queryset.order_by("-updated_at")[:limit])
    except (OperationalError, ProgrammingError):
        return []


def _home_context(user, presence: dict) -> dict:
    active_tasks = _safe_recent("tasks", "Task", user, limit=6)
    active_tasks = [row for row in active_tasks if getattr(row, "status", "active") not in {"completed", "archived"}][:5]
    projects = _safe_recent("projects", "Project", user, limit=5)
    projects = [row for row in projects if getattr(row, "status", "active") not in {"completed", "archived"}][:4]
    conversations = _safe_recent("chat", "Conversation", user, limit=6)
    documents = _safe_recent("documents", "Document", user, limit=4)
    notifications = _safe_recent("notifications", "Notification", user, limit=12)
    workflows = _safe_recent("workflow_engine", "WorkflowExecution", user, limit=12)
    browser_jobs = _safe_recent("internet", "ComputerUseOperation", user, limit=8)
    agent_jobs = _safe_recent("agent_manager", "AgentTask", user, limit=12)
    agent_jobs = [item for item in agent_jobs if getattr(item, "parent_task_id", None) is None]
    tools = _safe_recent("tool_manager", "Tool", user, limit=6)
    voice_sessions = _safe_recent("voice", "VoiceSession", user, limit=4)

    attention = []
    attention_states = {"failed", "error", "waiting", "waiting_user", "pending", "approval_required", "blocked"}
    for record, kind, section_name, icon in (
        *((item, "Workflow", "workflows", "workflow") for item in workflows),
        *((item, "Notification", "notifications", "bell") for item in notifications),
        *((item, "Computer use", "browser", "globe") for item in browser_jobs),
        *((item, "Agent task", "agents", "spark") for item in agent_jobs),
        *((item, "Voice", "voice", "mic") for item in voice_sessions),
    ):
        config = getattr(record, "configuration", {}) or {}
        status_value = str(getattr(record, "status", "active") or "active").lower()
        runtime_state = str(getattr(record, "state", "") or "").lower()
        if kind == "Voice" and runtime_state in {"error", "paused"}:
            status_value = runtime_state
        approval_state = str(config.get("approval_state", "") or "").lower()
        browser_attention = config.get("attention") if isinstance(config.get("attention"), dict) else {}
        requires_attention = (
            status_value in attention_states
            or approval_state in {"pending", "required", "approval_required"}
            or bool(config.get("requires_confirmation"))
            or bool(config.get("captcha_detected"))
            or bool(config.get("login_required"))
            or bool(config.get("permission_required"))
            or bool(browser_attention)
        )
        if not requires_attention:
            continue
        reason = (
            "CAPTCHA detected" if config.get("captcha_detected")
            else "Login required" if config.get("login_required")
            else "Permission required" if config.get("permission_required")
            else "Approval required" if approval_state in {"pending", "required", "approval_required"}
            else status_value.replace("_", " ").title()
        )
        attention.append({
            "id": str(record.pk),
            "title": getattr(record, "title", "") or getattr(record, "name", "") or kind,
            "reason": reason,
            "status": status_value,
            "kind": kind,
            "icon": icon,
            "url": reverse("workspace", kwargs={"section": section_name}) + f"#record-{record.pk}",
            "updated_at": getattr(record, "updated_at", None),
        })
    attention.sort(key=lambda item: item.get("updated_at") or timezone.now(), reverse=True)

    active_work = []
    for item in presence.get("items", []):
        active_work.append({**item, "detail": "In progress" if item.get("status") == "running" else "Awaiting the next step"})
    for record in browser_jobs:
        if getattr(record, "status", "") in {"running", "queued", "pending", "waiting_user", "cancelling"}:
            active_work.append({
                "title": getattr(record, "title", "") or getattr(record, "request_text", "") or "Computer-use task",
                "type": "Computer use",
                "status": record.status,
                "icon": "globe",
                "detail": getattr(record, "current_operation", "") or ("Waiting for you" if record.status == "waiting_user" else "Observing and executing"),
                "progress": int(getattr(record, "progress", 0) or 0),
                "id": str(record.pk),
            })
    for record in agent_jobs:
        if getattr(record, "status", "") in {"running", "queued", "waiting", "cancelling"}:
            children = list(record.child_tasks.select_related("agent").order_by("-updated_at")[:1]) if hasattr(record, "child_tasks") else []
            child = children[0] if children else None
            active_work.append({
                "title": getattr(record, "title", "") or getattr(record, "request_text", "") or "Echo objective",
                "type": f"Agent · {(child.agent.title if child and child.agent else 'Manager')}",
                "status": record.status,
                "icon": "spark",
                "detail": (getattr(child, "current_operation", "") if child else "") or getattr(record, "current_operation", "") or "Coordinating agents",
                "progress": int(getattr(record, "progress", 0) or 0),
                "id": str(record.pk),
            })
    active_work = active_work[:6]

    suggestions = []
    if attention:
        suggestions.append({"label": f"Review {attention[0]['reason'].lower()}", "prompt": "Show me everything requiring my attention and explain the safest next action.", "icon": "alert"})
    if active_tasks:
        task_title = active_tasks[0].title or active_tasks[0].name
        suggestions.append({"label": "Plan around my top task", "prompt": f"Plan my work around {task_title}", "icon": "planner"})
    if conversations:
        conversation_title = conversations[0].title or conversations[0].name
        suggestions.append({"label": "Continue recent thinking", "prompt": f"Continue my conversation about {conversation_title}", "icon": "message"})
    if documents:
        suggestions.append({"label": "Work with a recent document", "prompt": f"Help me work with {documents[0].title or documents[0].name}", "icon": "document"})
    for fallback in (
        {"label": "Plan my day", "prompt": "Plan my work for today", "icon": "planner"},
        {"label": "Search my knowledge", "prompt": "What do I know about my current projects?", "icon": "knowledge"},
        {"label": "Start a research task", "prompt": "Research ", "icon": "globe"},
    ):
        if len(suggestions) >= 4:
            break
        if fallback["label"] not in {item["label"] for item in suggestions}:
            suggestions.append(fallback)

    profile = VoiceProfileService.default_for(user)
    return {
        "active_tasks": [_record_payload(item, "tasks", "check") for item in active_tasks],
        "projects": [_record_payload(item, "projects", "projects") for item in projects],
        "conversations": [_record_payload(item, "chat", "message") for item in conversations],
        "documents": [_record_payload(item, "documents", "document") for item in documents],
        "attention": attention[:7],
        "active_work": active_work,
        "suggestions": suggestions,
        "tools": [_record_payload(item, "workflows", "tool") for item in tools if getattr(item, "status", "active") not in {"disabled", "archived"}][:5],
        "voice": {
            "profile": {
                "language": profile.language,
                "auto_speak": profile.auto_speak,
                "provider": profile.speech_to_text_provider,
            },
            "recent_sessions": [VoiceSessionService.serialize(item) for item in voice_sessions[:3]],
            "providers": VoiceProviderRegistry.capabilities(),
        },
    }


def _voice_context(user) -> dict:
    profile = VoiceProfileService.default_for(user)
    sessions = VoiceSessionService.owned(user).select_related("conversation", "profile").order_by("-last_activity_at", "-created_at")[:20]
    transcripts = SpeechTranscript.objects.filter(owner=user).select_related("session", "conversation", "message").order_by("-created_at")[:30]
    return {
        "profile": {
            "language": profile.language,
            "speech_to_text_provider": profile.speech_to_text_provider,
            "text_to_speech_provider": profile.text_to_speech_provider,
            "voice_name": profile.voice_name,
            "speaking_rate": float(profile.speaking_rate),
            "pitch": float(profile.pitch),
            "volume": float(profile.volume),
            "auto_speak": profile.auto_speak,
            "continuous_listening": profile.continuous_listening,
            "barge_in_enabled": profile.barge_in_enabled,
            "memory_requires_approval": profile.memory_requires_approval,
            "speaker_identification_enabled": profile.speaker_identification_enabled,
            "reject_unrecognized_speakers": profile.reject_unrecognized_speakers,
            "voice_history_enabled": profile.voice_history_enabled,
            "transcript_retention_days": profile.transcript_retention_days,
            "active_session_minutes": profile.active_session_minutes,
        },
        "sessions": [VoiceSessionService.serialize(item) for item in sessions],
        "transcripts": [
            {
                "id": str(item.pk),
                "session_id": str(item.session_id) if item.session_id else None,
                "text": item.text,
                "route": item.command_route,
                "response_content": str((item.command_result or {}).get("content", "")),
                "response_route": str((item.command_result or {}).get("route", item.command_route or "")),
                "memory_status": item.memory_status,
                "created_at": item.created_at,
            }
            for item in transcripts
        ],
        "providers": VoiceProviderRegistry.capabilities(),
    }



def _browser_context(user) -> dict:
    try:
        BrowserSession = apps.get_model("internet", "BrowserSession")
        BrowserObservation = apps.get_model("internet", "BrowserObservation")
        BrowserAction = apps.get_model("internet", "BrowserAction")
        ComputerUseOperation = apps.get_model("internet", "ComputerUseOperation")
        MediaUnderstanding = apps.get_model("internet", "MediaUnderstanding")
        sessions = _owned(BrowserSession, user).order_by("-last_activity_at", "-created_at")
        current_session = sessions.filter(status__in=("active", "running", "ready")).first() or sessions.first()
        operations = list(_owned(ComputerUseOperation, user).select_related("session").order_by("-updated_at")[:20])
        actions = list(_owned(BrowserAction, user).select_related("session", "post_observation").order_by("-created_at")[:12])
        media = list(_owned(MediaUnderstanding, user).order_by("-processed_at", "-created_at")[:6])
        latest_observation = None
        if current_session:
            latest_observation = _owned(BrowserObservation, user).filter(session=current_session).order_by("-sequence").first()
        def op_payload(item):
            config = item.configuration or {}
            return {
                "id": str(item.pk), "request": item.request_text, "status": item.status,
                "progress": int(item.progress or 0), "current_operation": item.current_operation,
                "current_tool": item.current_tool, "cancellable": item.cancellable,
                "cancel_requested": item.cancel_requested, "error": item.error_message,
                "attention": config.get("attention") or {}, "updated_at": item.updated_at,
                "session_id": str(item.session_id) if item.session_id else "",
            }
        return {
            "current_session": {
                "id": str(current_session.pk), "status": current_session.status, "engine": current_session.engine,
                "url": current_session.current_url, "title": current_session.current_title,
                "last_activity_at": current_session.last_activity_at,
            } if current_session else None,
            "latest_observation": {
                "id": str(latest_observation.pk), "url": latest_observation.url, "title": latest_observation.page_title,
                "visible_text": latest_observation.visible_text[:1600], "screenshot_url": latest_observation.screenshot.url if latest_observation.screenshot else "",
                "observed_at": latest_observation.observed_at,
            } if latest_observation else None,
            "operations": [op_payload(item) for item in operations],
            "active_operations": [op_payload(item) for item in operations if item.status in {"queued", "running", "waiting_user", "cancelling"}],
            "recent_actions": [{
                "id": str(item.pk), "action": item.action_type, "status": item.status, "verified": item.verified,
                "target": item.target[:160], "error": item.error_message, "created_at": item.created_at,
            } for item in actions],
            "media": [{
                "id": str(item.pk), "status": item.status, "source_url": item.source_url,
                "summary": item.summary[:900], "confidence": float(item.confidence or 0), "processed_at": item.processed_at,
            } for item in media],
        }
    except (OperationalError, ProgrammingError):
        return {"current_session": None, "latest_observation": None, "operations": [], "active_operations": [], "recent_actions": [], "media": []}

def _workspace_context(request, section: str) -> dict:
    if section not in SECTION_META:
        raise Http404("Workspace not found")
    sources = [
        _query_source(app_label, model_name, section, icon, request.user)
        for app_label, model_name, _key, icon in DATA_SOURCES[section]
    ]
    for source, (_, _, key, _) in zip(sources, DATA_SOURCES[section]):
        source["key"] = key
    counts = _all_counts(request.user)
    total = sum(counts.values())
    meta = dict(SECTION_META[section])
    current_time = timezone.localtime()
    presence = _presence(request.user)
    if section == "home":
        display_name = request.user.display_name or request.user.first_name or "there"
        greeting = "Good morning" if current_time.hour < 12 else "Good afternoon" if current_time.hour < 18 else "Good evening"
        meta["title"] = f"{greeting}, {display_name}"
    context = {
        "section": section,
        "section_meta": meta,
        "nav_groups": NAV_GROUPS,
        "sources": sources,
        "counts": counts,
        "total_records": total,
        "presence": presence,
        "timeline": _timeline(request.user),
        "create_enabled": section in CREATE_TARGETS,
        "ai_provider_ready": bool(settings.AI_PROVIDER_BASE_URL and settings.AI_PROVIDER_API_KEY),
        "now": current_time,
    }
    if section == "home":
        context["home"] = _home_context(request.user, presence)
    if section in {"voice", "settings"}:
        context["voice"] = _voice_context(request.user)
    if section == "browser":
        context["computer_use"] = _browser_context(request.user)
    return context


@login_required
def dashboard(request):
    return workspace(request, "home")


@login_required
def workspace(request, section: str):
    return render(request, "workspace/shell.html", _workspace_context(request, section))


@require_POST
@login_required
def workspace_action(request):
    section = str(request.POST.get("section", "")).strip()
    title = str(request.POST.get("title", "")).strip()
    description = str(request.POST.get("description", "")).strip()
    category = str(request.POST.get("category", "")).strip()
    if section not in CREATE_TARGETS:
        return JsonResponse({"detail": "This workspace does not support direct creation."}, status=400)
    if not title:
        return JsonResponse({"detail": "A title is required."}, status=400)
    app_label, model_name = CREATE_TARGETS[section]
    model = apps.get_model(app_label, model_name)
    field_names = {field.name for field in model._meta.fields}
    payload = {}
    for field, value in (("name", title), ("title", title), ("description", description), ("status", "active"), ("category", category)):
        if field in field_names:
            payload[field] = value
    if "owner" in field_names:
        payload["owner"] = request.user
    if "user" in field_names:
        payload["user"] = request.user
    if "data" in field_names:
        payload["data"] = {"created_from": "echo_workspace"}
    if "configuration" in field_names:
        payload["configuration"] = {"created_from": "echo_workspace"}
    if model_name == "Memory":
        payload.update({"content": description or title, "summary": title, "memory_type": category or "workspace", "importance_score": 0.5, "confidence_score": 1})
    if model_name == "SearchQuery":
        payload["configuration"] = {"query": title, "created_from": "echo_workspace"}
    record = model.objects.create(**payload)
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"ok": True, "record": _record_payload(record, section, SECTION_META[section]["icon"])}, status=201)
    return redirect("workspace", section=section)


@require_POST
@login_required
def ai_command(request):
    try:
        payload = json.loads(request.body or b"{}") if request.content_type == "application/json" else request.POST
    except json.JSONDecodeError:
        return JsonResponse({"detail": "Invalid request payload."}, status=400)
    prompt = str(payload.get("prompt", "")).strip()
    section = str(payload.get("section", "home")).strip()
    conversation_id = str(payload.get("conversation_id", "")).strip() or None
    try:
        result = AgentManagerOrchestrator(request.user, source="text", section=section).execute(
            prompt,
            conversation_id=conversation_id,
        )
    except CommandError as exc:
        return JsonResponse({"ok": False, "detail": str(exc)}, status=400)
    except Exception as exc:
        return JsonResponse(
            {
                "ok": False,
                "saved": bool(prompt),
                "detail": f"Echo could not complete the command: {exc}",
            },
            status=502,
        )
    payload = result.as_dict()
    payload["saved"] = True
    if result.status == "completed":
        status_code = 200
    elif result.requires_configuration:
        status_code = 503
    elif result.status == "not_found":
        status_code = 404
    elif result.needs_confirmation or result.status == "waiting":
        status_code = 202
    else:
        status_code = 400
    return JsonResponse(payload, status=status_code)


@require_GET
@login_required
def workspace_search(request):
    query = str(request.GET.get("q", "")).strip()
    if len(query) < 2:
        return JsonResponse({"results": []})
    results = []
    for app_label, model_name, section in SEARCH_TARGETS:
        model = apps.get_model(app_label, model_name)
        field_names = {field.name for field in model._meta.fields}
        expression = models.Q()
        for field in ("title", "name", "description", "content", "summary"):
            if field in field_names:
                expression |= models.Q(**{f"{field}__icontains": query})
        if not expression.children:
            continue
        try:
            records = _owned(model, request.user).filter(expression).order_by("-updated_at")[:4]
            for record in records:
                item = _record_payload(record, section, SECTION_META[section]["icon"])
                item["type"] = model._meta.verbose_name.title()
                item["url"] = reverse("workspace", kwargs={"section": section}) + f"#record-{record.pk}"
                results.append(item)
        except (OperationalError, ProgrammingError):
            continue
    return JsonResponse({"results": results[:24]})


@require_POST
@login_required
def upload_document(request):
    uploaded = request.FILES.get("file")
    if uploaded is None:
        return JsonResponse({"detail": "Choose a file to upload."}, status=400)
    if uploaded.size > settings.DATA_UPLOAD_MAX_MEMORY_SIZE:
        return JsonResponse({"detail": "The file exceeds the configured upload limit."}, status=413)
    original_name = Path(uploaded.name).name
    digest = hashlib.sha256()
    for chunk in uploaded.chunks():
        digest.update(chunk)
    uploaded.seek(0)
    storage_name = f"workspace/{request.user.pk}/{uuid.uuid4().hex}-{original_name}"
    saved_path = default_storage.save(storage_name, uploaded)
    file_model = apps.get_model("core", "UploadedFile")
    file_record = file_model.objects.create(
        owner=request.user,
        name=original_name,
        title=original_name,
        description="Uploaded through the Echo document studio.",
        status="active",
        file_name=Path(saved_path).name,
        original_name=original_name,
        extension=Path(original_name).suffix.lower().lstrip("."),
        mime_type=uploaded.content_type or "application/octet-stream",
        size=uploaded.size,
        storage_path=default_storage.url(saved_path),
        checksum=digest.hexdigest(),
        uploaded_at=timezone.now(),
        data={"storage_key": saved_path},
    )
    document_model = apps.get_model("documents", "Document")
    document = document_model.objects.create(
        owner=request.user,
        name=original_name,
        title=Path(original_name).stem,
        description="Uploaded document queued for extraction and knowledge indexing.",
        status="uploaded",
        category=Path(original_name).suffix.lower().lstrip(".") or "file",
        configuration={"uploaded_file_id": str(file_record.pk), "storage_key": saved_path},
        data={"mime_type": uploaded.content_type, "size": uploaded.size},
    )
    from echo.apps.documents.tasks import process_document

    processing = None
    processing_error = ""
    try:
        processing = process_document.delay(str(document.pk), str(request.user.pk), saved_path)
    except Exception as exc:  # eager execution preserves the failed document record
        processing_error = str(exc)
    document.refresh_from_db()
    payload = _record_payload(document, "documents", "document")
    payload["processing_task_id"] = str(getattr(processing, "id", "") or "")
    if processing_error:
        payload["processing_error"] = processing_error
    return JsonResponse({"ok": True, "document": payload}, status=201)

@require_POST
@login_required
def workspace_record_update(request):
    try:
        payload = json.loads(request.body or b"{}") if request.content_type == "application/json" else request.POST
    except json.JSONDecodeError:
        return JsonResponse({"detail": "Invalid request payload."}, status=400)
    section = str(payload.get("section", "")).strip()
    record_id = str(payload.get("record_id", "")).strip()
    status_value = str(payload.get("status", "")).strip()
    target = CREATE_TARGETS.get(section)
    if target is None or not record_id or status_value not in {"active", "completed", "paused", "archived"}:
        return JsonResponse({"detail": "The requested update is not allowed."}, status=400)
    model = apps.get_model(*target)
    try:
        record = _owned(model, request.user).filter(pk=record_id).first()
    except (ValueError, TypeError):
        record = None
    if record is None:
        return JsonResponse({"detail": "Record not found."}, status=404)
    if "status" not in {field.name for field in model._meta.fields}:
        return JsonResponse({"detail": "This record has no status field."}, status=400)
    record.status = status_value
    record.save(update_fields=["status", "updated_at"])
    return JsonResponse({"ok": True, "record_id": str(record.pk), "status": record.status})
