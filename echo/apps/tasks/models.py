from __future__ import annotations

from django.conf import settings
from django.db import models
from echo.common.models import DomainModel

class Task(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Task'
        verbose_name_plural = 'Task records'


class SubTask(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Sub Task'
        verbose_name_plural = 'Sub Task records'


class TaskDependency(DomainModel):
    dependency_types = models.CharField(max_length=255, blank=True, db_index=False)

    class Meta(DomainModel.Meta):
        verbose_name = 'Task Dependency'
        verbose_name_plural = 'Task Dependency records'


class Reminder(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Reminder'
        verbose_name_plural = 'Reminder records'


class RecurrenceRule(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Recurrence Rule'
        verbose_name_plural = 'Recurrence Rule records'


class TaskAttachment(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Task Attachment'
        verbose_name_plural = 'Task Attachment records'


class TimeEntry(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Time Entry'
        verbose_name_plural = 'Time Entry records'


class TaskActivity(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Task Activity'
        verbose_name_plural = 'Task Activity records'

