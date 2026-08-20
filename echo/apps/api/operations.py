from __future__ import annotations

import json
import platform
import time
import uuid
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

from django.apps import apps
from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import connections
from django.db.models import Q
from django.http import HttpResponse, StreamingHttpResponse
from django.utils import timezone
from rest_framework import serializers as drf_serializers
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response

from echo.apps.agent_manager.models import AgentPerformance
from echo.apps.ai_engine.provider import OpenAICompatibleProvider
from echo.apps.ai_engine.runtime import AIExecutionService
from echo.apps.analytics.collector import AnalyticsCollector
from echo.apps.calendar.models import Event
from echo.apps.calendar.scheduling import SchedulingService
from echo.apps.chat.models import Conversation, Message, SharedConversation
from echo.apps.code_assistant.analyzer import PythonAnalyzer
from echo.apps.code_assistant.models import SourceFile
from echo.apps.documents.extractors import DocumentExtractor
from echo.apps.dashboard.models import DashboardLayout
from echo.apps.documents.models import Document, DocumentContent, ProcessingJob
from echo.apps.email.imap_sync import IMAPSyncService
from echo.apps.email.mailer import SMTPMailer
from echo.apps.email.models import EmailAccount
from echo.apps.internet.models import CrawledPage, Download, SearchQuery, SearchResult, WebPage
from echo.apps.internet.safe_fetch import SafeFetchService
from echo.apps.internet.search_provider import ConfiguredSearchProvider
from echo.apps.knowledge.models import KnowledgeDocument
from echo.apps.knowledge.models import KnowledgeVersion
from echo.apps.knowledge.search import KnowledgeSearchService
from echo.apps.memory.models import Memory, MemoryAccessLog
from echo.apps.notifications.dispatcher import NotificationDispatcher
from echo.apps.notifications.models import Notification
from echo.apps.planner.engine import PlanningEngine
from echo.apps.planner.models import Goal, PlanStep
from echo.apps.projects.portability import ProjectPortabilityService
from echo.apps.tasks.models import Task, TimeEntry
from echo.apps.tasks.tracking import TimeTrackingService
from echo.apps.tool_manager.execution import ToolExecutor
from echo.apps.tool_manager.models import Tool, ToolExecution, ToolHealth
from echo.apps.vector_database.embedding import (
    batch_feature_hash_embedding,
    feature_hash_embedding,
)
from echo.apps.vector_database.models import SearchHistory, VectorChunk, VectorIndex
from echo.apps.vector_database.vector_math import rank
from echo.apps.workflow_engine.executor import WorkflowExecutor
from echo.apps.workflow_engine.models import Checkpoint, Workflow
from echo.common.serializers import DynamicModelSerializer


Handler = Callable[[Any, str], Response | StreamingHttpResponse]


def _serialize(instance, *, many: bool = False):
    if many and isinstance(instance, (list, tuple)):
        if not instance:
            return []
        model_types = {item.__class__ for item in instance}
        if len(model_types) > 1:
            return [_serialize(item) for item in instance]
        model = instance[0].__class__
    else:
        model = instance.model if hasattr(instance, "model") else instance.__class__
    serializer_class = type(
        f"{model.__name__}OperationSerializer",
        (DynamicModelSerializer,),
        {
            "Meta": type(
                "Meta",
                (),
                {
                    "model": model,
                    "fields": "__all__",
                    "read_only_fields": (
                        "id",
                        "created_at",
                        "updated_at",
                        "owner",
                        "user",
                        "actor",
                    ),
                },
            )
        },
    )
    return serializer_class(instance, many=many).data


def _uuid(value: Any, field: str = "id") -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ValidationError({field: "A valid UUID is required."}) from exc


def _owned(model, user):
    names = {field.name for field in model._meta.fields}
    queryset = model.objects.all()
    if user.is_staff:
        return queryset
    if "owner" in names:
        return queryset.filter(owner=user)
    if "user" in names:
        return queryset.filter(user=user)
    if "actor" in names:
        return queryset.filter(actor=user)
    return queryset.none()


def _required_record(model, user, identifier, field: str = "id"):
    record = _owned(model, user).filter(pk=_uuid(identifier, field)).first()
    if record is None:
        raise NotFound(f"{model._meta.verbose_name} was not found.")
    return record


def _database_status(request, path):
    started = time.monotonic()
    with connections["default"].cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()
    return Response(
        {
            "status": "ok",
            "database": "ok",
            "latency_ms": round((time.monotonic() - started) * 1000, 3),
            "timestamp": timezone.now(),
        }
    )


def _version(request, path):
    return Response(
        {
            "name": "Echo Enterprise Platform",
            "version": "1.0.0",
            "python": platform.python_version(),
            "environment": settings.ENVIRONMENT,
        }
    )


def _dashboard(request, path):
    totals = {}
    recent = []
    for app_config in apps.get_app_configs():
        if not app_config.name.startswith("echo.apps."):
            continue
        totals[app_config.label] = sum(
            _owned(model, request.user).count() for model in app_config.get_models()
        )
    activity_model = apps.get_model("dashboard", "RecentActivity")
    recent = _serialize(_owned(activity_model, request.user)[:20], many=True)
    return Response(
        {
            "totals": totals,
            "grand_total": sum(totals.values()),
            "recent_activity": recent,
            "generated_at": timezone.now(),
        }
    )


def _dashboard_layout_reset(request, path):
    DashboardLayout.objects.filter(owner=request.user).update(is_default=False)
    layout = DashboardLayout.objects.create(
        owner=request.user,
        user=request.user,
        name="default",
        title="Default dashboard layout",
        status="active",
        is_default=True,
        columns=12,
        theme="system",
        data={"widgets": []},
    )
    return Response(_serialize(layout), status=status.HTTP_201_CREATED)


def _code_search(request, path):
    query = str(request.query_params.get("q", "")).strip()
    if not query:
        raise ValidationError({"q": "A search query is required."})
    candidates = SourceFile.objects.filter(owner=request.user)[:500]
    lowered = query.casefold()
    records = [
        record
        for record in candidates
        if lowered in record.name.casefold()
        or lowered in record.title.casefold()
        or lowered in record.description.casefold()
        or lowered in str((record.configuration or {}).get("content", "")).casefold()
    ][:100]
    return Response({"count": len(records), "results": _serialize(records, many=True)})


def _knowledge_rollback(request, path):
    version = _required_record(
        KnowledgeVersion,
        request.user,
        request.data.get("version_id"),
        "version_id",
    )
    configuration = version.configuration or {}
    document_id = configuration.get("document_id")
    snapshot = configuration.get("snapshot")
    if not document_id or not isinstance(snapshot, dict):
        raise ValidationError({"version_id": "The version does not contain a restorable document snapshot."})
    document = _required_record(KnowledgeDocument, request.user, document_id, "document_id")
    for field in ("name", "title", "description", "status", "category", "configuration", "data"):
        if field in snapshot:
            setattr(document, field, snapshot[field])
    document.full_clean()
    document.save()
    return Response(_serialize(document))


def _document_export(request, path):
    identifier = next((part for part in path.split("/") if _is_uuid(part)), None)
    document = _required_record(Document, request.user, identifier)
    content = DocumentContent.objects.filter(
        owner=request.user,
        configuration__document_id=str(document.pk),
    ).first()
    export_format = str(request.data.get("format", "json")).lower()
    text = (content.configuration or {}).get("content", "") if content else ""
    if export_format == "text":
        response = HttpResponse(text, content_type="text/plain; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{document.name or document.pk}.txt"'
        return response
    return Response({"document": _serialize(document), "content": text, "exported_at": timezone.now()})


def _chat_export(request, path):
    conversation_id = request.data.get("conversation_id")
    conversation = _required_record(Conversation, request.user, conversation_id, "conversation_id")
    messages = Message.objects.filter(
        owner=request.user,
        conversation=conversation,
    ).order_by("created_at")
    return Response(
        {
            "conversation": _serialize(conversation),
            "messages": _serialize(messages, many=True),
            "exported_at": timezone.now(),
        }
    )


def _chat_search(request, path):
    query = str(request.query_params.get("q", "")).strip()
    if not query:
        raise ValidationError({"q": "A search query is required."})
    messages = Message.objects.filter(owner=request.user).filter(
        Q(content__icontains=query) | Q(rendered_content__icontains=query)
    )[:100]
    return Response({"count": messages.count(), "results": _serialize(messages, many=True)})


def _chat_share(request, path):
    token = path.split("/")[-1]
    share = SharedConversation.objects.select_related("conversation").filter(
        token=token,
        status="active",
    ).first()
    if not share or (share.expires_at and share.expires_at <= timezone.now()):
        raise NotFound("Shared conversation was not found or has expired.")
    share.view_count += 1
    share.save(update_fields=["view_count", "updated_at"])
    messages = Message.objects.filter(conversation=share.conversation).order_by("created_at")
    return Response(
        {
            "conversation": {
                "id": share.conversation.pk,
                "title": share.conversation.title,
                "description": share.conversation.description,
                "conversation_type": share.conversation.conversation_type,
                "last_message_at": share.conversation.last_message_at,
            },
            "messages": [
                {
                    "id": message.pk,
                    "role": message.role,
                    "content": message.content,
                    "rendered_content": message.rendered_content,
                    "created_at": message.created_at,
                    "edited_at": message.edited_at,
                }
                for message in messages
            ],
        }
    )


def _ai_generate(request, path):
    messages = request.data.get("messages")
    if not isinstance(messages, list) or not messages:
        prompt = str(request.data.get("prompt", "")).strip()
        if not prompt:
            raise ValidationError({"messages": "messages or prompt is required."})
        messages = [{"role": "user", "content": prompt}]
    request_record, response_record, payload = AIExecutionService.generate(
        request.user,
        messages,
        model=request.data.get("model"),
        temperature=float(request.data.get("temperature", 0.2)),
    )
    return Response(
        {
            "request_id": request_record.pk,
            "response_id": response_record.pk,
            "content": response_record.content,
            "usage": payload.get("usage", {}),
        },
        status=status.HTTP_201_CREATED,
    )


def _ai_stream(request, path):
    messages = request.data.get("messages")
    if not isinstance(messages, list) or not messages:
        raise ValidationError({"messages": "A non-empty message list is required."})
    provider = OpenAICompatibleProvider()

    def event_stream():
        for chunk in provider.stream(
            messages,
            model=request.data.get("model"),
            temperature=float(request.data.get("temperature", 0.2)),
        ):
            yield f"data: {json.dumps({'content': chunk})}\n\n"
        yield "data: [DONE]\n\n"

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response


def _memory_search(request, path):
    query = str(request.query_params.get("q", "")).strip()
    if not query:
        raise ValidationError({"q": "A search query is required."})
    records = Memory.objects.filter(user=request.user).filter(
        Q(content__icontains=query)
        | Q(summary__icontains=query)
        | Q(title__icontains=query)
        | Q(name__icontains=query)
    )[:100]
    now = timezone.now()
    for memory in records:
        memory.access_count += 1
        memory.last_accessed = now.isoformat()
        memory.save(update_fields=["access_count", "last_accessed", "updated_at"])
        MemoryAccessLog.objects.create(
            owner=request.user,
            user=request.user,
            memory=memory,
            name="search",
            title="Memory search access",
            status="recorded",
            reason=query,
            accessed_at=now,
        )
    return Response({"count": records.count(), "results": _serialize(records, many=True)})


def _vector_embed(request, path):
    dimensions = int(request.data.get("dimensions", 384))
    if path == "vector/embed/batch":
        texts = request.data.get("texts")
        if not isinstance(texts, list) or not all(isinstance(item, str) for item in texts):
            raise ValidationError({"texts": "A list of strings is required."})
        return Response({"dimensions": dimensions, "embeddings": batch_feature_hash_embedding(texts, dimensions)})
    text = str(request.data.get("text", ""))
    if not text:
        raise ValidationError({"text": "Text is required."})
    return Response({"dimensions": dimensions, "embedding": feature_hash_embedding(text, dimensions)})


def _vector_search(request, path):
    query_vector = request.data.get("vector")
    if query_vector is None:
        text = str(request.data.get("query", ""))
        if not text:
            raise ValidationError({"query": "query or vector is required."})
        query_vector = feature_hash_embedding(text, int(request.data.get("dimensions", 384)))
    if not isinstance(query_vector, list):
        raise ValidationError({"vector": "A numeric vector list is required."})
    candidates = []
    records = list(VectorChunk.objects.filter(owner=request.user)[:5000])
    for chunk in records:
        embedding = (chunk.metadata or {}).get("embedding") or (chunk.data or {}).get("embedding")
        if isinstance(embedding, list) and len(embedding) == len(query_vector):
            candidates.append((str(chunk.pk), embedding))
    ranked = rank(query_vector, candidates)[: int(request.data.get("limit", 20))]
    by_id = {str(item.pk): item for item in records}
    results = [
        {"score": score, "record": _serialize(by_id[identifier])}
        for score, identifier in ranked
    ]
    SearchHistory.objects.create(
        owner=request.user,
        user=request.user,
        name="vector_search",
        title="Vector search",
        status="completed",
        query=str(request.data.get("query", "")),
        results={"matches": [{"id": item["record"]["id"], "score": item["score"]} for item in results]},
    )
    return Response({"count": len(results), "results": results})


def _vector_index(request, path):
    if request.method == "GET":
        indexes = VectorIndex.objects.filter(owner=request.user)
        chunks = VectorChunk.objects.filter(owner=request.user).count()
        return Response({"indexes": _serialize(indexes, many=True), "chunk_count": chunks})
    if path.endswith("rebuild"):
        updated = 0
        dimensions = int(request.data.get("dimensions", 384))
        for chunk in VectorChunk.objects.filter(owner=request.user).iterator():
            chunk.metadata = {
                **(chunk.metadata or {}),
                "embedding": feature_hash_embedding(chunk.content, dimensions),
                "indexed_at": timezone.now().isoformat(),
            }
            chunk.save(update_fields=["metadata", "updated_at"])
            updated += 1
        return Response({"status": "completed", "updated_chunks": updated, "dimensions": dimensions})
    index = VectorIndex.objects.create(
        owner=request.user,
        name=str(request.data.get("name", "default")),
        title=str(request.data.get("title", "Vector index")),
        status="active",
        provider="local-feature-hash",
        index_name=str(request.data.get("index_name", "default")),
        dimensions=int(request.data.get("dimensions", 384)),
        distance_metric="cosine",
    )
    return Response(_serialize(index), status=status.HTTP_201_CREATED)


def _knowledge_search(request, path):
    query = str(request.query_params.get("q", request.data.get("q", ""))).strip()
    hits = KnowledgeSearchService.search(request.user, query, int(request.query_params.get("limit", 25)))
    return Response({"count": len(hits), "results": [hit.__dict__ for hit in hits]})


def _knowledge_export(request, path):
    records = KnowledgeDocument.objects.filter(owner=request.user).order_by("created_at")
    return Response({"count": records.count(), "documents": _serialize(records, many=True)})


def _knowledge_import(request, path):
    records = request.data.get("documents")
    if not isinstance(records, list):
        raise ValidationError({"documents": "A list of document objects is required."})
    created = []
    for item in records:
        if not isinstance(item, dict):
            raise ValidationError({"documents": "Every document must be an object."})
        created.append(
            KnowledgeDocument.objects.create(
                owner=request.user,
                name=str(item.get("name", "document")),
                title=str(item.get("title", item.get("name", "Knowledge document"))),
                description=str(item.get("description", "")),
                status=str(item.get("status", "active")),
                category=str(item.get("category", "imported")),
                configuration=item.get("configuration", {}),
                data=item.get("data", {}),
            )
        )
    return Response({"count": len(created), "documents": _serialize(created, many=True)}, status=status.HTTP_201_CREATED)


def _document_upload(request, path):
    uploaded = request.FILES.get("file")
    if uploaded is None:
        raise ValidationError({"file": "A document file is required."})
    storage_name = default_storage.save(f"documents/{uuid.uuid4()}-{Path(uploaded.name).name}", uploaded)
    local_path = default_storage.path(storage_name)
    job = ProcessingJob.objects.create(
        owner=request.user,
        name=Path(uploaded.name).name,
        title=f"Processing {uploaded.name}",
        status="processing",
        category="extraction",
        configuration={"storage_name": storage_name},
    )
    try:
        content = DocumentExtractor().extract(local_path)
    except Exception as exc:
        job.status = "failed"
        job.configuration = {**job.configuration, "error": str(exc)}
        job.save(update_fields=["status", "configuration", "updated_at"])
        raise
    document = Document.objects.create(
        owner=request.user,
        name=Path(uploaded.name).stem,
        title=Path(uploaded.name).name,
        status="ready",
        category=Path(uploaded.name).suffix.lower().lstrip("."),
        configuration={
            "storage_name": storage_name,
            "mime_type": getattr(uploaded, "content_type", ""),
            "size": uploaded.size,
        },
    )
    DocumentContent.objects.create(
        owner=request.user,
        name=str(document.pk),
        title=f"Content for {document.title}",
        status="ready",
        category="extracted_text",
        configuration={"document_id": str(document.pk), "content": content},
    )
    job.status = "completed"
    job.configuration = {**job.configuration, "document_id": str(document.pk)}
    job.save(update_fields=["status", "configuration", "updated_at"])
    return Response(_serialize(document), status=status.HTTP_201_CREATED)


def _document_search(request, path):
    query = str(request.query_params.get("q", "")).strip()
    contents = list(DocumentContent.objects.filter(owner=request.user)[:500])
    if query:
        lowered = query.casefold()
        contents = [
            content
            for content in contents
            if lowered in content.title.casefold()
            or lowered in content.description.casefold()
            or lowered in str((content.configuration or {}).get("content", "")).casefold()
        ]
    results = contents[:100]
    return Response({"count": len(results), "results": _serialize(results, many=True)})


def _document_preview(request, path):
    identifier = next((part for part in path.split("/") if _is_uuid(part)), None)
    document = _required_record(Document, request.user, identifier)
    content = DocumentContent.objects.filter(
        owner=request.user,
        configuration__document_id=str(document.pk),
    ).first()
    return Response({"document": _serialize(document), "content": (content.configuration or {}).get("content", "") if content else ""})


def _internet_search(request, path):
    query = str(request.data.get("query", request.data.get("q", ""))).strip()
    if not query:
        raise ValidationError({"query": "A search query is required."})
    search_type = path.split("/")[-1]
    if search_type == "search":
        search_type = "web"
    query_record = SearchQuery.objects.create(
        owner=request.user,
        user=request.user,
        name=query[:255],
        title=query[:255],
        status="running",
        query=query,
        search_type=search_type,
        requested_at=timezone.now(),
    )
    results = ConfiguredSearchProvider().search(
        query,
        search_type=search_type,
        limit=int(request.data.get("limit", 10)),
    )
    stored = []
    for position, item in enumerate(results, start=1):
        url = str(item.get("url", ""))
        stored.append(
            SearchResult.objects.create(
                owner=request.user,
                name=str(item.get("title", url))[:255],
                title=str(item.get("title", url))[:255],
                description=str(item.get("snippet", "")),
                status="retrieved",
                query=query,
                url=url,
                snippet=str(item.get("snippet", "")),
                domain=urlparse(url).hostname or "",
                rank=position,
                retrieved_at=timezone.now(),
                data=item,
            )
        )
    query_record.status = "completed"
    query_record.save(update_fields=["status", "updated_at"])
    return Response({"query_id": query_record.pk, "count": len(stored), "results": _serialize(stored, many=True)})


def _internet_fetch(request, path):
    url = str(request.data.get("url", "")).strip()
    if not url:
        raise ValidationError({"url": "A URL is required."})
    fetched = SafeFetchService().fetch(url)
    body = fetched["body"]
    content_type = fetched["content_type"]
    text = body.decode("utf-8", errors="replace") if "text" in content_type or "json" in content_type else ""
    page = WebPage.objects.create(
        owner=request.user,
        name=(urlparse(url).hostname or "web-page")[:255],
        title=url[:255],
        status="fetched",
        url=url,
        status_code=str(fetched["status_code"]),
        content_type=content_type,
        description=text[:5000],
        metadata={"bytes": len(body)},
        last_fetched=timezone.now().isoformat(),
    )
    return Response({"page": _serialize(page), "content": text[:200_000], "bytes": len(body)})


def _internet_crawl(request, path):
    response = _internet_fetch(request, path)
    page = response.data["page"]
    record = CrawledPage.objects.create(
        owner=request.user,
        name=str(page["id"]),
        title=page["title"],
        status="completed",
        category="crawl",
        configuration={"web_page_id": str(page["id"]), "url": page["url"]},
    )
    response.data["crawl"] = _serialize(record)
    return response


def _internet_download(request, path):
    url = str(request.data.get("url", "")).strip()
    fetched = SafeFetchService().fetch(url, max_bytes=int(request.data.get("max_bytes", 10_000_000)))
    file_name = Path(urlparse(url).path).name or f"download-{uuid.uuid4()}"
    storage_name = default_storage.save(f"downloads/{uuid.uuid4()}-{file_name}", ContentFile(fetched["body"]))
    record = Download.objects.create(
        owner=request.user,
        name=file_name,
        title=file_name,
        status="completed",
        category="download",
        configuration={"url": url, "storage_name": storage_name, "bytes": len(fetched["body"])},
    )
    return Response(_serialize(record), status=status.HTTP_201_CREATED)


def _code_analyze(request, path):
    source = str(request.data.get("source", ""))
    if not source:
        raise ValidationError({"source": "Python source is required."})
    result = PythonAnalyzer().analyze(source)
    return Response({"valid": result.valid, "symbols": result.symbols, "errors": result.errors})


def _code_ai(request, path):
    source = str(request.data.get("source", ""))
    instruction = str(request.data.get("instruction", "")).strip()
    action = path.split("/")[-1]
    prompts = {
        "review": "Review this code for correctness, security, maintainability, and performance.",
        "generate": "Generate production-ready code for the stated instruction.",
        "refactor": "Refactor this code while preserving behavior and explain material changes.",
        "tests": "Generate comprehensive automated tests for this code.",
        "documentation": "Generate precise developer documentation for this code.",
    }
    user_prompt = f"{prompts[action]}\n\nInstruction: {instruction}\n\nCode:\n{source}"
    request_record, response_record, payload = AIExecutionService.generate(
        request.user,
        [{"role": "user", "content": user_prompt}],
        model=request.data.get("model"),
        temperature=float(request.data.get("temperature", 0.1)),
    )
    return Response({"request_id": request_record.pk, "content": response_record.content, "usage": payload.get("usage", {})})


def _planner_build(request, path):
    goal = _required_record(Goal, request.user, request.data.get("goal_id"), "goal_id")
    plan = PlanningEngine.build(goal, request.user)
    steps = [
        step
        for step in PlanStep.objects.filter(owner=request.user)
        if str((step.configuration or {}).get("plan_id", "")) == str(plan.pk)
    ]
    steps.sort(key=lambda step: int((step.configuration or {}).get("position", 0)))
    return Response({"plan": _serialize(plan), "steps": _serialize(steps, many=True)}, status=status.HTTP_201_CREATED)


def _planner_reorder(request, path):
    ordered_ids = request.data.get("step_ids")
    if not isinstance(ordered_ids, list):
        raise ValidationError({"step_ids": "A list of step UUIDs is required."})
    steps = {str(item.pk): item for item in PlanStep.objects.filter(owner=request.user, pk__in=ordered_ids)}
    if len(steps) != len(set(map(str, ordered_ids))):
        raise ValidationError({"step_ids": "One or more steps were not found."})
    for position, step_id in enumerate(map(str, ordered_ids), start=1):
        step = steps[step_id]
        step.configuration = {**(step.configuration or {}), "position": position}
        step.save(update_fields=["configuration", "updated_at"])
    return Response({"updated": len(steps)})


def _planner_progress(request, path):
    plan_id = str(request.query_params.get("plan_id", ""))
    steps = PlanStep.objects.filter(owner=request.user)
    if plan_id:
        steps = steps.filter(configuration__plan_id=plan_id)
    total = steps.count()
    completed = steps.filter(status="completed").count()
    return Response({"total": total, "completed": completed, "percent": round((completed / total * 100), 2) if total else 0})


def _workflow_execute(request, path):
    workflow = _required_record(Workflow, request.user, request.data.get("workflow_id"), "workflow_id")
    execution = WorkflowExecutor.execute(workflow, request.user, request.data.get("inputs", {}))
    return Response(_serialize(execution), status=status.HTTP_201_CREATED)


def _checkpoint_restore(request, path):
    checkpoint = _required_record(Checkpoint, request.user, request.data.get("checkpoint_id"), "checkpoint_id")
    return Response({"checkpoint": _serialize(checkpoint), "context": (checkpoint.configuration or {}).get("context", {})})


def _tool_execute(request, path):
    tool = _required_record(Tool, request.user, request.data.get("tool_id"), "tool_id")
    result = ToolExecutor.execute(tool, request.user, request.data.get("input", {}))
    return Response(result.as_dict(), status=status.HTTP_201_CREATED)


def _tool_register(request, path):
    handler = str(request.data.get("handler", "")).strip().lower()
    definition = ToolExecutor.definition(handler)
    required_permission = str(request.data.get("required_permission", "")).strip()
    permissions = list(definition.permissions)
    if required_permission:
        from echo.apps.authentication.models import Permission
        if not Permission.objects.filter(codename=required_permission).exists():
            raise ValidationError({"required_permission": "Unknown Echo permission codename."})
        if required_permission not in permissions:
            permissions.append(required_permission)
    tool = Tool.objects.create(
        owner=request.user,
        name=str(request.data.get("name", handler)),
        title=str(request.data.get("title", handler.replace(".", " ").title())),
        description=str(request.data.get("description", definition.description)),
        status="active",
        category=str(request.data.get("category", "builtin")),
        configuration={
            "handler": handler,
            "required_permissions": permissions,
            "input_schema": definition.input_schema,
            "output_schema": definition.output_schema,
            "result_format": definition.result_format,
            "confirmation": definition.confirmation,
            "cancellable": definition.cancellable,
            "execution_mode": definition.execution_mode,
            "timeout": definition.timeout,
            "risk_level": definition.risk_level,
            "agent_access": list(definition.agent_access),
            "registry_source": definition.source,
        },
    )
    return Response(_serialize(tool), status=status.HTTP_201_CREATED)


def _tool_registry(request, path):
    tools = Tool.objects.filter(owner=request.user)
    return Response({"handlers": ToolExecutor.runtime_handlers(), "registered_handlers": ToolExecutor.available_handlers(), "definitions": ToolExecutor.definitions(), "tools": _serialize(tools, many=True)})


def _tool_health(request, path):
    executions = ToolExecution.objects.filter(owner=request.user)
    registry = ToolExecutor.validation_report()
    data = {
        "healthy": bool(registry.get("ok")),
        "handlers": len(registry.get("registered_tools") or []),
        "tools": Tool.objects.filter(owner=request.user, status="active").count(),
        "completed": executions.filter(status="completed").count(),
        "failed": executions.filter(status="failed").count(),
        "registry_issues": registry.get("issues") or [],
    }
    ToolHealth.objects.create(
        owner=request.user,
        name="tool_registry",
        title="Tool registry health",
        status="healthy" if data["healthy"] else "failed",
        category="health",
        configuration=data,
    )
    return Response(data, status=status.HTTP_200_OK if data["healthy"] else status.HTTP_503_SERVICE_UNAVAILABLE)


def _task_time_start(request, path):
    task = _required_record(Task, request.user, request.data.get("task_id"), "task_id")
    return Response(_serialize(TimeTrackingService.start(task, request.user)), status=status.HTTP_201_CREATED)


def _task_time_stop(request, path):
    entry = _required_record(TimeEntry, request.user, request.data.get("time_entry_id"), "time_entry_id")
    return Response(_serialize(TimeTrackingService.stop(entry, request.user)))


def _calendar_availability(request, path):
    start = request.query_params.get("start")
    end = request.query_params.get("end")
    if not start or not end:
        raise ValidationError({"start": "start and end ISO date-times are required."})
    from echo.apps.calendar.scheduling import _parse_datetime

    conflicts = SchedulingService.conflicts(
        request.user,
        _parse_datetime(start, "start"),
        _parse_datetime(end, "end"),
    )
    return Response({"available": not conflicts, "conflicts": _serialize(conflicts, many=True) if conflicts else []})


def _calendar_sync(request, path):
    events = request.data.get("events")
    if not isinstance(events, list):
        raise ValidationError({"events": "A list of event objects is required."})
    created = [SchedulingService.create_event(request.user, item) for item in events]
    return Response({"count": len(created), "events": _serialize(created, many=True)}, status=status.HTTP_201_CREATED)


def _email_send(request, path):
    to = request.data.get("to")
    if isinstance(to, str):
        to = [to]
    if not isinstance(to, list) or not to:
        raise ValidationError({"to": "At least one recipient is required."})
    reply_to = request.data.get("reply_to", [])
    if isinstance(reply_to, str):
        reply_to = [reply_to]
    sent = SMTPMailer().send(
        str(request.data.get("subject", "")),
        str(request.data.get("text", "")),
        to,
        html=request.data.get("html"),
        reply_to=reply_to,
    )
    return Response({"sent": sent})


def _email_sync(request, path):
    account = _required_record(EmailAccount, request.user, request.data.get("account_id"), "account_id")
    return Response(IMAPSyncService.sync(account, int(request.data.get("limit", 50))))


def _notification_create(request, path):
    notification = Notification.objects.create(
        owner=request.user,
        name=str(request.data.get("name", "notification")),
        title=str(request.data.get("title", "Echo notification")),
        description=str(request.data.get("message", request.data.get("description", ""))),
        status="queued",
        category=str(request.data.get("category", "general")),
        configuration=request.data.get("configuration", {}),
        data=request.data.get("data", {}),
    )
    result = NotificationDispatcher.deliver(notification, str(request.data.get("channel", "database")))
    return Response({"notification": _serialize(notification), "delivery": result.__dict__}, status=status.HTTP_201_CREATED)


def _project_backup(request, path):
    return Response(ProjectPortabilityService.export(request.user))


def _project_restore(request, path):
    fixture = request.data.get("records")
    if not isinstance(fixture, str):
        raise ValidationError({"records": "The records field must contain a Django JSON fixture string."})
    return Response({"restored": ProjectPortabilityService.restore(request.user, fixture)}, status=status.HTTP_201_CREATED)


def _analytics_aggregate(request, path):
    aggregate = AnalyticsCollector.aggregate(request.user, int(request.query_params.get("days", request.data.get("days", 30))))
    return Response(_serialize(aggregate))


def _agent_performance(request, path):
    records = AgentPerformance.objects.filter(owner=request.user)
    return Response({"count": records.count(), "results": _serialize(records, many=True)})


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
        return True
    except (ValueError, TypeError, AttributeError):
        return False



GET_HANDLERS: dict[str, Handler] = {
    "core/health": _database_status,
    "core/status": _database_status,
    "core/version": _version,
    "dashboard": _dashboard,
    "dashboard/home": _dashboard,
    "chat/search": _chat_search,
    "ai/history": lambda request, path: Response(_serialize(_owned(apps.get_model("ai_engine", "AIRequest"), request.user)[:100], many=True)),
    "memory/search": _memory_search,
    "vector/index": _vector_index,
    "knowledge/search": _knowledge_search,
    "documents/search": _document_search,
    "internet/history": lambda request, path: Response(_serialize(_owned(SearchQuery, request.user)[:100], many=True)),
    "internet/downloads": lambda request, path: Response(_serialize(_owned(Download, request.user)[:100], many=True)),
    "internet/monitoring": lambda request, path: _database_status(request, path),
    "planner/progress": _planner_progress,
    "agents/performance": _agent_performance,
    "tools/registry": _tool_registry,
    "tools/health": _tool_health,
    "tools/analytics": _tool_health,
    "tasks/analytics": lambda request, path: Response({"tasks": Task.objects.filter(owner=request.user).count(), "time_entries": TimeEntry.objects.filter(owner=request.user).count()}),
    "calendar/availability": _calendar_availability,
    "code/search": _code_search,
}

POST_HANDLERS: dict[str, Handler] = {
    "dashboard/refresh": _dashboard,
    "dashboard/layout/reset": _dashboard_layout_reset,
    "chat/export": _chat_export,
    "ai/generate": _ai_generate,
    "ai/request": _ai_generate,
    "ai/stream": _ai_stream,
    "vector/embed": _vector_embed,
    "vector/embed/batch": _vector_embed,
    "vector/search": _vector_search,
    "vector/hybrid-search": _vector_search,
    "vector/index": _vector_index,
    "knowledge/import": _knowledge_import,
    "knowledge/export": _knowledge_export,
    "knowledge/rollback": _knowledge_rollback,
    "documents/upload": _document_upload,
    "internet/search": _internet_search,
    "internet/news": _internet_search,
    "internet/images": _internet_search,
    "internet/videos": _internet_search,
    "internet/fetch": _internet_fetch,
    "internet/crawl": _internet_crawl,
    "internet/download": _internet_download,
    "code/analyze": _code_analyze,
    "code/review": _code_ai,
    "code/generate": _code_ai,
    "code/refactor": _code_ai,
    "code/tests": _code_ai,
    "code/documentation": _code_ai,
    "planner/plans": _planner_build,
    "planner/steps/reorder": _planner_reorder,
    "workflows/execute": _workflow_execute,
    "workflows/checkpoints/restore": _checkpoint_restore,
    "tools/execute": _tool_execute,
    "tools/register": _tool_register,
    "tasks/time/start": _task_time_start,
    "tasks/time/stop": _task_time_stop,
    "calendar/sync": _calendar_sync,
    "email/send": _email_send,
    "email/sync": _email_sync,
    "notifications": _notification_create,
    "projects/backup": _project_backup,
    "projects/restore": _project_restore,
    "analytics/aggregate": _analytics_aggregate,
}

PUT_HANDLERS: dict[str, Handler] = {
    "vector/index/rebuild": _vector_index,
}


def dispatch_operation(request, resource_path: str):
    path = resource_path.strip("/")
    if request.method == "GET" and path.startswith("chat/share/"):
        return _chat_share(request, path)
    if request.method == "GET" and path.startswith("documents/") and path.endswith("/preview"):
        return _document_preview(request, path)
    if request.method == "POST" and path.startswith("documents/") and path.endswith("/export"):
        return _document_export(request, path)
    handlers = {
        "GET": GET_HANDLERS,
        "POST": POST_HANDLERS,
        "PUT": PUT_HANDLERS,
    }.get(request.method, {})
    handler = handlers.get(path)
    if handler is None:
        return None
    try:
        return handler(request, path)
    except DjangoValidationError as exc:
        if hasattr(exc, "message_dict"):
            raise ValidationError(exc.message_dict) from exc
        raise ValidationError(exc.messages) from exc
