from __future__ import annotations

import logging
import time
import uuid

from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger(__name__)


class CorrelationIdMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        supplied = request.headers.get("X-Correlation-ID", "").strip()
        try:
            request.correlation_id = str(uuid.UUID(supplied)) if supplied else str(uuid.uuid4())
        except (ValueError, AttributeError):
            request.correlation_id = str(uuid.uuid4())

        started = time.monotonic()
        response = self.get_response(request)
        response["X-Correlation-ID"] = request.correlation_id
        response["X-Response-Time-ms"] = f"{(time.monotonic() - started) * 1000:.2f}"
        return response


class RequestAuditMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        user = getattr(request, "user", None)
        if request.path.startswith("/api/") and user and user.is_authenticated:
            try:
                from echo.apps.core.models import AuditLog

                AuditLog.objects.create(
                    owner=user,
                    actor=user,
                    action=f"{request.method} {request.path}",
                    object_type="http_request",
                    object_id=request.correlation_id,
                    new_data={"status_code": response.status_code},
                )
            except Exception:
                logger.exception("Unable to persist request audit record.")
        return response
