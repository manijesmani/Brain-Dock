#!/bin/sh
#
# Writes the Nginx site for this deployment and reloads Nginx.
#
#   sudo /srv/braindock/app/deploy/nginx.sh
#
# The name and the admin path come from backend/.env -- SITE_URL and
# DJANGO_ADMIN_URL_PATH -- so Nginx serves exactly what Django answers to,
# and neither has to be written into the repository.
#
# Until a certificate exists for the name, only the plain-HTTP half is
# installed: enough for Let's Encrypt to check the name, which is how the
# certificate is obtained in the first place. Run this again afterwards.
#
# The new configuration is tested before Nginx is reloaded, and put back to
# the previous one if the test fails. Nginx serves the other sites on this
# host too; a mistake here must never be what stops it from starting.
set -eu

if [ "$(id -u)" -ne 0 ]; then
    echo "run this with sudo" >&2
    exit 1
fi

APP_DIR="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"
ENV_FILE="$APP_DIR/backend/.env"

# django-environ keeps the first assignment of a name, so this does too.
env_value() {
    sed -n "s/^$1=//p" "$ENV_FILE" | head -n 1
}

SITE_URL="$(env_value SITE_URL)"
case "$SITE_URL" in
    https://*) ;;
    *)
        echo "SITE_URL in $ENV_FILE must be the site's https:// address" >&2
        exit 1
        ;;
esac
SERVER_NAME="${SITE_URL#https://}"
SERVER_NAME="${SERVER_NAME%%/*}"

ADMIN_PATH="$(env_value DJANGO_ADMIN_URL_PATH)"
ADMIN_PATH="/${ADMIN_PATH:-admin/}"
case "$ADMIN_PATH" in
    *[!A-Za-z0-9/_-]* | *[!/] | //*)
        echo "DJANGO_ADMIN_URL_PATH may hold only letters, digits, - and _," >&2
        echo "with a trailing slash and no leading one, e.g. my-admin/" >&2
        exit 1
        ;;
esac

CERT_DIR="/etc/letsencrypt/live/$SERVER_NAME"

# Debian's layout where it exists, the upstream package's conf.d otherwise.
if [ -d /etc/nginx/sites-enabled ]; then
    SITE=/etc/nginx/sites-available/braindock.conf
    LINK=/etc/nginx/sites-enabled/braindock.conf
else
    SITE=/etc/nginx/conf.d/braindock.conf
    LINK=
fi

render() {
    sed -e "s|@SERVER_NAME@|$SERVER_NAME|g" \
        -e "s|@ADMIN_PATH@|$ADMIN_PATH|g" \
        -e "s|@APP_DIR@|$APP_DIR|g" \
        -e "s|@CERT_DIR@|$CERT_DIR|g" \
        "$APP_DIR/deploy/nginx/$1"
}

PREVIOUS="$(mktemp)"
trap 'rm -f "$PREVIOUS"' EXIT
if [ -f "$SITE" ]; then
    cp "$SITE" "$PREVIOUS"
else
    : > "$PREVIOUS"
fi

mkdir -p /var/www/letsencrypt

if [ -f "$CERT_DIR/fullchain.pem" ]; then
    MODE=https
    { render http.conf; echo; render https.conf; } > "$SITE"
else
    MODE=http
    render http.conf > "$SITE"
fi
if [ -n "$LINK" ]; then
    ln -sfn "$SITE" "$LINK"
fi

if ! nginx -t; then
    if [ -s "$PREVIOUS" ]; then
        cp "$PREVIOUS" "$SITE"
    else
        rm -f "$SITE" ${LINK:+"$LINK"}
    fi
    echo >&2
    echo "Nginx rejected the new configuration. The previous one is back in place" >&2
    echo "and Nginx was not reloaded." >&2
    exit 1
fi

systemctl reload nginx

if [ "$MODE" = http ]; then
    cat <<EOF

There is no certificate for $SERVER_NAME yet, so only plain HTTP is set up.
Get one with:

    sudo certbot certonly --webroot -w /var/www/letsencrypt -d $SERVER_NAME \\
        --deploy-hook "systemctl reload nginx"

Then run this script again to switch the site to HTTPS.
EOF
else
    echo "Nginx is serving https://$SERVER_NAME"
fi
