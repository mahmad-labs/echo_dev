from __future__ import annotations

from django.conf import settings
from django.db import models
from echo.common.models import DomainModel

class CodeProject(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Code Project'
        verbose_name_plural = 'Code Project records'


class SourceFile(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Source File'
        verbose_name_plural = 'Source File records'


class CodeSymbol(DomainModel):
    supported_types = models.CharField(max_length=255, blank=True, db_index=False)

    class Meta(DomainModel.Meta):
        verbose_name = 'Code Symbol'
        verbose_name_plural = 'Code Symbol records'


class CodeReview(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Code Review'
        verbose_name_plural = 'Code Review records'


class CodeIssue(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Code Issue'
        verbose_name_plural = 'Code Issue records'


class Dependency(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Dependency'
        verbose_name_plural = 'Dependency records'


class TestSuite(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Test Suite'
        verbose_name_plural = 'Test Suite records'

