from django.apps import AppConfig


class AgentManagerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'echo.apps.agent_manager'
    label = 'agent_manager'
    verbose_name = 'Agent Manager'

    def ready(self):
        from . import signals  # noqa: F401
        from .registry import AgentRegistry
        AgentRegistry.ensure_loaded()
