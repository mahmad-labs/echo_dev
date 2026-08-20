# Database architecture

PostgreSQL is the production system of record. SQLite exists to satisfy zero-infrastructure local development and automated test workflows. The schema uses UUID identifiers for domain records and the user model, UTC timestamps, explicit ownership relations, JSON extension fields, and domain-specific relational fields.

## Migrations

All 24 apps contain an initial migration and the migration model set matches the 183 concrete model declarations. The authentication migration depends on Django auth; all other owner-aware apps use a swappable dependency on the configured user model. Intra-app relationship operations are ordered so target models exist before dependent fields are applied.

Before merging schema changes:

```bash
python manage.py makemigrations --check --dry-run
python manage.py migrate --plan
python manage.py test
```

Review generated operations, lock behavior, defaults, indexes, nullability, data conversion, and rollback implications. Large production data migrations should be separated from schema migrations and written to be restartable.

## Transactions

Domain services, workflow execution, planning, project restore, notification delivery logging, and bootstrap operations use transactions. External network calls should not be enclosed in long database transactions unless the persisted state machine requires it. Where a network operation is involved, Echo records running, completed, or failed state with correlation information.

## Connections

`DB_CONN_MAX_AGE` controls persistent connections. Size the application process count and database pool together. Use server-side telemetry to monitor lock waits, slow queries, connection saturation, autovacuum health, and table/index growth.

## JSON fields

JSON fields preserve extensibility where the specification defines provider-specific or evolving configuration. Stable business keys that participate in joins, constraints, ordering, or frequent filters should be promoted to typed fields in future migrations rather than hidden permanently in JSON.
