from django.apps import AppConfig


class AnalyticsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'echo.apps.analytics'
    label = 'analytics'
    verbose_name = 'Analytics'

    def ready(self):
        from . import signals  # noqa: F401
