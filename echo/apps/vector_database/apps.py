from django.apps import AppConfig


class VectorDatabaseConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'echo.apps.vector_database'
    label = 'vector_database'
    verbose_name = 'Vector Database'

    def ready(self):
        from . import signals  # noqa: F401
