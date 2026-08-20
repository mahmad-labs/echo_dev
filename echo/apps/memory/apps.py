from django.apps import AppConfig


class MemoryConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'echo.apps.memory'
    label = 'memory'
    verbose_name = 'Memory'

    def ready(self):
        from . import signals  # noqa: F401
