from django.apps import AppConfig


class CodeAssistantConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'echo.apps.code_assistant'
    label = 'code_assistant'
    verbose_name = 'Code Assistant'

    def ready(self):
        from . import signals  # noqa: F401
