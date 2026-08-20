from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Any

from django.db import transaction
from django.db.models import Model, QuerySet


@dataclass(frozen=True)
class ServiceResult:
    value: Any
    changed: bool = False


class DomainService:
    model: type[Model] | None = None

    def __init__(self, actor=None):
        self.actor = actor

    def queryset(self) -> QuerySet:
        if self.model is None:
            raise RuntimeError('Service model is not configured.')
        queryset = self.model.objects.all()
        names = {field.name for field in self.model._meta.fields}
        if self.actor and not self.actor.is_staff:
            if 'owner' in names:
                queryset = queryset.filter(owner=self.actor)
            elif 'user' in names:
                queryset = queryset.filter(user=self.actor)
            else:
                queryset = queryset.none()
        return queryset

    def _emit(self, signal_name: str, instance: Model) -> None:
        module = import_module(f'{instance._meta.app_config.name}.signals')
        signal = getattr(module, signal_name, None)
        if signal is not None:
            signal.send(sender=instance.__class__, instance=instance, actor=self.actor)

    @transaction.atomic
    def create(self, **values) -> ServiceResult:
        if self.model is None:
            raise RuntimeError('Service model is not configured.')
        names = {field.name for field in self.model._meta.fields}
        if self.actor and 'owner' in names and 'owner' not in values:
            values['owner'] = self.actor
        if self.actor and 'user' in names and 'user' not in values:
            values['user'] = self.actor
        value = self.model(**values)
        value.full_clean()
        value.save()
        self._emit('record_created', value)
        return ServiceResult(value=value, changed=True)

    @transaction.atomic
    def update(self, instance: Model, **values) -> ServiceResult:
        for key, value in values.items():
            setattr(instance, key, value)
        instance.full_clean()
        instance.save()
        self._emit('record_updated', instance)
        return ServiceResult(value=instance, changed=True)
