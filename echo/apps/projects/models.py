from __future__ import annotations

from django.conf import settings
from django.db import models
from echo.common.models import DomainModel

class Workspace(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Workspace'
        verbose_name_plural = 'Workspace records'


class Project(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Project'
        verbose_name_plural = 'Project records'


class ProjectMember(DomainModel):
    roles = models.CharField(max_length=255, blank=True, db_index=False)

    class Meta(DomainModel.Meta):
        verbose_name = 'Project Member'
        verbose_name_plural = 'Project Member records'


class ProjectLabel(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Project Label'
        verbose_name_plural = 'Project Label records'


class ProjectMilestone(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Project Milestone'
        verbose_name_plural = 'Project Milestone records'


class ProjectActivity(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Project Activity'
        verbose_name_plural = 'Project Activity records'


class ProjectSettings(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Project Settings'
        verbose_name_plural = 'Project Settings records'

