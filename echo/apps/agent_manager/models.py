from __future__ import annotations

import uuid

from django.db import models
from echo.common.models import DomainModel


class Agent(DomainModel):
    """Owner-scoped materialization of a registered Echo agent."""

    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)
    identifier = models.CharField(max_length=96, blank=True, db_index=True)
    version = models.CharField(max_length=32, default="1")
    capabilities = models.JSONField(default=list, blank=True)
    required_tools = models.JSONField(default=list, blank=True)
    required_permissions = models.JSONField(default=list, blank=True)
    input_schema = models.JSONField(default=dict, blank=True)
    output_schema = models.JSONField(default=dict, blank=True)
    available = models.BooleanField(default=True, db_index=True)
    health_status = models.CharField(max_length=32, default="healthy", db_index=True)
    last_health_check = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta(DomainModel.Meta):
        verbose_name = "Agent"
        verbose_name_plural = "Agent records"
        constraints = [
            models.UniqueConstraint(fields=("owner", "identifier"), condition=~models.Q(identifier=""), name="agent_owner_identifier_unique"),
        ]
        indexes = [models.Index(fields=("owner", "available", "identifier"), name="agent_owner_available_idx")]


class AgentCapability(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = "Agent Capability"
        verbose_name_plural = "Agent Capability records"


class AgentTask(DomainModel):
    """Durable unit of orchestrated work, including parent/child execution state."""

    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)
    agent = models.ForeignKey(Agent, on_delete=models.SET_NULL, null=True, blank=True, related_name="tasks")
    parent_task = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="child_tasks")
    conversation = models.ForeignKey("chat.Conversation", on_delete=models.SET_NULL, null=True, blank=True, related_name="agent_tasks")
    project = models.ForeignKey("projects.Project", on_delete=models.SET_NULL, null=True, blank=True, related_name="agent_tasks")
    request_text = models.TextField(blank=True)
    priority = models.CharField(max_length=24, default="normal", db_index=True)
    input_payload = models.JSONField(default=dict, blank=True)
    output_payload = models.JSONField(default=dict, blank=True)
    current_operation = models.CharField(max_length=255, blank=True)
    current_tool = models.CharField(max_length=120, blank=True)
    progress = models.PositiveSmallIntegerField(default=0)
    started_at = models.DateTimeField(null=True, blank=True, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True, db_index=True)
    cancellable = models.BooleanField(default=True)
    cancel_requested = models.BooleanField(default=False, db_index=True)
    error_message = models.TextField(blank=True)
    correlation_id = models.UUIDField(default=uuid.uuid4, db_index=True)

    class Meta(DomainModel.Meta):
        verbose_name = "Agent Task"
        verbose_name_plural = "Agent Task records"
        indexes = [
            models.Index(fields=("owner", "status", "-updated_at"), name="agent_task_owner_state_idx"),
            models.Index(fields=("parent_task", "created_at"), name="agent_task_parent_idx"),
        ]


class AgentCommunication(DomainModel):
    """Structured agent-to-agent message; never relies on parsing prose for handoff state."""

    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)
    task = models.ForeignKey(AgentTask, on_delete=models.CASCADE, null=True, blank=True, related_name="communications")
    sender_agent = models.ForeignKey(Agent, on_delete=models.SET_NULL, null=True, blank=True, related_name="sent_messages")
    recipient_agent = models.ForeignKey(Agent, on_delete=models.SET_NULL, null=True, blank=True, related_name="received_messages")
    message_type = models.CharField(max_length=64, default="handoff", db_index=True)
    correlation_id = models.UUIDField(default=uuid.uuid4, db_index=True)
    payload = models.JSONField(default=dict, blank=True)
    processed_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta(DomainModel.Meta):
        verbose_name = "Agent Communication"
        verbose_name_plural = "Agent Communication records"
        indexes = [models.Index(fields=("owner", "correlation_id", "created_at"), name="agent_comm_corr_idx")]


class AgentGroup(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = "Agent Group"
        verbose_name_plural = "Agent Group records"


class AgentMembership(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = "Agent Membership"
        verbose_name_plural = "Agent Membership records"


class AgentPerformance(DomainModel):
    category = models.CharField(max_length=100, blank=True, db_index=True)
    configuration = models.JSONField(default=dict, blank=True)

    class Meta(DomainModel.Meta):
        verbose_name = "Agent Performance"
        verbose_name_plural = "Agent Performance records"
