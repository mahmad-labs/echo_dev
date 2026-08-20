from __future__ import annotations

from django.conf import settings
from django.db import models
from echo.common.models import DomainModel

class AnalyticsEvent(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Analytics Event'
        verbose_name_plural = 'Analytics Event records'


class MetricDefinition(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Metric Definition'
        verbose_name_plural = 'Metric Definition records'


class MetricPoint(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Metric Point'
        verbose_name_plural = 'Metric Point records'


class Report(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Report'
        verbose_name_plural = 'Report records'


class DashboardSnapshot(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Dashboard Snapshot'
        verbose_name_plural = 'Dashboard Snapshot records'


class UsageAggregate(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Usage Aggregate'
        verbose_name_plural = 'Usage Aggregate records'

