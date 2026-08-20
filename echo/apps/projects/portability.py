from __future__ import annotations

from typing import Any

from django.apps import apps
from django.core import serializers
from django.db import transaction


class ProjectPortabilityService:
    """Export and restore user-owned project-domain records as Django JSON fixtures."""

    APP_LABEL = "projects"

    @classmethod
    def export(cls, user) -> dict[str, Any]:
        objects = []
        counts = {}
        for model in apps.get_app_config(cls.APP_LABEL).get_models():
            queryset = model.objects.filter(owner=user).order_by("created_at")
            records = list(queryset)
            counts[model._meta.model_name] = len(records)
            objects.extend(records)
        return {
            "format": "django-json-v1",
            "app": cls.APP_LABEL,
            "counts": counts,
            "records": serializers.serialize("json", objects),
        }

    @classmethod
    @transaction.atomic
    def restore(cls, user, fixture: str) -> dict[str, int]:
        restored: dict[str, int] = {}
        for deserialized in serializers.deserialize("json", fixture):
            obj = deserialized.object
            if obj._meta.app_label != cls.APP_LABEL:
                raise ValueError("Fixture contains records outside the projects domain.")
            if hasattr(obj, "owner_id"):
                obj.owner = user
            obj.pk = None
            obj.save()
            model_name = obj._meta.model_name
            restored[model_name] = restored.get(model_name, 0) + 1
        return restored
