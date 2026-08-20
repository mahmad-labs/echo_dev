#!/usr/bin/env bash
set -euo pipefail
: "${DATABASE_URL:?DATABASE_URL must be set}"
BACKUP_FILE="${1:?Usage: restore_postgres.sh PATH_TO_DUMP}"
sha256sum --check "$BACKUP_FILE.sha256"
pg_restore --clean --if-exists --no-owner --no-acl --dbname="$DATABASE_URL" "$BACKUP_FILE"
printf 'Restored %s\n' "$BACKUP_FILE"
