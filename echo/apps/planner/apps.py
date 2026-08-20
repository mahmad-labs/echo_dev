from django.apps import AppConfig


class PlannerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'echo.apps.planner'
    label = 'planner'
    verbose_name = 'Planner'

    def ready(self):
        from . import signals  # noqa: F401
