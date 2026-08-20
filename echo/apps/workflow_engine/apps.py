from django.apps import AppConfig


class WorkflowEngineConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'echo.apps.workflow_engine'
    label = 'workflow_engine'
    verbose_name = 'Workflow Engine'

    def ready(self):
        from . import signals  # noqa: F401
