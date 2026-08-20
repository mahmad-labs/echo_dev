from django.apps import AppConfig


class TasksConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'echo.apps.tasks'
    label = 'tasks'
    verbose_name = 'Tasks'

    def ready(self):
        from . import signals  # noqa: F401
