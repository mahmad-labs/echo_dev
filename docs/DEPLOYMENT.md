# Deployment Without Containers

## Reference topology

Use a conventional Linux host or virtual machine with Nginx, Gunicorn, PostgreSQL, and optionally Redis plus Celery. Run each process under a dedicated unprivileged `echo` account. Example Nginx, systemd, and logrotate files are provided under `deploy/`.

## Host preparation

Install Python 3.11 or newer, Python development headers, PostgreSQL client libraries, PostgreSQL, Nginx, and optional Redis. Create `/opt/echo`, `/etc/echo`, `/var/lib/echo`, and `/var/log/echo` with ownership limited to the service account.

## Release installation

```bash
python3 -m venv /opt/echo/venv
/opt/echo/venv/bin/pip install --upgrade pip
/opt/echo/venv/bin/pip install -r /opt/echo/current/requirements.txt
/opt/echo/venv/bin/python /opt/echo/current/manage.py migrate --noinput
/opt/echo/venv/bin/python /opt/echo/current/manage.py collectstatic --noinput
/opt/echo/venv/bin/python /opt/echo/current/manage.py validate_echo
/opt/echo/venv/bin/python /opt/echo/current/manage.py check --deploy
```

Run database migrations once per release before starting the new web workers. Keep the previous release directory until health and smoke checks pass.

## Production environment

Store variables in `/etc/echo/echo.env`, readable only by the service account. At minimum configure:

```env
DJANGO_ENV=production
DJANGO_DEBUG=false
DJANGO_SECRET_KEY=<high-entropy-secret>
DJANGO_ALLOWED_HOSTS=echo.example.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://echo.example.com
DATABASE_URL=postgresql://echo_app:<password>@127.0.0.1:5432/echo?sslmode=require
SECURE_SSL_REDIRECT=true
REDIS_URL=redis://127.0.0.1:6379/0
CELERY_TASK_ALWAYS_EAGER=false
```

Add email and provider credentials only for enabled integrations. Rotate secrets using a controlled change procedure and restart affected processes.

## Database preparation

Create a dedicated database and least-privilege login. The application role needs connect, schema usage, table/sequence DML, and migration DDL privileges during deployment. For stricter separation, run migrations with a deployment role and web traffic with a DML-only role.

## Services

Install and enable:

- `deploy/systemd/echo-web.service`
- `deploy/systemd/echo-worker.service` when asynchronous tasks are enabled
- `deploy/systemd/echo-beat.service` when scheduled tasks are enabled

Adjust worker counts to CPU, memory, request latency, and provider concurrency. Never run Django's development server in production.

## Reverse proxy and TLS

Install `deploy/nginx/echo.conf` as a site configuration, replace the hostname and certificate paths, test with `nginx -t`, and reload Nginx. Terminate TLS at Nginx, forward `X-Forwarded-Proto`, preserve host headers, enforce the upload limit, and serve immutable static assets directly.

## Release verification

Verify these checks before directing traffic:

```bash
curl --fail https://echo.example.com/health/
curl --fail https://echo.example.com/ready/
```

Then authenticate through the API, create and read a low-risk resource, inspect structured logs, confirm database connections, and verify a Celery job when workers are enabled.

## Rollback

Application rollback means switching the `current` release symlink to the previous tested release and restarting services. Database rollback requires a migration-specific plan; do not blindly reverse destructive migrations. Take a verified backup before schema changes and use forward-fix migrations whenever feasible.

## High availability

For multiple web hosts, use a shared PostgreSQL database, shared Redis where required, shared or object-backed media storage, a load balancer with readiness checks, and one active Celery beat scheduler. Apply migrations as a controlled deployment step, not concurrently on every host.
