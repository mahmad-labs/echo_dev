from __future__ import annotations

from django.conf import settings
from django.db import models
from echo.common.models import DomainModel

class UserSetting(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'User Setting'
        verbose_name_plural = 'User Setting records'


class SystemSetting(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'System Setting'
        verbose_name_plural = 'System Setting records'


class FeaturePreference(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Feature Preference'
        verbose_name_plural = 'Feature Preference records'


class IntegrationSetting(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Integration Setting'
        verbose_name_plural = 'Integration Setting records'


class SecretReference(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Secret Reference'
        verbose_name_plural = 'Secret Reference records'


class ConfigurationAudit(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Configuration Audit'
        verbose_name_plural = 'Configuration Audit records'

