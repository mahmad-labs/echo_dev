from django.apps import AppConfig


class ToolManagerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'echo.apps.tool_manager'
    label = 'tool_manager'
    verbose_name = 'Tool Manager'

    def ready(self):
        from . import signals  # noqa: F401
        from .registry import ToolRegistry
        ToolRegistry.bootstrap()
