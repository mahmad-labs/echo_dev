from __future__ import annotations

from django.conf import settings
from django.db import models
from echo.common.models import DomainModel

class AIModel(DomainModel):
    provider = models.CharField(max_length=255, blank=True, db_index=False)
    model_identifier = models.CharField(max_length=255, blank=True, db_index=False)
    max_context = models.BigIntegerField(default=0)
    max_output_tokens = models.BigIntegerField(default=0)
    supports_streaming = models.BooleanField(default=False)
    supports_tools = models.BooleanField(default=False)
    supports_images = models.BooleanField(default=False)
    supports_audio = models.BooleanField(default=False)
    cost_input = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    cost_output = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    enabled = models.BooleanField(default=False)

    class Meta(DomainModel.Meta):
        verbose_name = 'A I Model'
        verbose_name_plural = 'A I Model records'


class AIProvider(DomainModel):
    api_endpoint = models.URLField(max_length=2048, blank=True)
    api_key_reference = models.UUIDField(null=True, blank=True, db_index=True)
    priority = models.BigIntegerField(default=0)
    enabled = models.BooleanField(default=False)
    rate_limit = models.BigIntegerField(default=0)
    timeout = models.BigIntegerField(default=0)
    retry_limit = models.BigIntegerField(default=0)

    class Meta(DomainModel.Meta):
        verbose_name = 'A I Provider'
        verbose_name_plural = 'A I Provider records'


class PromptTemplate(DomainModel):
    category = models.CharField(max_length=255, blank=True, db_index=True)
    system_prompt = models.TextField(blank=True)
    template = models.TextField(blank=True)
    version = models.BigIntegerField(default=0)
    enabled = models.BooleanField(default=False)

    class Meta(DomainModel.Meta):
        verbose_name = 'Prompt Template'
        verbose_name_plural = 'Prompt Template records'


class AIRequest(DomainModel):
    conversation = models.CharField(max_length=255, blank=True, db_index=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name='ai_engine_a_i_request_user')
    provider = models.CharField(max_length=255, blank=True, db_index=False)
    model = models.CharField(max_length=255, blank=True, db_index=False)
    prompt_tokens = models.BigIntegerField(default=0)
    completion_tokens = models.BigIntegerField(default=0)
    latency = models.BigIntegerField(default=0)
    started_at = models.DateTimeField(null=True, blank=True, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'A I Request'
        verbose_name_plural = 'A I Request records'


class AIResponse(DomainModel):
    request = models.CharField(max_length=255, blank=True, db_index=False)
    content = models.TextField(blank=True)
    finish_reason = models.TextField(blank=True)
    tool_calls = models.JSONField(default=dict, blank=True)
    cost = models.DecimalField(max_digits=12, decimal_places=4, default=0)

    class Meta(DomainModel.Meta):
        verbose_name = 'A I Response'
        verbose_name_plural = 'A I Response records'


class ToolInvocation(DomainModel):
    request = models.CharField(max_length=255, blank=True, db_index=False)
    tool_name = models.CharField(max_length=255, blank=True, db_index=False)
    arguments = models.JSONField(default=dict, blank=True)
    result = models.JSONField(default=dict, blank=True)
    started_at = models.DateTimeField(null=True, blank=True, db_index=True)
    finished_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Tool Invocation'
        verbose_name_plural = 'Tool Invocation records'


class ContextSnapshot(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = 'Context Snapshot'
        verbose_name_plural = 'Context Snapshot records'

