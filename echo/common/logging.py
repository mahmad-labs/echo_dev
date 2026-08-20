import json
import logging
from datetime import datetime, timezone
from typing import Any

_SENSITIVE = ("api_key", "token", "secret", "password", "authorization", "cookie", "credential")


def _redact(value: Any, *, key: str = "") -> Any:
    lowered = str(key or "").casefold()
    if any(marker in lowered for marker in _SENSITIVE):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(k): _redact(v, key=str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_redact(item) for item in value[:100]]
    if isinstance(value, str) and len(value) > 8000:
        return value[:8000] + "…"
    return value


class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        event = getattr(record, "echo_event", None)
        if isinstance(event, dict):
            payload["event"] = _redact(event)
        correlation_id = getattr(record, "correlation_id", "")
        if correlation_id:
            payload["correlation_id"] = str(correlation_id)[:255]
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)
