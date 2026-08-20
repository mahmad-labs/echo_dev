# Architecture

## System shape

Echo is a modular Django monolith. It keeps domain boundaries explicit while using one deployment unit, one relational database, one authentication system, and one operational control plane. This shape provides transactional consistency and straightforward operations without preventing later extraction of high-load domains.

The runtime consists of:

- Django and Django REST Framework for browser and API traffic.
- PostgreSQL in production, with SQLite available for local development and tests.
- Django's cache abstraction, backed by process-local memory by default or Redis when configured.
- Celery for background work, operating eagerly by default or through Redis-backed workers and a scheduler.
- Bootstrap-based HTML, CSS, and JavaScript for the web interface.
- Provider adapters for AI generation, voice services, internet search, SMTP, and IMAP.

## Domain modules

The `echo/apps` package contains 24 applications:

1. authentication
2. core
3. dashboard
4. chat
5. ai_engine
6. memory
7. vector_database
8. knowledge
9. documents
10. internet
11. code_assistant
12. planner
13. agent_manager
14. workflow_engine
15. tool_manager
16. tasks
17. calendar
18. email
19. notifications
20. api
21. analytics
22. settings
23. voice
24. projects

Each domain owns its models, migrations, serializers, services, permissions, tasks, tests, views, URLs, signals, and admin registrations. Cross-domain orchestration is placed in explicit service modules rather than model methods or signals.

## Layering

### Presentation

Browser views render templates from `templates/`. REST resources use DRF serializers, viewsets, and API views. The compatibility controller under `echo.apps.api` implements the documented Echo route surface.

### Application services

Services coordinate use cases such as workflow execution, project backup and restore, document extraction, notification dispatch, time tracking, calendar conflict detection, vector ranking, AI requests, and safe external HTTP access. Services define transaction boundaries and keep controllers thin.

### Domain and persistence

Django models hold durable state. `UUIDModel`, `OwnedModel`, and `DomainModel` provide consistent identifiers, timestamps, ownership, lifecycle status, descriptive fields, and extensible JSON metadata. Domain-specific fields and constraints remain in their owning applications.

### Infrastructure

Provider adapters isolate external systems. Logging, correlation IDs, exception normalization, pagination, health checks, caching, and reusable permissions live in `echo/common`. Configuration is environment-driven through `config/settings.py`.

## API surfaces

Echo exposes two complementary API surfaces:

- `/api/v1/<domain>/...` provides generated REST resources for every concrete domain model.
- `/api/...` preserves the 238 method/path pairs described by the official specification. High-value action routes call concrete services; standard resource routes resolve to the correct domain model and enforce ownership.

The endpoint catalog at `/api/v1/endpoint-catalog/` allows authenticated clients to inspect the compatibility surface. OpenAPI documentation covers the explicitly registered API views and generated routers.

## Authentication and tenancy

A custom email-first user model is the identity root. Sessions support browser traffic, rotating JWTs support interactive API clients, and hashed API tokens support automation. Roles map to platform permission codenames. Staff and superusers bypass application role checks as administrative operators.

Tenant isolation is ownership-based. Nonstaff requests are scoped to records owned by the authenticated user, or to explicit user/actor fields where ownership is not present. Ownership fields are read-only in generic serializers and assigned server-side on creation.

## Execution model

`AgentManagerOrchestrator` is the coordination entry point for text, voice, and workflow delegation. Each objective becomes a durable root `AgentTask`; specialist work becomes child tasks selected from `AgentRegistry`. `AgentContextBuilder` exposes only declared Memory, Knowledge, project, browser, computer, approval, permission, and execution scopes. `AgentCommunication` records structured assignments, context requests/results, plans, handoffs, and results under one correlation graph. See `docs/AGENT_ORCHESTRATION.md`.

Tool execution uses an allowlisted in-process registry. Agents declare required tools but do not create private tool systems. Workflow execution validates dependencies, rejects cycles, executes registered tools in topological order, and can delegate through the registered `agent.execute` bridge. Celery tasks call the same services used by synchronous requests, avoiding duplicate business logic.

Computer use is a Tool Manager capability rather than a parallel intelligence stack. Controlled browser sessions combine DOM, accessibility data, visible text, screenshots, and optional vision. Authorized desktop sessions combine OS UI-tree providers, real screen capture, OCR/vision, active-window state, and mouse/keyboard input. Both environments follow observe → plan → act → observe result → verify → continue/replan. `ComputerUseOperation` provides the asynchronous browser task identity and is linked back into the Agent Manager task graph. See `docs/COMPUTER_CONTROL.md`.

Voice is an input/output channel to the same Agent Manager. Acoustic sessions begin in wake-word mode and enter an active command session when the user says the wake word or explicitly activates Voice. Accepted user activity renews an inactivity deadline capped at 60 minutes; when that deadline expires Echo returns to wake-word listening instead of shutting down. Optional speaker verification is probabilistic and does not replace approval or account authentication for sensitive actions.

## Data consistency

Use database constraints for identity and uniqueness, service-level validation for cross-record invariants, and `transaction.atomic()` for multi-record operations. Initial migrations are committed for all 24 applications. A post-migration bootstrap creates system roles, permissions, configuration, application registry entries, and feature flags idempotently.

## Security boundaries

- Secrets come from environment variables and are never committed.
- Passwords use Argon2 with PBKDF2 fallback.
- API tokens are stored only as SHA-256 hashes and shown once.
- External fetching rejects non-HTTP schemes, credentials in URLs, loopback, private, link-local, multicast, reserved, and unspecified destinations.
- Upload sizes are bounded and document extraction is type-aware.
- Correlation IDs and structured JSON logs support traceability.
- CSRF, secure cookies, HSTS, content-type protection, clickjacking protection, and conservative referrer policy are configurable in Django settings.

## Scalability

The monolith scales horizontally behind a reverse proxy when PostgreSQL and Redis are enabled. Web, worker, and scheduler processes are independently scalable. Heavy provider calls and workflow jobs should run in Celery. Database indexes are declared on identifiers, ownership-related fields, lifecycle status, timestamps, and frequently queried domain fields.

## Extension rules

Add behavior in the owning app. Introduce a service when an operation spans models or external systems. Keep serializers declarative, avoid signal-driven business workflows, use explicit permissions, add migrations with every schema change, and add tests at service and API boundaries. Extract a domain into a separate service only when operational data demonstrates that the modular monolith is the limiting factor.
