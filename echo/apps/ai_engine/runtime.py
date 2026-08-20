from __future__ import annotations

import time

from django.utils import timezone

from .models import AIRequest, AIResponse
from .provider import OpenAICompatibleProvider


class AIExecutionService:
    @classmethod
    def generate(cls, user, messages, *, model=None, temperature=0.2):
        started = timezone.now()
        request_record = AIRequest.objects.create(
            owner=user,
            user=user,
            name="chat_completion",
            title="AI generation request",
            status="running",
            model=model or "",
            started_at=started,
            data={"messages": messages, "temperature": temperature},
        )
        start_clock = time.monotonic()
        try:
            content, payload = OpenAICompatibleProvider().complete(
                messages,
                model=model,
                temperature=temperature,
            )
        except Exception:
            request_record.status = "failed"
            request_record.completed_at = timezone.now()
            request_record.latency = int((time.monotonic() - start_clock) * 1000)
            request_record.save(update_fields=["status", "completed_at", "latency", "updated_at"])
            raise

        usage = payload.get("usage", {}) if isinstance(payload, dict) else {}
        request_record.status = "completed"
        request_record.completed_at = timezone.now()
        request_record.latency = int((time.monotonic() - start_clock) * 1000)
        request_record.prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
        request_record.completion_tokens = int(usage.get("completion_tokens", 0) or 0)
        request_record.save(
            update_fields=[
                "status",
                "completed_at",
                "latency",
                "prompt_tokens",
                "completion_tokens",
                "updated_at",
            ]
        )
        response_record = AIResponse.objects.create(
            owner=user,
            name="chat_completion",
            title="AI generation response",
            status="completed",
            request=str(request_record.pk),
            content=content,
            finish_reason=str(payload.get("choices", [{}])[0].get("finish_reason", "")),
            tool_calls=payload.get("choices", [{}])[0].get("message", {}).get("tool_calls") or {},
            data={"provider_response_id": payload.get("id")},
        )
        return request_record, response_record, payload
