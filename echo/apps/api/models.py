from __future__ import annotations

from django.conf import settings
from django.db import models
from echo.common.models import DomainModel

class APIClient(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'A P I Client'
        verbose_name_plural = 'A P I Client records'


class APIKey(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'A P I Key'
        verbose_name_plural = 'A P I Key records'


class APIRequestLog(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'A P I Request Log'
        verbose_name_plural = 'A P I Request Log records'


class WebhookEndpoint(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Webhook Endpoint'
        verbose_name_plural = 'Webhook Endpoint records'


class WebhookDelivery(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Webhook Delivery'
        verbose_name_plural = 'Webhook Delivery records'


class IdempotencyRecord(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Idempotency Record'
        verbose_name_plural = 'Idempotency Record records'

