#!/bin/sh
#
# Restores a backup taken by deploy/backup.sh.
#
#   ./deploy/restore.sh backups/braindock-db-<stamp>.dump [backups/braindock-media-<stamp>.tar.gz]
#
# This destroys the current contents of the database. It asks first, and the
# question is not rhetorical.
set -eu

cd "$(dirname "$0")/.."

DB_FILE="${1:-}"
MEDIA_FILE="${2:-}"

if [ -z "$DB_FILE" ]; then
    echo "usage: $0 <db dump> [media archive]" >&2
    exit 1
fi

if [ ! -f "$DB_FILE" ]; then
    echo "no such file: $DB_FILE" >&2
    exit 1
fi

if [ -z "$(docker compose ps --quiet --status running db)" ]; then
    echo "the db service is not running; start the stack first" >&2
    exit 1
fi

echo "About to overwrite the running database with:"
echo "  $DB_FILE"
[ -n "$MEDIA_FILE" ] && echo "  $MEDIA_FILE"
echo
printf "Type 'restore' to continue: "
read -r CONFIRMATION
if [ "$CONFIRMATION" != "restore" ]; then
    echo "cancelled"
    exit 1
fi

# ---------------------------------------------------------------------------
# Stop everything that writes, so nothing is inserted between the drop and the
# reload. Nginx keeps running and answers 502, which is a clearer signal to a
# user than a half-restored database.
# ---------------------------------------------------------------------------
echo "==> stopping the application"
docker compose stop web worker beat

echo "==> restoring the database"
# --clean --if-exists drops each object before recreating it, so this works
# against a populated database. --single-transaction makes the whole restore
# roll back if any part of it fails, rather than leaving a half-loaded schema.
docker compose exec -T db sh -c \
    'pg_restore --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --clean --if-exists --no-owner --single-transaction' \
    < "$DB_FILE"

if [ -n "$MEDIA_FILE" ]; then
    if [ ! -f "$MEDIA_FILE" ]; then
        echo "no such file: $MEDIA_FILE" >&2
        exit 1
    fi
    echo "==> restoring attachments"
    # Started on its own so the volume is mounted, with migrations suppressed:
    # the database has just been restored and must not be touched again.
    docker compose run --rm --no-deps -e BRAINDOCK_RUN_MIGRATIONS=0 -T web \
        tar --extract --gzip --directory /app/media < "$MEDIA_FILE"
fi

echo "==> starting the application"
docker compose start web worker beat

echo
echo "restored. check: docker compose ps"
