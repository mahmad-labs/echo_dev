from django.apps import AppConfig


class DashboardConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'echo.apps.dashboard'
    label = 'dashboard'
    verbose_name = 'Dashboard'

    def ready(self):
        from . import signals  # noqa: F401
