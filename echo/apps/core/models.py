from __future__ import annotations

from django.conf import settings
from django.db import models
from echo.common.models import DomainModel

class SystemConfiguration(DomainModel):
    key = models.CharField(max_length=255, unique=True)
    value = models.JSONField(default=dict, blank=True)
    value_type = models.CharField(max_length=255, blank=True, db_index=False)
    editable = models.BooleanField(default=False)
    category = models.CharField(max_length=255, blank=True, db_index=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'System Configuration'
        verbose_name_plural = 'System Configuration records'


class FeatureFlag(DomainModel):
    enabled = models.BooleanField(default=False)
    rollout_percentage = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    environment = models.CharField(max_length=255, blank=True, db_index=False)

    class Meta(DomainModel.Meta):
        verbose_name = 'Feature Flag'
        verbose_name_plural = 'Feature Flag records'
        constraints = [models.UniqueConstraint(fields=['name'], name='unique_feature_flag_name')]


class SystemLog(DomainModel):
    level = models.CharField(max_length=255, blank=True, db_index=False)
    module = models.CharField(max_length=255, blank=True, db_index=False)
    message = models.TextField(blank=True)
    details = models.JSONField(default=dict, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name='core_system_log_user')
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'System Log'
        verbose_name_plural = 'System Log records'


class AuditLog(DomainModel):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name='core_audit_log_actor')
    action = models.CharField(max_length=255, blank=True, db_index=False)
    object_type = models.CharField(max_length=255, blank=True, db_index=False)
    object_id = models.UUIDField(null=True, blank=True, db_index=True)
    old_data = models.JSONField(default=dict, blank=True)
    new_data = models.JSONField(default=dict, blank=True)
    timestamp = models.CharField(max_length=255, blank=True, db_index=False)

    class Meta(DomainModel.Meta):
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Log records'


class ScheduledTask(DomainModel):
    task_path = models.CharField(max_length=255, blank=True, db_index=False)
    last_run = models.DateTimeField(null=True, blank=True, db_index=True)
    next_run = models.DateTimeField(null=True, blank=True, db_index=True)
    enabled = models.BooleanField(default=False)
    retry_count = models.BigIntegerField(default=0)

    class Meta(DomainModel.Meta):
        verbose_name = 'Scheduled Task'
        verbose_name_plural = 'Scheduled Task records'


class UploadedFile(DomainModel):
    file_name = models.CharField(max_length=255, blank=True, db_index=False)
    original_name = models.CharField(max_length=255, blank=True, db_index=False)
    extension = models.CharField(max_length=255, blank=True, db_index=False)
    mime_type = models.CharField(max_length=255, blank=True, db_index=False)
    size = models.BigIntegerField(default=0)
    storage_path = models.URLField(max_length=2048, blank=True)
    checksum = models.TextField(blank=True)
    uploaded_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Uploaded File'
        verbose_name_plural = 'Uploaded File records'


class ApplicationRegistry(DomainModel):
    version = models.BigIntegerField(default=0)
    enabled = models.BooleanField(default=False)
    installed_at = models.DateTimeField(null=True, blank=True, db_index=True)
    last_updated = models.DateTimeField(null=True, blank=True, db_index=True)
    dependencies = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Application Registry'
        verbose_name_plural = 'Application Registry records'
        constraints = [models.UniqueConstraint(fields=['name'], name='unique_application_registry_name')]

