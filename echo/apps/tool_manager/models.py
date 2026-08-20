from __future__ import annotations

from django.conf import settings
from django.db import models
from echo.common.models import DomainModel

class Tool(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Tool'
        verbose_name_plural = 'Tool records'


class ToolCapability(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Tool Capability'
        verbose_name_plural = 'Tool Capability records'


class ToolExecution(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Tool Execution'
        verbose_name_plural = 'Tool Execution records'


class ToolPermission(DomainModel):
    permission_levels = models.CharField(max_length=255, blank=True, db_index=False)

    class Meta(DomainModel.Meta):
        verbose_name = 'Tool Permission'
        verbose_name_plural = 'Tool Permission records'


class ToolSecretReference(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Tool Secret Reference'
        verbose_name_plural = 'Tool Secret Reference records'


class ToolHealth(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Tool Health'
        verbose_name_plural = 'Tool Health records'

