# Troubleshooting

## Diagnostic order

1. Reproduce the issue and capture the timestamp, endpoint, user, and correlation ID.
2. Check `/health/` and `/ready/`.
3. Review web, worker, scheduler, Nginx, PostgreSQL, and Redis logs.
4. Run `python manage.py check` and `python manage.py validate_echo` in the deployed environment.
5. Confirm environment variables and service-account permissions without printing secrets.
6. Compare the applied migration list with the release.
7. Isolate provider failures from core application failures.

## Import or startup errors

Activate the intended virtual environment and run:

```bash
python --version
python -m pip --version
python -m pip install -r requirements.txt
python manage.py check
```

Confirm the service working directory is the repository root and `DJANGO_SETTINGS_MODULE` is not overridden incorrectly.

## Secret-key failure

Production startup intentionally fails when `DJANGO_SECRET_KEY` is missing. Add a high-entropy value to the protected environment file and restart the web and worker services. Do not use the development fallback in production.

## Database connection failure

Validate host, port, database, username, password, DNS, firewall, TLS mode, and PostgreSQL service status. Test with the PostgreSQL client using the same network path. Confirm the URL is percent-encoded when credentials contain reserved characters.

## Migration problems

```bash
python manage.py showmigrations
python manage.py makemigrations --check --dry-run
python manage.py migrate --plan
```

Do not use `--fake` unless the database schema has been independently verified to match the migration state. Restore a backup before correcting destructive inconsistencies.

## Static files missing

Run `python manage.py collectstatic --noinput`, verify `STATIC_ROOT`, check Nginx alias permissions, and restart or reload the proxy. Manifest errors usually indicate a referenced static asset was not collected or does not exist.

## Authentication failures

For JWTs, verify the `Bearer` scheme, access-token expiry, refresh rotation, and blacklist state. For API tokens, verify `Token` or `X-API-Key`, token expiry, revocation, and the owning user's active state. Raw API tokens cannot be recovered; issue a replacement and revoke the old record.

## Forbidden or empty results

Nonstaff queries are ownership-scoped. A `404` may intentionally conceal a resource owned by another user. Check the resource owner, user roles, required permission codename, and whether the caller is using the expected account.

## Celery jobs do not run

When eager mode is enabled, the request process runs the task. Otherwise confirm `REDIS_URL`, worker service status, queue routing, beat status for scheduled work, and worker logs. Restarting a worker does not repair non-idempotent task design; inspect the durable operation record before retrying.

## External provider errors

Confirm the provider base URL, model name, API key, timeout, TLS trust, and account quota. The application rejects unsafe URL targets. Use a reachable public HTTPS endpoint and never bypass private-network checks for user-controlled URLs.

## Slow requests

Use correlation IDs to inspect timing, query count, external calls, and background-job boundaries. Add database indexes only after confirming query plans. Move long provider operations to Celery and use pagination for large collections.

## Test failures after bootstrap

System roles and permissions are created automatically after migration. Tests that need those records should retrieve them with `get_or_create` rather than assuming an empty table.
