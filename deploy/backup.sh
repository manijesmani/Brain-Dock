#!/bin/sh
#
# Takes a backup of both things that cannot be rebuilt from the repository:
# the database, and the uploaded attachments.
#
#   sudo /srv/braindock/app/deploy/backup.sh
#
# braindock-backup.timer runs it nightly. Environment:
#   BRAINDOCK_BACKUP_DIR        where to write   (default /var/backups/braindock)
#   BRAINDOCK_RETENTION_DAYS    how long to keep (default 14)
set -eu

SELF="$(readlink -f "$0")"

# The braindock account owns the attachments and, through peer
# authentication, the database role.
if [ "$(id -un)" != braindock ]; then
    if [ "$(id -u)" -ne 0 ]; then
        echo "run this with sudo" >&2
        exit 1
    fi
    exec sudo -u braindock -H \
        BRAINDOCK_BACKUP_DIR="${BRAINDOCK_BACKUP_DIR:-}" \
        BRAINDOCK_RETENTION_DAYS="${BRAINDOCK_RETENTION_DAYS:-}" \
        "$SELF" "$@"
fi

APP_DIR="$(cd "$(dirname "$SELF")/.." && pwd)"
# Started from someone else's home directory, find would fail on reading it.
cd "$APP_DIR"
BACKUP_DIR="${BRAINDOCK_BACKUP_DIR:-/var/backups/braindock}"
RETENTION_DAYS="${BRAINDOCK_RETENTION_DAYS:-14}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"

DB_FILE="$BACKUP_DIR/braindock-db-$STAMP.dump"
MEDIA_FILE="$BACKUP_DIR/braindock-media-$STAMP.tar.gz"

# Nobody else on the host has any business reading these.
umask 077

# The database the application itself uses, read from its own configuration.
# django-environ keeps the first assignment of a name, so this does too.
DATABASE_URL="$(sed -n 's/^DATABASE_URL=//p' "$APP_DIR/backend/.env" | head -n 1)"
if [ -z "$DATABASE_URL" ]; then
    echo "DATABASE_URL is not set in $APP_DIR/backend/.env" >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
# --format=custom rather than plain SQL: it is compressed, and pg_restore can
# read a single table out of it without replaying the whole file.
echo "==> dumping the database"
pg_dump --dbname="$DATABASE_URL" --format=custom --no-owner --file="$DB_FILE"

# A dump nobody has read back is not a backup. pg_restore --list parses the
# archive's table of contents and fails on a truncated or corrupt file.
echo "==> verifying the dump"
if ! pg_restore --list "$DB_FILE" > /dev/null; then
    echo "the dump did not parse; leaving it in place for inspection" >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Attachments
# ---------------------------------------------------------------------------
echo "==> archiving attachments"
tar --create --gzip --file="$MEDIA_FILE" --directory="$APP_DIR/backend/media" .

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
