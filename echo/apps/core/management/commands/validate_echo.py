from __future__ import annotations

from pathlib import Path

from django.apps import apps
from django.core.checks import run_checks
from django.core.management.base import BaseCommand, CommandError

from echo.spec_catalog import SPEC_ENDPOINTS


EXPECTED_APP_COUNT = 24
EXPECTED_MODEL_COUNT = 189
EXPECTED_ENDPOINT_COUNT = 238
REQUIRED_APP_FILES = {
    "admin.py",
    "apps.py",
    "models.py",
    "permissions.py",
    "serializers.py",
    "services.py",
    "signals.py",
    "tasks.py",
    "tests.py",
    "urls.py",
    "views.py",
}


class Command(BaseCommand):
    help = "Run structural and Django-system validation for the Echo platform."

    def handle(self, *args, **options):
        failures = [str(error) for error in run_checks()]
        echo_apps = [
            app_config
            for app_config in apps.get_app_configs()
            if app_config.name.startswith("echo.apps.")
        ]
        model_count = sum(len(list(app_config.get_models())) for app_config in echo_apps)
        endpoint_pairs = {
            (item["method"].upper(), item["path"])
            for item in SPEC_ENDPOINTS
        }

        if len(echo_apps) != EXPECTED_APP_COUNT:
            failures.append(
                f"Expected {EXPECTED_APP_COUNT} Echo apps, found {len(echo_apps)}."
            )
        if model_count != EXPECTED_MODEL_COUNT:
            failures.append(
                f"Expected {EXPECTED_MODEL_COUNT} concrete models, found {model_count}."
            )
        if len(SPEC_ENDPOINTS) != EXPECTED_ENDPOINT_COUNT:
            failures.append(
                f"Expected {EXPECTED_ENDPOINT_COUNT} catalog entries, found "
                f"{len(SPEC_ENDPOINTS)}."
            )
        if len(endpoint_pairs) != EXPECTED_ENDPOINT_COUNT:
            failures.append("The specification endpoint catalog contains duplicate method/path pairs.")

        for app_config in echo_apps:
            app_path = Path(app_config.path)
            missing = sorted(
                filename for filename in REQUIRED_APP_FILES if not (app_path / filename).is_file()
            )
            migration = app_path / "migrations" / "0001_initial.py"
            if missing:
                failures.append(
                    f"{app_config.label} is missing required modules: {', '.join(missing)}."
                )
            if not migration.is_file():
                failures.append(f"{app_config.label} is missing migrations/0001_initial.py.")

        if failures:
            raise CommandError("\n".join(failures))

        self.stdout.write(
            self.style.SUCCESS(
                "Validated "
                f"{len(echo_apps)} apps, {model_count} models, and "
                f"{len(endpoint_pairs)} specification endpoints."
            )
        )
