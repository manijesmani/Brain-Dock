#!/bin/sh
#
# Shared entrypoint for all three backend containers (web, worker, beat).
#
# Ordering against Postgres and Redis is not handled here: compose declares
# `depends_on: condition: service_healthy`, so this script only ever starts
# once those two answer. A wait-for-it loop would duplicate that badly.
set -eu

# Only one container may run migrations, and only one needs the static files.
# The worker and the beat scheduler start with this unset, so a deploy never
# races two `migrate` processes against the same database.
if [ "${BRAINDOCK_RUN_MIGRATIONS:-0}" = "1" ]; then
    echo "==> applying migrations"
    python manage.py migrate --noinput

    # The admin is the only server-rendered page, but it is unusable without
    # these, and Nginx serves them straight off the shared volume.
    echo "==> collecting static files"
    python manage.py collectstatic --noinput --clear
fi

exec "$@"
