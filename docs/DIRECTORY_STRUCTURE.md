# Directory structure

```text
.
├── config/                     Django settings, root URLs, WSGI, ASGI, Celery
├── echo/
│   ├── common/                 shared models, services, security, middleware, API primitives
│   ├── apps/                   24 bounded domain applications
│   └── spec_catalog.py         238 specification-compatible method/path pairs
├── templates/                  browser shell, authentication, and dashboard templates
├── static/                     versioned CSS and JavaScript source assets
├── media/                      local development uploads
├── docs/                       architecture, operations, API, model, and runbook documents
├── deploy/                     systemd, Nginx, and log-rotation examples
├── scripts/                    setup, backup, and restore utilities
├── manage.py                   Django command entry point
├── requirements.txt            runtime dependency lock
├── requirements-dev.txt        quality and coverage tooling
├── pyproject.toml              Ruff and mypy configuration
└── .env.example                environment contract
```

Every domain app contains `models.py`, `serializers.py`, `views.py`, `urls.py`, `permissions.py`, `services.py`, `signals.py`, `tasks.py`, `admin.py`, tests, and migrations. Provider-facing domains add focused adapters such as AI completion, safe web fetch, document extraction, IMAP synchronization, voice HTTP integration, or vector operations.

`echo.common` is deliberately small. Domain-specific behavior must remain in its owning app. Shared code is appropriate only for stable cross-cutting concerns: identity and ownership bases, pagination, generated model routers, structured exceptions, correlation IDs, logging, and health checks.
