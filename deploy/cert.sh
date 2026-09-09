#!/bin/sh
#
# Issues and renews the Let's Encrypt certificate, and installs it where the
# Nginx configuration expects to find it.
#
#   ./deploy/cert.sh issue example.com you@example.com
#   ./deploy/cert.sh renew
#
# Certbot proves control of the domain over plain HTTP, by writing a file that
# Nginx serves from /.well-known/acme-challenge/. So the stack has to be
# running and port 80 has to be reachable from the internet before this can
# work. Bring it up with the self-signed certificate from make-dev-cert.sh
# first; this replaces it.
set -eu

cd "$(dirname "$0")/.."

ACTION="${1:-}"
LETSENCRYPT_DIR="$PWD/deploy/letsencrypt"
CERT_DIR="$PWD/deploy/certs"
CHALLENGE_VOLUME="braindock_certbot"

# Certbot runs as root inside its container, so everything it writes lands as
# root on the host. The installed copies are handed back to whoever ran this.
HOST_UID="$(id -u)"
HOST_GID="$(id -g)"

usage() {
    echo "usage: $0 issue <domain> <email>" >&2
    echo "       $0 renew" >&2
    exit 1
}

require_stack() {
    if [ -z "$(docker compose ps --quiet --status running nginx)" ]; then
        echo "the nginx service is not running." >&2
        echo "certbot's challenge is served by it, so start the stack first." >&2
        exit 1
    fi
}

# Copies the certificate out of certbot's directory tree and into the two
# fixed filenames the Nginx configuration names. Done inside a container
# because /etc/letsencrypt is root-owned and its live/ entries are symlinks
# into archive/ -- `cp -L` resolves them into real files.
install_cert() {
    domain="$1"
    docker run --rm \
        -v "$LETSENCRYPT_DIR:/etc/letsencrypt" \
        -v "$CERT_DIR:/out" \
        --entrypoint sh \
        certbot/certbot -c "
            set -e
            cp -L /etc/letsencrypt/live/$domain/fullchain.pem /out/fullchain.pem
            cp -L /etc/letsencrypt/live/$domain/privkey.pem   /out/privkey.pem
            chown $HOST_UID:$HOST_GID /out/fullchain.pem /out/privkey.pem
            chmod 644 /out/fullchain.pem
            chmod 600 /out/privkey.pem
        "

    # A certificate is only read when the configuration is loaded, so without
    # this the old one stays in use until something restarts Nginx.
    docker compose exec nginx nginx -s reload
    echo "installed and Nginx reloaded"
}

case "$ACTION" in
issue)
    DOMAIN="${2:-}"
    EMAIL="${3:-}"
    [ -n "$DOMAIN" ] && [ -n "$EMAIL" ] || usage

    require_stack
    mkdir -p "$LETSENCRYPT_DIR" "$CERT_DIR"

    docker run --rm \
        -v "$LETSENCRYPT_DIR:/etc/letsencrypt" \
        -v "$CHALLENGE_VOLUME:/var/www/certbot" \
        certbot/certbot certonly \
        --webroot --webroot-path /var/www/certbot \
        -d "$DOMAIN" \
        --email "$EMAIL" \
        --agree-tos --no-eff-email --non-interactive

    install_cert "$DOMAIN"
    ;;

renew)
    require_stack

    if [ ! -d "$LETSENCRYPT_DIR" ]; then
        echo "no certificate has been issued yet; run '$0 issue' first" >&2
        exit 1
    fi

    docker run --rm \
        -v "$LETSENCRYPT_DIR:/etc/letsencrypt" \
        -v "$CHALLENGE_VOLUME:/var/www/certbot" \
        certbot/certbot renew --webroot --webroot-path /var/www/certbot

    # Let's Encrypt renews within 30 days of expiry and exits successfully
    # with no work done otherwise, so this reinstalls the same file most of
    # the time. Copying an unchanged certificate costs nothing.
    DOMAIN="$(ls "$LETSENCRYPT_DIR/live" | grep -v README | head -1)"
    [ -n "$DOMAIN" ] && install_cert "$DOMAIN"
    ;;

*)
    usage
    ;;
esac
