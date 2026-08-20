import uuid
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models
import django.db.models.deletion


def normalize_voice_profile_defaults(apps, schema_editor):
    VoiceProfile = apps.get_model("voice", "VoiceProfile")
    owner_ids = VoiceProfile.objects.exclude(owner_id=None).values_list("owner_id", flat=True).distinct()
    for owner_id in owner_ids.iterator():
        profiles = VoiceProfile.objects.filter(owner_id=owner_id).order_by("created_at", "id")
        keep_id = profiles.values_list("id", flat=True).first()
        profiles.exclude(id=keep_id).update(is_default=False)
        profiles.filter(id=keep_id).update(is_default=True)


def noop_reverse(apps, schema_editor):
    return None



class Migration(migrations.Migration):
    dependencies = [
        ("chat", "0001_initial"),
        ("voice", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="voiceprofile",
            name="language",
            field=models.CharField(default="en-US", max_length=32),
        ),
        migrations.AddField(
            model_name="voiceprofile",
            name="speech_to_text_provider",
            field=models.CharField(default="browser", max_length=64),
        ),
        migrations.AddField(
            model_name="voiceprofile",
            name="text_to_speech_provider",
            field=models.CharField(default="browser", max_length=64),
        ),
        migrations.AddField(model_name="voiceprofile", name="voice_name", field=models.CharField(blank=True, max_length=160)),
        migrations.AddField(
            model_name="voiceprofile",
            name="speaking_rate",
            field=models.DecimalField(decimal_places=2, default=1, max_digits=4, validators=[MinValueValidator(0.5), MaxValueValidator(2)]),
        ),
        migrations.AddField(
            model_name="voiceprofile",
            name="pitch",
            field=models.DecimalField(decimal_places=2, default=1, max_digits=4, validators=[MinValueValidator(0), MaxValueValidator(2)]),
        ),
        migrations.AddField(
            model_name="voiceprofile",
            name="volume",
            field=models.DecimalField(decimal_places=2, default=1, max_digits=4, validators=[MinValueValidator(0), MaxValueValidator(1)]),
        ),
        migrations.AddField(model_name="voiceprofile", name="auto_speak", field=models.BooleanField(default=True)),
        migrations.AddField(model_name="voiceprofile", name="continuous_listening", field=models.BooleanField(default=False)),
        migrations.AddField(model_name="voiceprofile", name="barge_in_enabled", field=models.BooleanField(default=True)),
        migrations.AddField(model_name="voiceprofile", name="save_audio", field=models.BooleanField(default=False)),
        migrations.AddField(model_name="voiceprofile", name="memory_requires_approval", field=models.BooleanField(default=True)),
        migrations.AddField(model_name="voiceprofile", name="is_default", field=models.BooleanField(db_index=True, default=True)),
        migrations.AlterField(model_name="voiceprofile", name="category", field=models.CharField(blank=True, db_index=True, default="default", max_length=100)),
        migrations.RunPython(normalize_voice_profile_defaults, noop_reverse),
        migrations.AddConstraint(
            model_name="voiceprofile",
            constraint=models.UniqueConstraint(condition=models.Q(is_default=True), fields=("owner",), name="voice_one_default_profile_per_owner"),
        ),
        migrations.AddField(
            model_name="voicesession",
            name="conversation",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="voice_sessions", to="chat.conversation"),
        ),
        migrations.AddField(
            model_name="voicesession",
            name="profile",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="sessions", to="voice.voiceprofile"),
        ),
        migrations.AddField(
            model_name="voicesession",
            name="state",
            field=models.CharField(choices=[("idle", "Idle"), ("listening", "Listening"), ("processing", "Processing"), ("thinking", "Thinking"), ("speaking", "Speaking"), ("paused", "Paused"), ("error", "Error"), ("waiting", "Waiting for user"), ("ended", "Ended")], db_index=True, default="idle", max_length=32),
        ),
        migrations.AddField(model_name="voicesession", name="client_session_id", field=models.CharField(blank=True, db_index=True, max_length=120)),
        migrations.AddField(model_name="voicesession", name="input_mode", field=models.CharField(default="voice", max_length=32)),
        migrations.AddField(model_name="voicesession", name="language", field=models.CharField(default="en-US", max_length=32)),
        migrations.AddField(model_name="voicesession", name="stt_provider", field=models.CharField(default="browser", max_length=64)),
        migrations.AddField(model_name="voicesession", name="tts_provider", field=models.CharField(default="browser", max_length=64)),
        migrations.AddField(model_name="voicesession", name="started_at", field=models.DateTimeField(blank=True, db_index=True, null=True)),
        migrations.AddField(model_name="voicesession", name="ended_at", field=models.DateTimeField(blank=True, db_index=True, null=True)),
        migrations.AddField(model_name="voicesession", name="last_activity_at", field=models.DateTimeField(blank=True, db_index=True, null=True)),
        migrations.AddField(model_name="voicesession", name="turn_count", field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name="voicesession", name="last_error_code", field=models.CharField(blank=True, max_length=80)),
        migrations.AddField(model_name="voicesession", name="last_error_message", field=models.TextField(blank=True)),
        migrations.AlterField(model_name="voicesession", name="category", field=models.CharField(blank=True, db_index=True, default="conversation", max_length=100)),
        migrations.AddIndex(model_name="voicesession", index=models.Index(fields=["owner", "state", "-last_activity_at"], name="voice_session_owner_state")),
        migrations.AddField(
            model_name="audioasset",
            name="session",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="audio_assets", to="voice.voicesession"),
        ),
        migrations.AddField(model_name="audioasset", name="file", field=models.FileField(blank=True, upload_to="voice/%Y/%m/%d/")),
        migrations.AddField(model_name="audioasset", name="direction", field=models.CharField(choices=[("input", "Input"), ("output", "Output")], default="input", max_length=16)),
        migrations.AddField(model_name="audioasset", name="provider", field=models.CharField(blank=True, max_length=64)),
        migrations.AddField(model_name="audioasset", name="mime_type", field=models.CharField(blank=True, max_length=120)),
        migrations.AddField(model_name="audioasset", name="format_name", field=models.CharField(blank=True, max_length=24)),
        migrations.AddField(model_name="audioasset", name="byte_size", field=models.PositiveBigIntegerField(default=0)),
        migrations.AddField(model_name="audioasset", name="duration_ms", field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name="audioasset", name="checksum", field=models.CharField(blank=True, db_index=True, max_length=64)),
        migrations.AddField(model_name="audioasset", name="expires_at", field=models.DateTimeField(blank=True, db_index=True, null=True)),
        migrations.AlterField(model_name="audioasset", name="category", field=models.CharField(blank=True, db_index=True, default="speech", max_length=100)),
        migrations.AddField(
            model_name="speechtranscript",
            name="session",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="transcripts", to="voice.voicesession"),
        ),
        migrations.AddField(
            model_name="speechtranscript",
            name="conversation",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="voice_transcripts", to="chat.conversation"),
        ),
        migrations.AddField(
            model_name="speechtranscript",
            name="message",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="voice_transcripts", to="chat.message"),
        ),
        migrations.AddField(
            model_name="speechtranscript",
            name="audio_asset",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="transcripts", to="voice.audioasset"),
        ),
        migrations.AddField(model_name="speechtranscript", name="sequence", field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name="speechtranscript", name="text", field=models.TextField(default=""), preserve_default=False),
        migrations.AddField(model_name="speechtranscript", name="language", field=models.CharField(default="en-US", max_length=32)),
        migrations.AddField(model_name="speechtranscript", name="provider", field=models.CharField(default="browser", max_length=64)),
        migrations.AddField(model_name="speechtranscript", name="confidence", field=models.DecimalField(decimal_places=4, default=0, max_digits=5, validators=[MinValueValidator(0), MaxValueValidator(1)])),
        migrations.AddField(model_name="speechtranscript", name="is_final", field=models.BooleanField(default=True)),
        migrations.AddField(model_name="speechtranscript", name="intent", field=models.CharField(blank=True, db_index=True, max_length=80)),
        migrations.AddField(model_name="speechtranscript", name="command_route", field=models.CharField(blank=True, db_index=True, max_length=80)),
        migrations.AddField(model_name="speechtranscript", name="command_result", field=models.JSONField(blank=True, default=dict)),
        migrations.AddField(model_name="speechtranscript", name="memory_status", field=models.CharField(choices=[("not_candidate", "Not a candidate"), ("pending", "Pending approval"), ("approved", "Approved"), ("rejected", "Rejected")], db_index=True, default="not_candidate", max_length=24)),
        migrations.AddField(model_name="speechtranscript", name="started_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="speechtranscript", name="completed_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AlterField(model_name="speechtranscript", name="category", field=models.CharField(blank=True, db_index=True, default="utterance", max_length=100)),
        migrations.AddIndex(model_name="speechtranscript", index=models.Index(fields=["owner", "-created_at"], name="voice_transcript_owner_time")),
        migrations.AddField(
            model_name="speechsynthesis",
            name="session",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="syntheses", to="voice.voicesession"),
        ),
        migrations.AddField(
            model_name="speechsynthesis",
            name="message",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="voice_syntheses", to="chat.message"),
        ),
        migrations.AddField(
            model_name="speechsynthesis",
            name="audio_asset",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="syntheses", to="voice.audioasset"),
        ),
        migrations.AddField(model_name="speechsynthesis", name="text", field=models.TextField(default=""), preserve_default=False),
        migrations.AddField(model_name="speechsynthesis", name="provider", field=models.CharField(default="browser", max_length=64)),
        migrations.AddField(model_name="speechsynthesis", name="voice_name", field=models.CharField(blank=True, max_length=160)),
        migrations.AddField(model_name="speechsynthesis", name="language", field=models.CharField(default="en-US", max_length=32)),
        migrations.AddField(model_name="speechsynthesis", name="format_name", field=models.CharField(default="mp3", max_length=24)),
        migrations.AddField(model_name="speechsynthesis", name="duration_ms", field=models.PositiveIntegerField(default=0)),
        migrations.AddField(model_name="speechsynthesis", name="started_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="speechsynthesis", name="completed_at", field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name="speechsynthesis", name="error_message", field=models.TextField(blank=True)),
        migrations.AlterField(model_name="speechsynthesis", name="category", field=models.CharField(blank=True, db_index=True, default="response", max_length=100)),
        migrations.AddField(model_name="wakewordconfiguration", name="phrase", field=models.CharField(default="Echo", max_length=80)),
        migrations.AddField(model_name="wakewordconfiguration", name="enabled", field=models.BooleanField(default=False)),
        migrations.AddField(model_name="wakewordconfiguration", name="sensitivity", field=models.DecimalField(decimal_places=2, default=0.7, max_digits=4, validators=[MinValueValidator(0), MaxValueValidator(1)])),
        migrations.AddField(model_name="wakewordconfiguration", name="require_foreground", field=models.BooleanField(default=True)),
        migrations.AlterField(model_name="wakewordconfiguration", name="category", field=models.CharField(blank=True, db_index=True, default="wake_word", max_length=100)),
        migrations.CreateModel(
            name="VoiceEvent",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("name", models.CharField(blank=True, db_index=True, max_length=255)),
                ("title", models.CharField(blank=True, db_index=True, max_length=255)),
                ("description", models.TextField(blank=True)),
                ("status", models.CharField(db_index=True, default="active", max_length=64)),
                ("data", models.JSONField(blank=True, default=dict)),
                ("event_type", models.CharField(db_index=True, max_length=64)),
                ("from_state", models.CharField(blank=True, max_length=32)),
                ("to_state", models.CharField(blank=True, max_length=32)),
                ("detail", models.TextField(blank=True)),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("owner", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="%(app_label)s_%(class)s_owned", to="authentication.user")),
                ("session", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="events", to="voice.voicesession")),
            ],
            options={"verbose_name": "Voice Event", "verbose_name_plural": "Voice Events", "ordering": ("-created_at",)},
        ),
        migrations.AddIndex(model_name="voiceevent", index=models.Index(fields=["session", "created_at"], name="voice_event_session_time")),
    ]
