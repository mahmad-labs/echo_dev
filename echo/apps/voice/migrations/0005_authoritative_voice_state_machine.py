from django.db import migrations, models


def migrate_voice_states(apps, schema_editor):
    VoiceSession = apps.get_model("voice", "VoiceSession")
    active_like = {"listening", "processing", "thinking", "executing", "speaking", "waiting"}
    for session in VoiceSession.objects.all().iterator():
        previous = session.state
        if previous == "error":
            state = "error"
        elif previous == "ended":
            state = "shutdown"
        elif previous == "speaking":
            state = "speaking"
        elif previous in active_like:
            state = "active_session" if session.mode == "active" else "wake_word_listening"
        elif previous in {"paused", "stopped"}:
            state = "wake_word_listening"
        else:
            state = "starting"
        session.state = state
        session.save(update_fields=["state"])


class Migration(migrations.Migration):
    dependencies = [("voice", "0004_wake_session_speaker_awareness")]

    operations = [
        migrations.AddField(model_name="voicesession", name="greeted_at", field=models.DateTimeField(blank=True, db_index=True, null=True)),
        migrations.AddField(model_name="voicesession", name="shutdown_at", field=models.DateTimeField(blank=True, db_index=True, null=True)),
        migrations.AlterField(
            model_name="voicesession",
            name="state",
            field=models.CharField(
                choices=[
                    ("starting", "Starting"), ("greeting", "Greeting"), ("disabled", "Disabled"),
                    ("wake_word_listening", "Wake-word listening"), ("active_session", "Active session"),
                    ("processing", "Processing"), ("speaking", "Speaking"), ("sleeping", "Sleeping"),
                    ("shutdown", "Shutdown"), ("error", "Error"),
                ],
                db_index=True, default="starting", max_length=32,
            ),
        ),
        migrations.RunPython(migrate_voice_states, migrations.RunPython.noop),
    ]
