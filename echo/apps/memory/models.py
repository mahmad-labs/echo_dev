from __future__ import annotations

from django.conf import settings
from django.db import models
from echo.common.models import DomainModel

class Memory(DomainModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name='memory_memory_user')
    content = models.TextField(blank=True)
    summary = models.TextField(blank=True)
    memory_type = models.CharField(max_length=255, blank=True, db_index=False)
    category = models.CharField(max_length=255, blank=True, db_index=True)
    importance_score = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    confidence_score = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    access_count = models.BigIntegerField(default=0)
    last_accessed = models.CharField(max_length=255, blank=True, db_index=False)
    created_from = models.CharField(max_length=255, blank=True, db_index=False)
    source_type = models.CharField(max_length=255, blank=True, db_index=False)

    class Meta(DomainModel.Meta):
        verbose_name = 'Memory'
        verbose_name_plural = 'Memory records'


class MemoryCategory(DomainModel):
    color = models.CharField(max_length=255, blank=True, db_index=False)
    icon = models.CharField(max_length=255, blank=True, db_index=False)
    parent = models.CharField(max_length=255, blank=True, db_index=False)

    class Meta(DomainModel.Meta):
        verbose_name = 'Memory Category'
        verbose_name_plural = 'Memory Category records'


class MemoryTag(DomainModel):
    memory = models.ForeignKey('Memory', on_delete=models.CASCADE, null=True, blank=True, related_name='memory_tag_memory_items')
    tag = models.CharField(max_length=255, blank=True, db_index=False)

    class Meta(DomainModel.Meta):
        verbose_name = 'Memory Tag'
        verbose_name_plural = 'Memory Tag records'


class MemoryRelationship(DomainModel):
    source_memory = models.CharField(max_length=255, blank=True, db_index=False)
    target_memory = models.CharField(max_length=255, blank=True, db_index=False)
    relationship_type = models.CharField(max_length=255, blank=True, db_index=False)
    strength = models.DecimalField(max_digits=12, decimal_places=4, default=0)

    class Meta(DomainModel.Meta):
        verbose_name = 'Memory Relationship'
        verbose_name_plural = 'Memory Relationship records'


class MemorySnapshot(DomainModel):
    memory = models.ForeignKey('Memory', on_delete=models.CASCADE, null=True, blank=True, related_name='memory_snapshot_memory_items')
    version = models.BigIntegerField(default=0)
    content = models.TextField(blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Memory Snapshot'
        verbose_name_plural = 'Memory Snapshot records'


class MemoryAccessLog(DomainModel):
    memory = models.ForeignKey('Memory', on_delete=models.CASCADE, null=True, blank=True, related_name='memory_access_log_memory_items')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name='memory_memory_access_log_user')
    conversation = models.CharField(max_length=255, blank=True, db_index=False)
    reason = models.TextField(blank=True)
    retrieval_score = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    accessed_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Memory Access Log'
        verbose_name_plural = 'Memory Access Log records'


class MemoryRule(DomainModel):
    rule_type = models.CharField(max_length=255, blank=True, db_index=False)
    conditions = models.JSONField(default=dict, blank=True)
    actions = models.JSONField(default=dict, blank=True)
    enabled = models.BooleanField(default=False)

    class Meta(DomainModel.Meta):
        verbose_name = 'Memory Rule'
        verbose_name_plural = 'Memory Rule records'


class WorkingMemory(DomainModel):
    conversation = models.CharField(max_length=255, blank=True, db_index=False)
    context = models.JSONField(default=dict, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Working Memory'
        verbose_name_plural = 'Working Memory records'


class MemoryFeedback(DomainModel):
    memory = models.ForeignKey('Memory', on_delete=models.CASCADE, null=True, blank=True, related_name='memory_feedback_memory_items')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name='memory_memory_feedback_user')
    feedback = models.CharField(max_length=255, blank=True, db_index=False)
    rating = models.DecimalField(max_digits=12, decimal_places=4, default=0)

    class Meta(DomainModel.Meta):
        verbose_name = 'Memory Feedback'
        verbose_name_plural = 'Memory Feedback records'

