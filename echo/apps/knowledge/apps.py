from django.apps import AppConfig


class KnowledgeConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'echo.apps.knowledge'
    label = 'knowledge'
    verbose_name = 'Knowledge'

    def ready(self):
        from . import signals  # noqa: F401
