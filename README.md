# Echo Enterprise Platform

Echo is a production-oriented Django platform reconstructed from the official Echo project specification. The repository contains one cohesive application with 24 domain apps, 189 concrete models, 238 specification-compatible API routes, owner-scoped REST APIs and protected domain-service endpoints, browser administration, background processing, provider adapters, verified browser/desktop computer use, centrally orchestrated agents, 60-minute wake-aware continuous voice with optional speaker verification, automated tests, database migrations, and conventional Linux deployment assets.


## AI operating workspace

Echo includes a complete AI-first interface at `/` and `/workspace/<section>/`. It replaces dashboard-style module navigation with adaptive workspaces, persistent Echo presence, universal search, command execution, real record creation, document upload, task state changes, responsive behavior, and accessibility controls. See [docs/EXPERIENCE_DESIGN.md](docs/EXPERIENCE_DESIGN.md).

## Requirements

- Python 3.11 or newer
- PostgreSQL for production; SQLite is supported for local development and tests
- Redis only when distributed caching or asynchronous Celery workers are enabled
- Chrome/Chromium, Edge, or Firefox for controlled browser computer-use features
- A virtual environment and standard Python package installation tools

No container runtime is required.

## Installation

### Linux or macOS

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic --noinput
python manage.py runserver
```

### Windows PowerShell

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic --noinput
python manage.py runserver
```

Migration automatically creates the platform roles, permissions, application registry, baseline configuration, and feature flags. `python manage.py bootstrap_echo` is available as an idempotent repair command but is not required for a normal installation.

Open `http://127.0.0.1:8000/`. Sign in with the administrator account. Swagger UI is at `/api/docs/`, ReDoc at `/api/redoc/`, the OpenAPI schema at `/api/schema/`, liveness at `/health/`, and readiness at `/ready/`.

## Production database

Local development defaults to SQLite. Configure PostgreSQL with an environment value such as:

```env
DATABASE_URL=postgresql://echo_app:strong-password@127.0.0.1:5432/echo?sslmode=require
```

Create the database and least-privilege role before migration. Do not use SQLite for a multi-process production deployment.

## Redis and Celery

Celery runs eagerly in the web process by default, so the application is immediately usable without another service. To enable asynchronous workers:

```env
REDIS_URL=redis://127.0.0.1:6379/0
CELERY_TASK_ALWAYS_EAGER=false
```

Then run the worker and scheduler under process supervision:

```bash
celery -A config worker --loglevel=INFO
celery -A config beat --loglevel=INFO
```

## Authentication

The platform supports secure browser sessions, rotating JWT access/refresh tokens, and hashed long-lived API tokens. JWT clients send `Authorization: Bearer <access-token>`. API-token clients send `Authorization: Token <raw-token>` or `X-API-Key: <raw-token>`. Raw API tokens are displayed only once and are never stored.

## Quality checks

```bash
python scripts/static_validate.py
python manage.py check
python manage.py check --deploy
python manage.py makemigrations --check --dry-run
python manage.py validate_echo
python manage.py validate_tools
python manage.py validate_agents
python manage.py echo_health
python manage.py test
```

For the optional development toolchain:

```bash
pip install -r requirements-dev.txt
ruff check .
ruff format --check .
mypy echo config
coverage run manage.py test
coverage report --fail-under=80
```

### Registry and system diagnostics

Echo has one authoritative runtime Tool Registry. Tool families are registered through explicit providers rather than Django import side effects, so the planner, Agent Manager, workflows, APIs and executors all discover the same executable definitions. Before deployment, run:

```bash
python manage.py validate_tools
python manage.py validate_agents
python manage.py echo_health
```

`validate_tools` detects missing/orphan handlers, invalid schemas, duplicate registrations, persisted tools with unavailable handlers, planner references to unavailable tools, and agent/tool mismatches. `validate_agents` verifies registered agents, required tools, permissions and persisted built-in agent records. `echo_health` performs database, cache, registry, model, vector, browser/computer dependency, AI and voice configuration probes without claiming external providers are healthy merely because they import.

## Documentation

- `docs/INSTALLATION.md` — complete local installation and first-run verification
- `docs/AGENT_ORCHESTRATION.md` — Agent Manager, scoped context, structured handoffs, task graph, Memory/Knowledge coordination
- `docs/VOICE.md` — wake/active voice runtime, speaker awareness, state machine, APIs, privacy, memory, and retention
- `docs/COMPUTER_CONTROL.md` — desktop/browser screen understanding, input control, observation, verification, and safety boundaries
- `docs/COMPUTER_USE.md` — observe/act/verify browser runtime, screen evidence, cancellation, approvals, and media intelligence
- `docs/HOMEPAGE_COMMAND_CENTER.md` — adaptive homepage hierarchy and universal command routing
- `docs/ARCHITECTURE.md` — architecture, boundaries, runtime flows, and design decisions
- `docs/DIRECTORY_STRUCTURE.md` — repository layout and ownership
- `docs/CONFIGURATION.md` — environment variables and provider configuration
- `docs/DATABASE.md` — persistence, migrations, indexing, and transaction guidance
- `docs/AUTHENTICATION_AND_AUTHORIZATION.md` — sessions, JWT, API tokens, roles, and ownership
- `docs/API.md` — API behavior, errors, filtering, pagination, and compatibility routing
- `docs/API_ENDPOINT_CATALOG.md` — all 238 specification-compatible method/path pairs
- `docs/MODEL_CATALOG.md` — all 189 concrete models and declared fields
- `docs/SECURITY.md` — application and infrastructure security controls
- `docs/TESTING.md` — test strategy and release quality gates
- `docs/DEVELOPMENT.md` — contribution and engineering workflow
- `docs/DEPLOYMENT.md` — conventional Linux deployment without containers
- `docs/OPERATIONS.md` — monitoring, jobs, incidents, and routine operations
- `docs/BACKUP_AND_RECOVERY.md` — PostgreSQL and media recovery procedures
- `docs/MAINTENANCE.md` — upgrades, cleanup, and lifecycle management
- `docs/TROUBLESHOOTING.md` — diagnostic sequence and common failures
- `docs/SYSTEM_AUDIT.md` — authoritative Tool Registry, execution-pipeline repair, permissions, and integration audit
- `docs/BUILD_VALIDATION.md` — reconstruction validation scope and runtime verification commands

## License

See `LICENSE`.
