"""Probe the private Gunicorn listener with the same scheme as the TLS proxy."""

import json
import os
from urllib.request import Request, urlopen

request = Request(
    "http://127.0.0.1:8000/api/health/",
    headers={"Host": os.environ["SITE_DOMAIN"], "X-Forwarded-Proto": "https"},
)
with urlopen(request, timeout=5) as response:
    if json.load(response).get("status") != "ok":
        raise SystemExit(1)
