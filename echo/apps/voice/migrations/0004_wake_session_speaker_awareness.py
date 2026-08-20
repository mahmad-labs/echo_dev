from django.db import migrations, models
from django.conf import settings
import uuid
import django.core.validators
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("voice", "0003_continuous_execution_states")]

    operations = [
        migrations.AddField(model_name="voiceprofile", name="speaker_identification_enabled", field=models.BooleanField(default=False)),
        migrations.AddField(model_name="voiceprofile", name="reject_unrecognized_speakers", field=models.BooleanField(default=True)),
        migrations.AddField(model_name="voiceprofile", name="voice_history_enabled", field=models.BooleanField(default=True)),
        migrations.AddField(model_name="voiceprofile", name="transcript_retention_days", field=models.PositiveSmallIntegerField(default=30, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(365)])),
        migrations.AddField(model_name="voiceprofile", name="active_session_minutes", field=models.PositiveSmallIntegerField(default=60, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(60)])),
        migrations.AddField(model_name="voicesession", name="mode", field=models.CharField(choices=[("wake_word", "Wake-word mode"), ("active", "Active voice session")], db_index=True, default="wake_word", max_length=24)),
        migrations.AddField(model_name="voicesession", name="active_started_at", field=models.DateTimeField(blank=True, db_index=True, null=True)),
        migrations.AddField(model_name="voicesession", name="active_expires_at", field=models.DateTimeField(blank=True, db_index=True, null=True)),
        migrations.AddField(model_name="voicesession", name="wake_word", field=models.CharField(default="Echo", max_length=80)),
        migrations.AddField(model_name="voicesession", name="speaker_state", field=models.CharField(db_index=True, default="not_enrolled", max_length=32)),
        migrations.AlterField(model_name="wakewordconfiguration", name="enabled", field=models.BooleanField(default=True)),
        migrations.CreateModel(
            name="SpeakerProfile",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(blank=True, db_index=True, max_length=255)),
                ("title", models.CharField(blank=True, db_index=True, max_length=255)),
                ("description", models.TextField(blank=True)),
                ("status", models.CharField(db_index=True, default="active", max_length=64)),
                ("data", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("category", models.CharField(blank=True, db_index=True, default="speaker", max_length=100)),
                ("configuration", models.JSONField(blank=True, default=dict)),
                ("enabled", models.BooleanField(db_index=True, default=True)),
                ("enrolled", models.BooleanField(db_index=True, default=False)),
                ("embedding", models.JSONField(blank=True, default=list)),
                ("sample_count", models.PositiveSmallIntegerField(default=0)),
                ("threshold", models.DecimalField(decimal_places=3, default=0.82, max_digits=4, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(1)])),
                ("enrolled_at", models.DateTimeField(blank=True, null=True)),
                ("last_verified_at", models.DateTimeField(blank=True, null=True)),
                ("owner", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="%(app_label)s_%(class)s_owned", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-created_at",), "abstract": False},
        ),
        migrations.CreateModel(
            name="SpeakerEnrollmentSample",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(blank=True, db_index=True, max_length=255)),
                ("title", models.CharField(blank=True, db_index=True, max_length=255)),
                ("description", models.TextField(blank=True)),
                ("status", models.CharField(db_index=True, default="active", max_length=64)),
                ("data", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("category", models.CharField(blank=True, db_index=True, default="speaker_sample", max_length=100)),
                ("configuration", models.JSONField(blank=True, default=dict)),
                ("embedding", models.JSONField(blank=True, default=list)),
                ("quality_score", models.DecimalField(decimal_places=4, default=0, max_digits=5, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(1)])),
                ("duration_ms", models.PositiveIntegerField(default=0)),
                ("owner", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="%(app_label)s_%(class)s_owned", to=settings.AUTH_USER_MODEL)),
                ("profile", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="samples", to="voice.speakerprofile")),
            ],
            options={"ordering": ("-created_at",), "abstract": False},
        ),
        migrations.CreateModel(
            name="SpeakerVerificationEvent",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("name", models.CharField(blank=True, db_index=True, max_length=255)),
                ("title", models.CharField(blank=True, db_index=True, max_length=255)),
                ("description", models.TextField(blank=True)),
                ("status", models.CharField(db_index=True, default="active", max_length=64)),
                ("data", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("category", models.CharField(blank=True, db_index=True, default="speaker_verification", max_length=100)),
                ("configuration", models.JSONField(blank=True, default=dict)),
                ("decision", models.CharField(db_index=True, default="unknown", max_length=24)),
                ("score", models.DecimalField(decimal_places=4, default=0, max_digits=5, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(1)])),
                ("threshold", models.DecimalField(decimal_places=4, default=0.82, max_digits=5, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(1)])),
                ("owner", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="%(app_label)s_%(class)s_owned", to=settings.AUTH_USER_MODEL)),
                ("profile", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="verification_events", to="voice.speakerprofile")),
                ("session", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="speaker_events", to="voice.voicesession")),
                ("transcript", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="speaker_events", to="voice.speechtranscript")),
            ],
            options={"ordering": ("-created_at",), "abstract": False},
        ),
        migrations.AddConstraint(model_name="speakerprofile", constraint=models.UniqueConstraint(fields=("owner",), name="voice_one_speaker_profile_per_owner")),
        migrations.AddIndex(model_name="speakerverificationevent", index=models.Index(fields=["owner", "-created_at"], name="voice_speaker_verify_time")),
    ]
