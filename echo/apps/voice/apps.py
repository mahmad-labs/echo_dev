from django.apps import AppConfig


class VoiceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'echo.apps.voice'
    label = 'voice'
    verbose_name = 'Voice'

    def ready(self):
        from . import signals  # noqa: F401
