from __future__ import annotations

from django.core.exceptions import PermissionDenied, ValidationError as DjangoValidationError
from rest_framework import permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from echo.apps.tool_manager.execution import ToolExecutionError, ToolExecutor

from .computer_use import (
    BrowserObservationService,
    BrowserSessionService,
    ComputerUseError,
    ComputerUseOperationService,
    HumanInterventionRequired,
    MediaUnderstandingService,
)
from .models import (
    BrowserAction, BrowserObservation, BrowserSession, ComputerUseOperation, MediaUnderstanding,
    ComputerSession, ComputerObservation, ComputerAction,
)
from .desktop_control import (
    ComputerSessionService, ComputerObservationService,
    DesktopUnavailable,
)


def _require_tools_execute(user) -> None:
    """Require Echo's own execution permission without bypassing role policy."""
    if user.is_staff or user.is_superuser:
        return
    role_granted = user.roles.filter(permission_links__permission__codename="tools.execute").exists()
    if not (role_granted or user.has_perm("tools.execute")):
        raise PermissionDenied("Permission 'tools.execute' is required.")


def _session_payload(session: BrowserSession) -> dict:
    return {
        "id": str(session.pk), "status": session.status, "engine": session.engine, "headless": session.headless,
        "current_url": session.current_url, "current_title": session.current_title, "active_tab_handle": session.active_tab_handle,
        "started_at": session.started_at, "ended_at": session.ended_at, "last_activity_at": session.last_activity_at,
    }


def _observation_payload(item: BrowserObservation, *, include_dom: bool = True) -> dict:
    payload = {
        "id": str(item.pk), "session_id": str(item.session_id), "sequence": item.sequence, "url": item.url,
        "title": item.page_title, "visible_text": item.visible_text, "viewport": item.viewport, "media": item.media,
        "content_hash": item.content_hash, "observed_at": item.observed_at,
        "screenshot_url": item.screenshot.url if item.screenshot else None,
    }
    if include_dom:
        payload["dom"] = item.dom
        payload["accessibility_tree"] = item.accessibility_tree
    return payload


def _operation_payload(item: ComputerUseOperation) -> dict:
    return {
        "id": str(item.pk), "status": item.status, "request": item.request_text, "plan": item.plan,
        "current_step": item.current_step, "progress": item.progress, "current_operation": item.current_operation,
        "current_tool": item.current_tool, "cancellable": item.cancellable, "cancel_requested": item.cancel_requested,
        "result": item.result, "error": item.error_message or None, "started_at": item.started_at,
        "completed_at": item.completed_at, "session_id": str(item.session_id) if item.session_id else None,
        "attention": (item.configuration or {}).get("attention"),
    }


class BrowserSessionListCreateView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        query = BrowserSession.objects.all() if request.user.is_staff else BrowserSession.objects.filter(owner=request.user)
        return Response({"sessions": [_session_payload(item) for item in query.order_by("-last_activity_at", "-created_at")[:30]]})

    def post(self, request):
        _require_tools_execute(request.user)
        session = BrowserSessionService.create(request.user, engine=request.data.get("engine"), headless=request.data.get("headless"))
        return Response({"session": _session_payload(session)}, status=status.HTTP_201_CREATED)


class BrowserSessionEndView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, pk):
        return Response({"session": _session_payload(BrowserSessionService.close(request.user, pk))})


class BrowserObserveView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request):
        try:
            session = BrowserSessionService.get(request.user, request.data.get("session_id")) if request.data.get("session_id") else BrowserSessionService.current(request.user, create=True)
            item = BrowserObservationService.observe(request.user, session, screenshot=bool(request.data.get("screenshot", True)), reason="api")
            return Response({"observation": _observation_payload(item)})
        except Exception as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class BrowserActionView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request):
        _require_tools_execute(request.user)
        action_type = str(request.data.get("action") or "").strip()
        if not action_type:
            raise ValidationError({"action": "An action is required."})
        session = BrowserSessionService.get(request.user, request.data.get("session_id")) if request.data.get("session_id") else BrowserSessionService.current(request.user, create=True)
        arguments = request.data.get("input") or {}
        if not isinstance(arguments, dict):
            raise ValidationError({"input": "input must be an object."})
        try:
            execution = ToolExecutor.execute_named(
                f"browser.{action_type}",
                request.user,
                {**arguments, "browser_session_id": str(session.pk)},
                agent="browser",
            )
            outcome = execution.output if isinstance(execution.output, dict) else {}
            return Response({
                "ok": bool(outcome.get("ok")),
                "action_id": outcome.get("action_id"),
                "verified": bool(outcome.get("ok")),
                "result": outcome,
                "observation_id": outcome.get("observation_id"),
                "tool_execution_id": execution.execution_id,
            }, status=status.HTTP_201_CREATED)
        except ToolExecutionError as exc:
            details = exc.details if isinstance(exc.details, dict) else {}
            reason = str(details.get("reason") or exc.error_type or "tool_error")
            detail = str(details.get("detail") or exc)
            if reason in {"approval", "captcha", "login", "mfa", "permission", "human_intervention"}:
                return Response({"detail": detail, "attention": {"type": reason, "detail": detail}}, status=status.HTTP_409_CONFLICT)
            return Response(exc.as_dict(), status=status.HTTP_400_BAD_REQUEST)
        except (DjangoValidationError, PermissionDenied) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class ComputerUseOperationListCreateView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        query = ComputerUseOperation.objects.all() if request.user.is_staff else ComputerUseOperation.objects.filter(owner=request.user)
        active = request.query_params.get("active")
        if active in {"1", "true", "yes"}:
            query = query.filter(status__in=("queued", "running", "waiting_user", "cancelling"))
        return Response({"operations": [_operation_payload(item) for item in query.order_by("-updated_at")[:50]]})

    def post(self, request):
        _require_tools_execute(request.user)
        prompt = str(request.data.get("request") or request.data.get("prompt") or "").strip()
        if not prompt:
            raise ValidationError({"request": "A computer-use request is required."})
        session = BrowserSessionService.get(request.user, request.data.get("session_id")) if request.data.get("session_id") else None
        try:
            operation = ComputerUseOperationService.create(request.user, prompt, session=session)
            queue_id = ComputerUseOperationService.dispatch(operation)
        except ComputerUseError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        payload = _operation_payload(operation)
        payload["queue_task_id"] = queue_id
        return Response({"operation": payload}, status=status.HTTP_202_ACCEPTED)


class ComputerUseOperationDetailView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, pk):
        query = ComputerUseOperation.objects.all() if request.user.is_staff else ComputerUseOperation.objects.filter(owner=request.user)
        item = query.filter(pk=pk).first()
        if not item:
            return Response({"detail": "Operation was not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response({"operation": _operation_payload(item)})


class ComputerUseOperationCancelView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, pk):
        try:
            item = ComputerUseOperationService.cancel(request.user, pk)
            return Response({"operation": _operation_payload(item)})
        except ComputerUseError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class ComputerUseOperationResumeView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, pk):
        _require_tools_execute(request.user)
        try:
            item, queue_id = ComputerUseOperationService.resume(request.user, pk)
            payload = _operation_payload(item)
            payload["queue_task_id"] = queue_id
            return Response({"operation": payload}, status=status.HTTP_202_ACCEPTED)
        except ComputerUseError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class MediaAnalyzeView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request):
        _require_tools_execute(request.user)
        session = BrowserSessionService.get(request.user, request.data.get("session_id")) if request.data.get("session_id") else BrowserSessionService.current(request.user, create=True)
        prompt = str(request.data.get("request") or "Watch and listen to the current media").strip()[:2000]
        try:
            # Media analysis may perform caption extraction, bounded audio transcription,
            # visual sampling, and model synthesis, so it is always a durable operation.
            # This dedicated endpoint cannot be repurposed into arbitrary browser steps.
            operation = ComputerUseOperation.objects.create(
                owner=request.user, session=session, name="media-analysis", title="Analyze current media",
                description="Evidence-backed media analysis operation.", status="queued", request_text=prompt,
                plan=[{"tool": "media.analyze", "input": {}, "description": "Process accessible media evidence"}],
                current_step=0, progress=0, cancellable=True, configuration={"planner": "fixed_media_analysis", "max_replans": 0},
            )
            queue_id = ComputerUseOperationService.dispatch(operation)
            payload = _operation_payload(operation)
            payload["queue_task_id"] = queue_id
            return Response({"operation": payload}, status=status.HTTP_202_ACCEPTED)
        except ComputerUseError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)


class MediaQuestionView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request):
        question = str(request.data.get("question") or "").strip()
        if not question:
            raise ValidationError({"question": "A question is required."})
        result = MediaUnderstandingService.answer_latest(request.user, question)
        return Response(result, status=status.HTTP_200_OK if result.get("ok") else status.HTTP_422_UNPROCESSABLE_ENTITY)

def _desktop_session_payload(session: ComputerSession) -> dict:
    return {
        "id": str(session.pk), "status": session.status, "environment": session.environment,
        "display_name": session.display_name, "active_window": session.active_window,
        "started_at": session.started_at, "ended_at": session.ended_at, "last_activity_at": session.last_activity_at,
    }


def _desktop_observation_payload(item: ComputerObservation, *, include_structured: bool = True) -> dict:
    payload = {
        "id": str(item.pk), "session_id": str(item.session_id), "sequence": item.sequence,
        "window": item.window_info, "cursor": item.cursor, "viewport": item.viewport,
        "ocr_text": item.ocr_text, "content_hash": item.content_hash, "observed_at": item.observed_at,
        "screenshot_url": item.screenshot.url if item.screenshot else None,
    }
    if include_structured:
        payload["ui_tree"] = item.ui_tree
        payload["vision"] = item.vision
    return payload


class DesktopSessionListCreateView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        query = ComputerSession.objects.all() if request.user.is_staff else ComputerSession.objects.filter(owner=request.user)
        return Response({"sessions": [_desktop_session_payload(item) for item in query.order_by("-last_activity_at", "-created_at")[:30]]})

    def post(self, request):
        _require_tools_execute(request.user)
        try:
            session = ComputerSessionService.create(request.user)
            return Response({"session": _desktop_session_payload(session)}, status=status.HTTP_201_CREATED)
        except (DesktopUnavailable, DjangoValidationError) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class DesktopSessionEndView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, pk):
        try:
            return Response({"session": _desktop_session_payload(ComputerSessionService.close(request.user, pk))})
        except DesktopUnavailable as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_404_NOT_FOUND)


class DesktopObserveView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request):
        _require_tools_execute(request.user)
        try:
            session = ComputerSessionService.get(request.user, request.data.get("session_id")) if request.data.get("session_id") else ComputerSessionService.current(request.user, create=True)
            observation = ComputerObservationService.observe(
                request.user, session, vision=bool(request.data.get("vision", False)),
                target_hint=str(request.data.get("target_hint") or "")[:500], reason="api",
            )
            return Response({"observation": _desktop_observation_payload(observation)}, status=status.HTTP_201_CREATED)
        except (DesktopUnavailable, DjangoValidationError, PermissionDenied) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class DesktopActionView(APIView):
    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request):
        _require_tools_execute(request.user)
        action = str(request.data.get("action") or "").strip()
        arguments = request.data.get("input") or {}
        if not action:
            raise ValidationError({"action": "An action is required."})
        if not isinstance(arguments, dict):
            raise ValidationError({"input": "input must be an object."})
        try:
            session = ComputerSessionService.get(request.user, request.data.get("session_id")) if request.data.get("session_id") else ComputerSessionService.current(request.user, create=True)
            execution = ToolExecutor.execute_named(
                f"computer.{action}",
                request.user,
                {**arguments, "computer_session_id": str(session.pk)},
                agent="computer",
            )
            outcome = execution.output if isinstance(execution.output, dict) else {}
            return Response({
                "ok": bool(outcome.get("ok")), "verified": bool(outcome.get("ok")),
                "action_id": outcome.get("action_id"), "observation_id": outcome.get("observation_id"),
                "session_id": str(session.pk), "result": outcome, "tool_execution_id": execution.execution_id,
            }, status=status.HTTP_201_CREATED)
        except ToolExecutionError as exc:
            details = exc.details if isinstance(exc.details, dict) else {}
            reason = str(details.get("reason") or exc.error_type or "tool_error")
            detail = str(details.get("detail") or exc)
            if reason in {"approval", "permission", "human_intervention"}:
                return Response({"detail": detail, "attention": {"type": reason, "detail": detail}}, status=status.HTTP_409_CONFLICT)
            return Response(exc.as_dict(), status=status.HTTP_400_BAD_REQUEST)
        except (DesktopUnavailable, DjangoValidationError, PermissionDenied) as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

