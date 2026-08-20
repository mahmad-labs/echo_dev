# Maintenance

## Routine schedule

Daily: verify backups, readiness, error rates, provider failures, and queue health. Weekly: clear expired sessions, review failed jobs and security events, inspect storage growth, and run authenticated smoke tests. Monthly: update dependencies, review advisories, rotate non-emergency credentials according to policy, test restore samples, and inspect database performance. Quarterly: complete a full recovery exercise, authorization review, capacity review, and provider contract test.

## Dependency upgrades

Update pinned versions intentionally. Review release notes and security advisories, install in a clean virtual environment, run checks/tests/static analysis, inspect migrations, and deploy first to a representative staging environment. Do not combine framework upgrades with unrelated schema or product changes when avoidable.

## Data cleanup

Use Django's `clearsessions` for expired browser sessions. Add retention commands appropriate to the deployment for old audit, analytics, provider response, delivery, login-history, and temporary processing records. Retention must follow legal, security, and product requirements and should preserve necessary investigation evidence.

## Operational commands

- `python manage.py validate_echo` verifies module/model/catalog structure.
- `python manage.py bootstrap_echo` repairs baseline roles and registries idempotently.
- `python manage.py showmigrations` displays schema state.
- `python manage.py migrate --plan` previews migration operations.
- `python manage.py check --deploy` evaluates production security settings.
