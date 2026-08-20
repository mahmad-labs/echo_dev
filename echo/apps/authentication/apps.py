from django.apps import AppConfig


class AuthenticationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'echo.apps.authentication'
    label = 'authentication'
    verbose_name = 'Authentication'

    def ready(self):
        from . import signals  # noqa: F401
