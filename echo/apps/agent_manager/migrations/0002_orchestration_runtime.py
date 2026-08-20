import uuid
import django.db.models.deletion
from django.db import migrations, models


def populate_agent_identifiers(apps, schema_editor):
    Agent = apps.get_model("agent_manager", "Agent")
    for agent in Agent.objects.filter(identifier="").iterator():
        agent.identifier = f"legacy-{agent.pk}"[:96]
        agent.save(update_fields=["identifier"])


def noop_reverse(apps, schema_editor):
    return None


class Migration(migrations.Migration):
    dependencies = [
        ("agent_manager", "0001_initial"),
        ("chat", "0001_initial"),
        ("projects", "0001_initial"),
    ]

    operations = [
        migrations.AddField(model_name="agent", name="identifier", field=models.CharField(blank=True, db_index=True, max_length=96)),
        migrations.AddField(model_name="agent", name="version", field=models.CharField(default="1", max_length=32)),
        migrations.AddField(model_name="agent", name="capabilities", field=models.JSONField(blank=True, default=list)),
        migrations.AddField(model_name="agent", name="required_tools", field=models.JSONField(blank=True, default=list)),
        migrations.AddField(model_name="agent", name="required_permissions", field=models.JSONField(blank=True, default=list)),
        migrations.AddField(model_name="agent", name="input_schema", field=models.JSONField(blank=True, default=dict)),
        migrations.AddField(model_name="agent", name="output_schema", field=models.JSONField(blank=True, default=dict)),
        migrations.AddField(model_name="agent", name="available", field=models.BooleanField(db_index=True, default=True)),
        migrations.AddField(model_name="agent", name="health_status", field=models.CharField(db_index=True, default="healthy", max_length=32)),
        migrations.AddField(model_name="agent", name="last_health_check", field=models.DateTimeField(blank=True, db_index=True, null=True)),
        migrations.AddField(model_name="agenttask", name="agent", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="tasks", to="agent_manager.agent")),
        migrations.AddField(model_name="agenttask", name="parent_task", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="child_tasks", to="agent_manager.agenttask")),
        migrations.AddField(model_name="agenttask", name="conversation", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="agent_tasks", to="chat.conversation")),
        migrations.AddField(model_name="agenttask", name="project", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="agent_tasks", to="projects.project")),
        migrations.AddField(model_name="agenttask", name="request_text", field=models.TextField(blank=True)),
        migrations.AddField(model_name="agenttask", name="priority", field=models.CharField(db_index=True, default="normal", max_length=24)),
        migrations.AddField(model_name="agenttask", name="input_payload", field=models.JSONField(blank=True, default=dict)),
        migrations.AddField(model_name="agenttask", name="output_payload", field=models.JSONField(blank=True, default=dict)),
        migrations.AddField(model_name="agenttask", name="current_operation", field=models.CharField(blank=True, max_length=255)),
        migrations.AddField(model_name="agenttask", name="current_tool", field=models.CharField(blank=True, max_length=120)),
        migrations.AddField(model_name="agenttask", name="progress", field=models.PositiveSmallIntegerField(default=0)),
        migrations.AddField(model_name="agenttask", name="started_at", field=models.DateTimeField(blank=True, db_index=True, null=True)),
        migrations.AddField(model_name="agenttask", name="completed_at", field=models.DateTimeField(blank=True, db_index=True, null=True)),
        migrations.AddField(model_name="agenttask", name="cancellable", field=models.BooleanField(default=True)),
        migrations.AddField(model_name="agenttask", name="cancel_requested", field=models.BooleanField(db_index=True, default=False)),
        migrations.AddField(model_name="agenttask", name="error_message", field=models.TextField(blank=True)),
        migrations.AddField(model_name="agenttask", name="correlation_id", field=models.UUIDField(db_index=True, default=uuid.uuid4)),
        migrations.AddField(model_name="agentcommunication", name="task", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="communications", to="agent_manager.agenttask")),
        migrations.AddField(model_name="agentcommunication", name="sender_agent", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="sent_messages", to="agent_manager.agent")),
        migrations.AddField(model_name="agentcommunication", name="recipient_agent", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="received_messages", to="agent_manager.agent")),
        migrations.AddField(model_name="agentcommunication", name="message_type", field=models.CharField(db_index=True, default="handoff", max_length=64)),
        migrations.AddField(model_name="agentcommunication", name="correlation_id", field=models.UUIDField(db_index=True, default=uuid.uuid4)),
        migrations.AddField(model_name="agentcommunication", name="payload", field=models.JSONField(blank=True, default=dict)),
        migrations.AddField(model_name="agentcommunication", name="processed_at", field=models.DateTimeField(blank=True, db_index=True, null=True)),
        migrations.RunPython(populate_agent_identifiers, noop_reverse),
        migrations.AddConstraint(model_name="agent", constraint=models.UniqueConstraint(condition=~models.Q(identifier=""), fields=("owner", "identifier"), name="agent_owner_identifier_unique")),
        migrations.AddIndex(model_name="agent", index=models.Index(fields=["owner", "available", "identifier"], name="agent_owner_available_idx")),
        migrations.AddIndex(model_name="agenttask", index=models.Index(fields=["owner", "status", "-updated_at"], name="agent_task_owner_state_idx")),
        migrations.AddIndex(model_name="agenttask", index=models.Index(fields=["parent_task", "created_at"], name="agent_task_parent_idx")),
        migrations.AddIndex(model_name="agentcommunication", index=models.Index(fields=["owner", "correlation_id", "created_at"], name="agent_comm_corr_idx")),
    ]
