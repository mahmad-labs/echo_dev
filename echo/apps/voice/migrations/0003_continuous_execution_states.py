from django.db import migrations, models


def enable_continuous_listening(apps, schema_editor):
    VoiceProfile = apps.get_model('voice', 'VoiceProfile')
    VoiceProfile.objects.filter(is_default=True).update(continuous_listening=True)


class Migration(migrations.Migration):
    dependencies = [('voice', '0002_voice_runtime')]
    operations = [
        migrations.AlterField(
            model_name='voiceprofile',
            name='continuous_listening',
            field=models.BooleanField(default=True),
        ),
        migrations.AlterField(
            model_name='voicesession',
            name='state',
            field=models.CharField(
                choices=[('idle','Idle'),('listening','Listening'),('processing','Processing'),('thinking','Thinking'),('executing','Executing'),('speaking','Speaking'),('paused','Paused'),('error','Error'),('waiting','Waiting for user'),('stopped','Stopped'),('ended','Ended')],
                db_index=True,
                default='idle',
                max_length=32,
            ),
        ),
        migrations.RunPython(enable_continuous_listening, migrations.RunPython.noop),
    ]
