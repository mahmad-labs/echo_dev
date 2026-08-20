# Installation

## 1. Prepare Python

Use a supported CPython release and a dedicated virtual environment. The project does not require a container runtime or a JavaScript build pipeline.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

On Windows PowerShell, activate with `.venv\Scripts\Activate.ps1`.

## 2. Configure the environment

Copy `.env.example` to `.env`. Development can start with the supplied SQLite URL and console email backend. Set a unique `DJANGO_SECRET_KEY` before sharing an environment or exposing the service to a network.

```bash
cp .env.example .env
```

Production configuration must use PostgreSQL, a high-entropy secret, explicit allowed hosts and trusted origins, HTTPS cookie settings, and real provider credentials where the corresponding integrations are used.

## 3. Initialize the database

The repository includes initial migrations for all 24 Echo apps. `makemigrations` should report no changes; running it is safe and confirms model/migration consistency.

```bash
python manage.py makemigrations
python manage.py migrate
```

The `post_migrate` bootstrap creates platform roles, custom permissions, feature flags, application registry records, and baseline system configuration. The operation is idempotent.

## 4. Create an administrator and static assets

```bash
python manage.py createsuperuser
python manage.py collectstatic --noinput
```

The custom user model authenticates by email. Administrators receive the Echo Administrator role automatically.

## 5. Start and verify

```bash
python manage.py runserver
```

Verify these endpoints:

- `/health/` returns process liveness.
- `/ready/` verifies database and cache access.
- `/login/` accepts the administrator account.
- `/api/docs/` loads the interactive API schema after sign-in.
- `/admin/` displays all registered domain models.

Run the structural validator and test suite before development:

```bash
python manage.py validate_echo
python manage.py test
```

## PostgreSQL first run

Create a database owner with only the privileges required for the Echo database. Set `DATABASE_URL`, then run the same migration commands. Use SSL according to the database topology. The URL parser supports `postgres://` and `postgresql://` schemes and honors the `sslmode` query parameter.

## Optional asynchronous processing

The default eager Celery mode needs no broker. For separate workers, configure `REDIS_URL`, set `CELERY_TASK_ALWAYS_EAGER=false`, and start supervised worker and beat processes. The systemd examples under `deploy/systemd/` use this mode.

## Controlled browser computer use

Computer-use requires a supported local browser (Chrome/Chromium, Edge, or Firefox). Selenium is installed from `requirements.txt`; modern Selenium Manager resolves a compatible driver when the host allows it. In locked-down environments, install the browser/driver through the operating system or point `ECHO_BROWSER_BINARY` at the approved browser executable. `ECHO_BROWSER_REMOTE_URL` may target an organization-managed Selenium service. No container runtime is required.

For a visible local agent, keep `ECHO_BROWSER_HEADLESS=false`. A server deployment controls a browser on the server/remote browser host, not a user's unrelated desktop browser. Keep private-network access disabled unless the deployment explicitly requires and secures it.

When Redis/Celery is not configured, computer-use operations run in Echo's bounded local thread executor. For production queues, configure Redis and a supervised Celery worker; use a dedicated browser queue/worker policy so one mutable browser session is not intentionally shared across competing worker processes.
