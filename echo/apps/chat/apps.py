from django.apps import AppConfig


class ChatConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'echo.apps.chat'
    label = 'chat'
    verbose_name = 'Chat'

    def ready(self):
        from . import signals  # noqa: F401
