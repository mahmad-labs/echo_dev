from django.apps import AppConfig


class AiEngineConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'echo.apps.ai_engine'
    label = 'ai_engine'
    verbose_name = 'Ai Engine'

    def ready(self):
        from . import signals  # noqa: F401
