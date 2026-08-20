import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("internet", "0002_computer_use"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ComputerSession",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(blank=True, db_index=True, max_length=255)),
                ("title", models.CharField(blank=True, db_index=True, max_length=255)),
                ("description", models.TextField(blank=True)),
                ("status", models.CharField(db_index=True, default="active", max_length=64)),
                ("data", models.JSONField(blank=True, default=dict)),
                ("owner", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="%(app_label)s_%(class)s_owned", to=settings.AUTH_USER_MODEL)),
                ("environment", models.CharField(db_index=True, default="desktop.local", max_length=96)),
                ("display_name", models.CharField(blank=True, max_length=255)),
                ("started_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("ended_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("last_activity_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("active_window", models.JSONField(blank=True, default=dict)),
                ("configuration", models.JSONField(blank=True, default=dict)),
            ],
            options={"ordering": ("-created_at",), "verbose_name": "Computer Session", "verbose_name_plural": "Computer Sessions"},
        ),
        migrations.CreateModel(
            name="ComputerObservation",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(blank=True, db_index=True, max_length=255)),
                ("title", models.CharField(blank=True, db_index=True, max_length=255)),
                ("description", models.TextField(blank=True)),
                ("status", models.CharField(db_index=True, default="active", max_length=64)),
                ("data", models.JSONField(blank=True, default=dict)),
                ("owner", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="%(app_label)s_%(class)s_owned", to=settings.AUTH_USER_MODEL)),
                ("sequence", models.PositiveIntegerField(default=0)),
                ("screenshot", models.FileField(blank=True, upload_to="computer/observations/%Y/%m/%d/")),
                ("ocr_text", models.TextField(blank=True)),
                ("vision", models.JSONField(blank=True, default=dict)),
                ("ui_tree", models.JSONField(blank=True, default=dict)),
                ("window_info", models.JSONField(blank=True, default=dict)),
                ("cursor", models.JSONField(blank=True, default=dict)),
                ("viewport", models.JSONField(blank=True, default=dict)),
                ("content_hash", models.CharField(blank=True, db_index=True, max_length=64)),
                ("observed_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("configuration", models.JSONField(blank=True, default=dict)),
                ("session", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="observations", to="internet.computersession")),
            ],
            options={"ordering": ("-created_at",), "verbose_name": "Computer Observation", "verbose_name_plural": "Computer Observations"},
        ),
        migrations.CreateModel(
            name="ComputerAction",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(blank=True, db_index=True, max_length=255)),
                ("title", models.CharField(blank=True, db_index=True, max_length=255)),
                ("description", models.TextField(blank=True)),
                ("status", models.CharField(db_index=True, default="active", max_length=64)),
                ("data", models.JSONField(blank=True, default=dict)),
                ("owner", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="%(app_label)s_%(class)s_owned", to=settings.AUTH_USER_MODEL)),
                ("action_type", models.CharField(db_index=True, max_length=80)),
                ("target", models.JSONField(blank=True, default=dict)),
                ("arguments", models.JSONField(blank=True, default=dict)),
                ("result", models.JSONField(blank=True, default=dict)),
                ("verified", models.BooleanField(db_index=True, default=False)),
                ("started_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("error_message", models.TextField(blank=True)),
                ("configuration", models.JSONField(blank=True, default=dict)),
                ("post_observation", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="actions_after", to="internet.computerobservation")),
                ("pre_observation", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="actions_before", to="internet.computerobservation")),
                ("session", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="actions", to="internet.computersession")),
            ],
            options={"ordering": ("-created_at",), "verbose_name": "Computer Action", "verbose_name_plural": "Computer Actions"},
        ),
        migrations.AddIndex(model_name="computersession", index=models.Index(fields=["owner", "status", "-last_activity_at"], name="computer_session_owner_idx")),
        migrations.AddIndex(model_name="computerobservation", index=models.Index(fields=["session", "-sequence"], name="computer_observation_seq_idx")),
        migrations.AddIndex(model_name="computeraction", index=models.Index(fields=["session", "-created_at"], name="computer_action_recent_idx")),
    ]
