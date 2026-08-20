from __future__ import annotations

from django.conf import settings
from django.db import models
from echo.common.models import DomainModel

class Calendar(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Calendar'
        verbose_name_plural = 'Calendar records'


class Event(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Event'
        verbose_name_plural = 'Event records'


class EventParticipant(DomainModel):
    response_status = models.CharField(max_length=255, blank=True, db_index=False)

    class Meta(DomainModel.Meta):
        verbose_name = 'Event Participant'
        verbose_name_plural = 'Event Participant records'


class RecurrenceRule(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Recurrence Rule'
        verbose_name_plural = 'Recurrence Rule records'


class Reminder(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Reminder'
        verbose_name_plural = 'Reminder records'


class AvailabilityRule(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Availability Rule'
        verbose_name_plural = 'Availability Rule records'


class TimeBlock(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Time Block'
        verbose_name_plural = 'Time Block records'

