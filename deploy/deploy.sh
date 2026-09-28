#!/bin/sh
#
# Installs or updates BrainDock on this server:
#
#   sudo /srv/braindock/app/deploy/deploy.sh
#
# The same script does the first deployment and every one after it. Each step
# is safe to repeat, so a run that stops part way can simply be started again.
# What has to be in place beforehand -- the system packages, the braindock
# account, this checkout, the database and backend/.env -- is described in
# deploy/README.md.
set -eu

# The systemd units name this path, so the checkout has to be exactly here.
APP_DIR=/srv/braindock/app
HOME_DIR=/srv/braindock
SOCKET=/run/braindock/gunicorn.sock

main() {
    if [ "$(id -u)" -ne 0 ]; then
        echo "run this with sudo" >&2
        exit 1
    fi

    SELF="$(readlink -f "$0")"
    if [ "$SELF" != "$APP_DIR/deploy/deploy.sh" ]; then
        echo "expected the checkout at $APP_DIR, which the systemd units name" >&2
        exit 1
    fi

    # The braindock commands below inherit this directory, and some tools
    # refuse to start in one they cannot read -- such as the home directory
    # of whoever ran sudo.
    cd "$APP_DIR"

    # Pull, then hand over to the script as it now stands, so a deploy always
    # runs the steps of the version it is deploying.
    if [ "${1:-}" != --pulled ]; then
        echo "==> pulling"
        as_app git -C "$APP_DIR" pull --ff-only
        exec "$SELF" --pulled
    fi

    if [ ! -f "$APP_DIR/backend/.env" ]; then
        echo "$APP_DIR/backend/.env is missing; see deploy/README.md" >&2
        exit 1
    fi

    echo "==> backend dependencies"
    if [ ! -x "$APP_DIR/backend/.venv/bin/python" ]; then
        as_app python3.13 -m venv "$APP_DIR/backend/.venv"
    fi
    as_app "$APP_DIR/backend/.venv/bin/pip" install --quiet --disable-pip-version-check \
        -r "$APP_DIR/backend/requirements/prod.txt"

    # Before anything is changed: a configuration Django's own deployment
    # checks object to stops the deploy while the old version still runs.
    echo "==> checking the configuration"
    "$APP_DIR/deploy/manage.sh" check --deploy --fail-level WARNING

    echo "==> database and static files"
    as_app mkdir -p "$APP_DIR/backend/media"
    "$APP_DIR/deploy/manage.sh" migrate --noinput
    "$APP_DIR/deploy/manage.sh" collectstatic --noinput --clear --verbosity 0

    echo "==> frontend"
    build_frontend

    echo "==> services"
    # Nginx reads the built frontend, the admin's static files and, through
    # X-Accel-Redirect, the attachments -- all inside a home directory that is
    # closed to every other account on the host.
    chmod 0750 "$HOME_DIR"
    usermod --append --groups braindock www-data
    install -d -o braindock -g braindock -m 0700 /var/backups/braindock

    install -m 0644 "$APP_DIR"/deploy/systemd/braindock-* /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable --quiet \
        braindock-web braindock-worker braindock-beat braindock-backup.timer
    systemctl restart braindock-web braindock-worker braindock-beat
    systemctl start braindock-backup.timer

    echo "==> nginx"
    "$APP_DIR/deploy/nginx.sh"

    echo "==> health"
    check_health
}

as_app() {
    sudo -u braindock -H "$@"
}

# Built beside the live copy and swapped in at the end, so the site keeps
# serving the previous build for the whole of the build.
build_frontend() {
    FRONTEND="$APP_DIR/frontend"
    (
        cd "$FRONTEND"
        as_app npm ci --no-audit --no-fund --loglevel=error
        as_app npm run build -- --outDir dist.new --emptyOutDir
    )
    rm -rf "$FRONTEND/dist.old"
    if [ -d "$FRONTEND/dist" ]; then
        mv "$FRONTEND/dist" "$FRONTEND/dist.old"
    fi
    mv "$FRONTEND/dist.new" "$FRONTEND/dist"
    rm -rf "$FRONTEND/dist.old"
}

# Two checks. The first asks Gunicorn directly, past Nginx, so its answer is
# about the application alone; the headers are the two Nginx would add. The
# second, once there is a certificate, asks the way a browser does -- through
# the certificate, the proxy, and Nginx's permission to read the frontend.
check_health() {
    SITE_URL="$(sed -n 's/^SITE_URL=//p' "$APP_DIR/backend/.env" | head -n 1)"
    SERVER_NAME="${SITE_URL#https://}"
    SERVER_NAME="${SERVER_NAME%%/*}"

    # --fail-with-body keeps the JSON on a 503, which names the failed check.
    if ! curl --silent --show-error --fail-with-body --max-time 10 \
        --unix-socket "$SOCKET" \
        --header "Host: $SERVER_NAME" \
        --header "X-Forwarded-Proto: https" \
        http://localhost/api/health/; then
        echo >&2
        echo "The application is not answering. Look at: journalctl -u braindock-web -n 50" >&2
        exit 1
    fi
    echo

    if [ ! -f "/etc/letsencrypt/live/$SERVER_NAME/fullchain.pem" ]; then
        echo "BrainDock is up; the site needs a certificate before it can be reached."
        return
    fi

    for URL_PATH in / /api/health/; do
        if ! curl --silent --show-error --fail --max-time 10 --output /dev/null \
            --resolve "$SERVER_NAME:443:127.0.0.1" "https://$SERVER_NAME$URL_PATH"; then
            echo "https://$SERVER_NAME$URL_PATH failed through Nginx." >&2
            echo "Look at: sudo tail -n 20 /var/log/nginx/error.log" >&2
            exit 1
        fi
    done
    echo "BrainDock is up at https://$SERVER_NAME"
}

# Everything runs from inside main, and the script exits right after it: the
# shell has then read the whole file before `git pull` can replace it.
main "$@"
exit
