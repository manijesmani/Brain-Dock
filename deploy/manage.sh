#!/bin/sh
#
# Runs manage.py the way the services run Django: as the braindock account,
# against the production settings, with the project's own virtualenv.
#
#   sudo /srv/braindock/app/deploy/manage.sh createsuperuser
#   sudo /srv/braindock/app/deploy/manage.sh telegram_webhook info
#
# manage.py on its own falls back to the development settings, which is the
# reason this exists.
set -eu

SELF="$(readlink -f "$0")"

if [ "$(id -un)" != braindock ]; then
    if [ "$(id -u)" -ne 0 ]; then
        echo "run this with sudo" >&2
        exit 1
    fi
    exec sudo -u braindock -H "$SELF" "$@"
fi

cd "$(dirname "$SELF")/../backend"
DJANGO_SETTINGS_MODULE=config.settings.prod exec .venv/bin/python manage.py "$@"
