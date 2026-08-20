from django.db.models.signals import post_migrate
from django.dispatch import Signal, receiver

record_created = Signal()
record_updated = Signal()


@receiver(post_migrate)
def bootstrap_after_migrate(sender, app_config, **kwargs):
    if app_config.label != "core":
        return
    from .bootstrap import bootstrap_platform

    bootstrap_platform()
