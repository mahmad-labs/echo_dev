from __future__ import annotations

from typing import Any

from django.apps import apps


def app_database_health(app_label: str) -> dict[str, Any]:
    """Execute real, read-only ORM probes for every concrete model in an Echo app.

    This is intentionally small enough for Celery health tasks while avoiding the
    misleading historical pattern of returning ``{"status": "ok"}`` without
    touching the subsystem at all.
    """

    config = apps.get_app_config(app_label)
    checked: list[str] = []
    try:
        for model in config.get_models():
            # ``first`` forces a SQL query while transferring at most one scalar.
            model.objects.order_by().values_list("pk", flat=True).first()
            checked.append(model._meta.label_lower)
    except Exception as exc:
        return {
            "status": "failed",
            "component": app_label,
            "checked_models": checked,
            "error_type": exc.__class__.__name__,
            "error": str(exc),
        }
    return {
        "status": "healthy",
        "component": app_label,
        "checked_models": checked,
        "model_count": len(checked),
    }
