from django.core.management.base import BaseCommand

from echo.apps.core.bootstrap import bootstrap_platform


class Command(BaseCommand):
    help = "Create or repair system roles, permissions, configuration, flags, and app registry records."

    def handle(self, *args, **options):
        result = bootstrap_platform()
        self.stdout.write(self.style.SUCCESS(f"Echo platform baseline is ready: {result}"))
