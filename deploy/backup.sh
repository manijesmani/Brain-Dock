#!/bin/sh
#
# Takes a backup of both things that cannot be rebuilt from the repository:
# the database, and the uploaded attachments.
#
#   ./deploy/backup.sh
#
# Environment:
#   BRAINDOCK_BACKUP_DIR        where to write   (default ./backups)
#   BRAINDOCK_RETENTION_DAYS    how long to keep (default 14)
#
# The stack has to be running. That is not a limitation worth working around:
# pg_dump needs the server up anyway.
set -eu

cd "$(dirname "$0")/.."

BACKUP_DIR="${BRAINDOCK_BACKUP_DIR:-./backups}"
RETENTION_DAYS="${BRAINDOCK_RETENTION_DAYS:-14}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"

DB_FILE="$BACKUP_DIR/braindock-db-$STAMP.dump"
MEDIA_FILE="$BACKUP_DIR/braindock-media-$STAMP.tar.gz"

mkdir -p "$BACKUP_DIR"

require_running() {
    if [ -z "$(docker compose ps --quiet --status running "$1")" ]; then
        echo "service '$1' is not running; start the stack first" >&2
        exit 1
    fi
}

require_running db
require_running web

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
# --format=custom rather than plain SQL: it is compressed, and pg_restore can
# read a single table out of it without replaying the whole file.
echo "==> dumping the database"
docker compose exec -T db sh -c \
    'pg_dump --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --format=custom --no-owner' \
    > "$DB_FILE"

# A dump nobody has read back is not a backup. pg_restore --list parses the
# archive's table of contents and fails on a truncated or corrupt file.
echo "==> verifying the dump"
if ! docker compose exec -T db pg_restore --list < "$DB_FILE" > /dev/null; then
    echo "the dump did not parse; leaving it in place for inspection" >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Attachments
# ---------------------------------------------------------------------------
echo "==> archiving attachments"
docker compose exec -T web tar --create --gzip --directory /app/media . > "$MEDIA_FILE"

echo "==> verifying the archive"
if ! gzip --test "$MEDIA_FILE"; then
    echo "the media archive is corrupt" >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Retention
# ---------------------------------------------------------------------------
# Only files this script's own naming produces are ever deleted.
echo "==> removing backups older than $RETENTION_DAYS days"
find "$BACKUP_DIR" -maxdepth 1 -type f \
    \( -name 'braindock-db-*.dump' -o -name 'braindock-media-*.tar.gz' \) \
    -mtime "+$RETENTION_DAYS" -print -delete

echo
echo "done:"
ls -lh "$DB_FILE" "$MEDIA_FILE"
