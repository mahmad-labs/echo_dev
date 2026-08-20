# Operations

## Service objectives

Define availability, latency, durability, and background-job objectives for the deployed environment. At minimum monitor HTTP success rate, p50/p95/p99 latency, database saturation, connection count, worker queue depth, task failures, provider errors, disk usage, backup age, and certificate expiry.

## Health endpoints

- `/health/` is a lightweight liveness check.
- `/ready/` verifies database and cache access and returns `503` when a required check fails.
- `/metrics/` exposes a minimal application inventory. Restrict it at the reverse proxy or internal network boundary.

Do not route user traffic to an instance that fails readiness.

## Logging

Echo emits structured JSON logs to standard output. Each request receives a correlation ID, accepting a valid incoming `X-Correlation-ID` or generating one. Reverse proxies and job systems should preserve that identifier. Centralize logs and index timestamp, level, logger, path, user identifier, status code, duration, and correlation ID.

Do not log passwords, raw tokens, provider secrets, email account passwords, uploaded private content, or full authorization headers.

## Background processing

When `CELERY_TASK_ALWAYS_EAGER=true`, tasks run in the calling process and no worker is required. In production, configure Redis, set eager mode to false, and run worker and beat services independently. Monitor queue depth, runtime, retries, worker heartbeats, and dead-letter or permanently failed jobs.

All task handlers must be safe to retry. Persist external operation identifiers and use transaction boundaries that avoid committing half-completed workflows.

## Routine checks

Daily:

- Confirm web, worker, scheduler, PostgreSQL, Redis, and Nginx service status.
- Review error-rate and latency alerts.
- Review failed workflows, notifications, email syncs, and provider requests.
- Confirm the latest backup completed and was transferred to protected storage.

Weekly:

- Inspect database growth, slow queries, locks, and vacuum health.
- Review disk, media, static, and log growth.
- Review inactive API tokens, stale sessions, and unusual login history.
- Restore a small backup sample or validate backup metadata.

Monthly:

- Apply supported dependency and operating-system security updates in staging first.
- Test a full recovery to an isolated environment.
- Review privileged roles, provider credentials, firewall rules, and TLS posture.
- Capacity-test high-growth tables and background queues.

## Incident response

1. Declare the incident and assign an incident lead.
2. Preserve logs, correlation IDs, deployment identifiers, and database state.
3. Reduce impact by disabling a feature flag, pausing a worker queue, reverting a release, or isolating a provider.
4. Restore service using tested procedures.
5. Validate data consistency and delayed jobs.
6. Rotate secrets when exposure is possible.
7. Produce a blameless review with corrective actions, owners, and due dates.

## Database maintenance

Use PostgreSQL-native monitoring and backups. Keep autovacuum enabled. Investigate long transactions, lock waits, index bloat, sequential scans on high-volume tables, and connection exhaustion. Execute heavy data corrections through auditable management commands or controlled scripts with dry-run behavior.

## Capacity and scaling

Scale web workers for request concurrency, Celery workers for queue pressure, and PostgreSQL resources for durable load. Provider-bound jobs often need rate-limited queues rather than more workers. Load-test with production-like data distributions and include authentication, pagination, uploads, and workflow execution.

## Computer-use operations

Every command-driven browser action is dispatched as a durable `ComputerUseOperation`, even when the plan contains a single navigation or scroll. This keeps HTTP requests and the continuous Voice loop responsive while the controlled browser performs page I/O. Operations expose status, current step/tool, progress, result/error, attention requirements, and cancellation state through the computer-use API and Browser workspace.

A controlled browser session is a single mutable environment. Echo serializes computer-use operations within that session while unrelated Chat, Voice, document, knowledge, and workflow work remains independent. Cancellation is checked between steps, during bounded waits, scroll-until loops, and media sampling. WebDriver page-load calls remain bounded by `ECHO_BROWSER_PAGELOAD_TIMEOUT`; a page-load timeout is treated as potentially recoverable only when the browser's actual post-timeout state can be observed and verified.

For Celery deployments, use a supervised browser worker policy compatible with the chosen WebDriver topology. A remote Selenium service is recommended when browser processes should not live beside the Django web process. Monitor `queued`, `running`, `waiting_user`, `cancelling`, `cancelled`, `failed`, and `completed` operation counts and investigate stale running records after host/process failure.
