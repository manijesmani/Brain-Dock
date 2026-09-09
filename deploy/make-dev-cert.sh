#!/bin/sh
#
# Generates a self-signed certificate into deploy/certs/ so the full stack can
# be brought up and exercised on a machine with no domain name.
#
# This is for verifying the deployment, not for serving anyone. A browser will
# warn about it, and it should never be used on a public address -- see
# deploy/README.md for issuing a real certificate with certbot.
#
#   ./deploy/make-dev-cert.sh [hostname]
set -eu

HOST="${1:-localhost}"
CERT_DIR="$(cd "$(dirname "$0")" && pwd)/certs"

mkdir -p "$CERT_DIR"

if [ -f "$CERT_DIR/fullchain.pem" ]; then
    echo "refusing to overwrite $CERT_DIR/fullchain.pem" >&2
    echo "delete it first if that is what you meant" >&2
    exit 1
fi

# The subjectAltName is what browsers actually read; a bare CN has been
# ignored for years.
openssl req -x509 -nodes \
    -newkey rsa:2048 \
    -days 365 \
    -keyout "$CERT_DIR/privkey.pem" \
    -out "$CERT_DIR/fullchain.pem" \
    -subj "/CN=$HOST" \
    -addext "subjectAltName=DNS:$HOST,DNS:localhost,IP:127.0.0.1"

# The key is mounted read-only into Nginx, which runs as an unprivileged user
# inside the container, but on the host it should stay unreadable to others.
chmod 600 "$CERT_DIR/privkey.pem"
chmod 644 "$CERT_DIR/fullchain.pem"

echo
echo "self-signed certificate for '$HOST' written to deploy/certs/"
openssl x509 -in "$CERT_DIR/fullchain.pem" -noout -subject -dates -ext subjectAltName
