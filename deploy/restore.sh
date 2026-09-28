#!/bin/sh
#
# Restores a backup taken by deploy/backup.sh.
#
#   sudo /srv/braindock/app/deploy/restore.sh \
#       /var/backups/braindock/braindock-db-<stamp>.dump \
#       [/var/backups/braindock/braindock-media-<stamp>.tar.gz]
#
# This destroys the current contents of the database. It asks first, and the
# question is not rhetorical.
set -eu

if [ "$(id -u)" -ne 0 ]; then
    echo "run this with sudo" >&2
    exit 1
fi

APP_DIR="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"

if [ -z "${1:-}" ]; then
    echo "usage: $0 <db dump> [media archive]" >&2
    exit 1
fi

for FILE in "$@"; do
    if [ ! -f "$FILE" ]; then
        echo "no such file: $FILE" >&2
        exit 1
    fi
done

# Absolute before the cd below, so relative arguments still resolve.
DB_FILE="$(readlink -f "$1")"
MEDIA_FILE=""
if [ -n "${2:-}" ]; then
    MEDIA_FILE="$(readlink -f "$2")"
fi

# The braindock commands below inherit this directory; the caller's home
# directory would be unreadable to them.
cd "$APP_DIR"

DATABASE_URL="$(sed -n 's/^DATABASE_URL=//p' "$APP_DIR/backend/.env" | head -n 1)"

echo "About to overwrite the live database with:"
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
systemctl stop braindock-web braindock-worker braindock-beat

# Both files are opened here, as root, and handed over on stdin. A backup can
# then be restored from anywhere -- a copy brought back from another machine
# need not be readable by the braindock account.
echo "==> restoring the database"
# --clean --if-exists drops each object before recreating it, so this works
# against a populated database. --single-transaction makes the whole restore
# roll back if any part of it fails, rather than leaving a half-loaded schema.
# shellcheck disable=SC2024 # root reading the file is the point
sudo -u braindock pg_restore --dbname="$DATABASE_URL" \
    --clean --if-exists --no-owner --single-transaction < "$DB_FILE"

if [ -n "$MEDIA_FILE" ]; then
    echo "==> restoring attachments"
    # shellcheck disable=SC2024 # as above
    sudo -u braindock tar --extract --gzip --directory="$APP_DIR/backend/media" < "$MEDIA_FILE"
fi

echo "==> starting the application"
systemctl start braindock-web braindock-worker braindock-beat

echo
echo "restored. check: systemctl status 'braindock-*'"
