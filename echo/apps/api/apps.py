from django.apps import AppConfig


class ApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'echo.apps.api'
    label = 'api'
    verbose_name = 'Api'

    def ready(self):
        from . import signals  # noqa: F401
