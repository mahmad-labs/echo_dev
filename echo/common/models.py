from __future__ import annotations

import uuid
from django.conf import settings
from django.db import models


class UUIDModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ('-created_at',)


class OwnedModel(UUIDModel):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name='%(app_label)s_%(class)s_owned')

    class Meta(UUIDModel.Meta):
        abstract = True


class DomainModel(OwnedModel):
    name = models.CharField(max_length=255, blank=True, db_index=True)
    title = models.CharField(max_length=255, blank=True, db_index=True)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=64, default='active', db_index=True)
    data = models.JSONField(default=dict, blank=True)

    class Meta(OwnedModel.Meta):
        abstract = True

    def __str__(self) -> str:
        return self.title or self.name or f'{self.__class__.__name__} {self.pk}'
