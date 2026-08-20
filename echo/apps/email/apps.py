from django.apps import AppConfig


class EmailConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'echo.apps.email'
    label = 'email'
    verbose_name = 'Email'

    def ready(self):
        from . import signals  # noqa: F401
