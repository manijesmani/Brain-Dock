"""Container health probe for the Gunicorn service.

Run as `python healthcheck.py`. Exits 0 when /api/health/ answers 200 and
non-zero otherwise, which is the contract Docker's HEALTHCHECK expects.

Two headers are not optional here. Production sets SECURE_SSL_REDIRECT, so a
plain http request from inside the container would be answered with a 301
rather than reaching the view; X-Forwarded-Proto is what Nginx would normally
supply. And ALLOWED_HOSTS is enforced before any of that, so the Host header
has to name something the settings accept.
"""

import sys
import urllib.error
import urllib.request

URL = "http://127.0.0.1:8000/api/health/"
TIMEOUT_SECONDS = 5


def main() -> int:
    request = urllib.request.Request(
        URL,
        headers={"Host": "127.0.0.1", "X-Forwarded-Proto": "https"},
    )

    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return 0 if response.status == 200 else 1
    # A 503 from the view arrives as HTTPError, a dead socket as URLError.
    # Both mean the same thing to Docker.
    except (urllib.error.URLError, OSError):
        return 1


if __name__ == "__main__":
    sys.exit(main())
