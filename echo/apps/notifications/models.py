from __future__ import annotations

from django.conf import settings
from django.db import models
from echo.common.models import DomainModel

class Notification(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Notification'
        verbose_name_plural = 'Notification records'


class NotificationChannel(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Notification Channel'
        verbose_name_plural = 'Notification Channel records'


class NotificationPreference(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Notification Preference'
        verbose_name_plural = 'Notification Preference records'


class NotificationTemplate(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Notification Template'
        verbose_name_plural = 'Notification Template records'


class DeliveryLog(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Delivery Log'
        verbose_name_plural = 'Delivery Log records'


class NotificationDigest(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Notification Digest'
        verbose_name_plural = 'Notification Digest records'

