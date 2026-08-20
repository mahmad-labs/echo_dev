# Development Workflow

## Local setup

Follow `INSTALLATION.md`. SQLite and eager Celery are the default so a developer can run the complete core platform with standard Django commands. Configure PostgreSQL and Redis locally when validating production-specific behavior.

## Branch and change discipline

Keep each change focused. Update models, migrations, services, API behavior, tests, and documentation together. Do not edit committed migrations after they have shipped; create a new migration. Avoid business logic in templates, serializers, signals, and admin classes.

## Adding domain behavior

1. Put the model in the owning application's `models.py`.
2. Generate and review the migration.
3. Put multi-record or provider behavior in `services.py` or a focused service module.
4. Add explicit permissions.
5. Add serializers and views only for the required interface.
6. Register administrative views where operational access is appropriate.
7. Add service tests and API tests, including negative authorization cases.
8. Update the relevant documentation and endpoint catalog when compatibility paths change.

## Commands

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py validate_echo
python manage.py test
ruff check .
ruff format --check .
mypy echo config
```

Use `coverage run manage.py test` and inspect untested service branches before release. Generated migrations are excluded from style linting but remain subject to syntax and migration checks.

## Code standards

- Target Python 3.11 or newer.
- Use type hints on public service interfaces.
- Prefer explicit names over abbreviations.
- Keep transactions at application-service boundaries.
- Use select/prefetch optimizations after measuring query behavior.
- Never execute arbitrary shell commands, imports, or user-supplied Python.
- Validate external URLs and timeouts through approved provider adapters.
- Keep raw credentials out of models, logs, fixtures, tests, and source control.

## Tests

Tests must be deterministic and independent of public network services. Mock provider boundaries. Use `get_or_create` for bootstrap-owned permission records. Test owner isolation, staff behavior, validation failures, transaction rollback, retry behavior, and response envelopes.

## Schema changes

Review every migration for table locks, defaults, backfills, and reversibility. For large production tables, use expand-and-contract changes: add nullable structures, deploy compatible code, backfill in bounded batches, enforce constraints, then remove obsolete structures in a later release.

## Dependency changes

Pin direct dependencies. Review upstream release notes and security advisories. Update in a dedicated change, run the full suite under every supported Python/database combination, and retain a rollback package. Do not mix framework upgrades with unrelated feature work.
