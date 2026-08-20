#!/usr/bin/env bash
set -euo pipefail
: "${DATABASE_URL:?DATABASE_URL must be set}"
BACKUP_DIR="${BACKUP_DIR:-./backups}"
mkdir -p "$BACKUP_DIR"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUTPUT="$BACKUP_DIR/echo-$STAMP.dump"
pg_dump --format=custom --no-owner --no-acl --dbname="$DATABASE_URL" --file="$OUTPUT"
sha256sum "$OUTPUT" > "$OUTPUT.sha256"
printf 'Created %s\n' "$OUTPUT"
