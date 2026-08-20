# Backup and recovery

## Backup scope

Back up PostgreSQL, uploaded media, environment/secrets through the organization's secrets backup process, and deployment configuration. Static files can be regenerated with `collectstatic` and source code should come from version control or the approved release artifact.

## PostgreSQL

`scripts/backup_postgres.sh` creates a custom-format `pg_dump` and SHA-256 checksum using `DATABASE_URL`. Store backups in encrypted, access-controlled, geographically appropriate storage with lifecycle retention.

```bash
DATABASE_URL='postgresql://...' BACKUP_DIR=/srv/echo-backups scripts/backup_postgres.sh
```

Restore into a clean recovery environment first:

```bash
DATABASE_URL='postgresql://...' scripts/restore_postgres.sh /srv/echo-backups/echo-YYYYMMDDTHHMMSSZ.dump
python manage.py migrate
python manage.py validate_echo
python manage.py check --deploy
```

## Media

Use a filesystem snapshot or object-storage versioning strategy consistent with database recovery points. After restoration, verify that database storage references exist and that no unexpected objects are exposed.

## Recovery procedure

1. Declare the incident and recovery point objective.
2. Stop writes or isolate the replacement environment.
3. Preserve logs and damaged data for investigation.
4. Verify backup checksum and provenance.
5. Restore database and media.
6. Apply the release's migrations.
7. rotate credentials when compromise is possible.
8. Run structural, readiness, authentication, API, upload, and background-job smoke tests.
9. Reopen traffic gradually and monitor errors, latency, queues, and data integrity.

Perform scheduled restore drills and record measured recovery time and data loss against objectives.
