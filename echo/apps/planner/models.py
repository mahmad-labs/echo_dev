from __future__ import annotations

from django.conf import settings
from django.db import models
from echo.common.models import DomainModel

class Goal(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Goal'
        verbose_name_plural = 'Goal records'


class ExecutionPlan(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Execution Plan'
        verbose_name_plural = 'Execution Plan records'


class PlanStep(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Plan Step'
        verbose_name_plural = 'Plan Step records'


class StepDependency(DomainModel):
    dependency_types = models.CharField(max_length=255, blank=True, db_index=False)

    class Meta(DomainModel.Meta):
        verbose_name = 'Step Dependency'
        verbose_name_plural = 'Step Dependency records'


class PlanningSession(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Planning Session'
        verbose_name_plural = 'Planning Session records'


class RiskAssessment(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Risk Assessment'
        verbose_name_plural = 'Risk Assessment records'

