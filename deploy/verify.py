"""Build and exercise a disposable Docker installation; never use production volumes.

Run from the repository with: python3 deploy/verify.py
The isolated test project and its volumes are removed even if a check fails.
"""

import argparse
import http.client
import json
import secrets
import shutil
import socket
import subprocess
import tempfile
from http.cookies import SimpleCookie
from pathlib import Path
from unittest.mock import patch

import docker as ops

SOURCE = Path(__file__).resolve().parent.parent
DOMAIN = "smoke.braindock.test"


def shell(code):
    result = ops.compose(
        "exec",
        "-T",
        "backend",
        "python",
        "manage.py",
        "shell",
        "--no-imports",
        "-c",
        code,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def request(port, path, *, cookies=None, method="GET", data=None, csrf=None):
    headers = {
        "Host": DOMAIN,
        "X-Forwarded-Proto": "https",
        "X-Forwarded-For": "127.0.0.1",
        "Origin": "https://" + DOMAIN,
    }
    if cookies:
        headers["Cookie"] = "; ".join(
            f"{key}={value}" for key, value in cookies.items()
        )
    if csrf:
        headers["X-CSRFToken"] = csrf
    if data is not None:
        headers["Content-Type"] = "application/json"
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=15)
    try:
        connection.request(
            method,
            path,
            body=json.dumps(data) if data is not None else None,
            headers=headers,
        )
        response = connection.getresponse()
        body = response.read()
        fields = response.getheaders()
        if cookies is not None:
            for key, value in fields:
                if key.lower() == "set-cookie":
                    jar = SimpleCookie(value)
                    cookies.update({name: item.value for name, item in jar.items()})
        return (
            response.status,
            body,
            {key.lower(): value for key, value in fields},
        )
    finally:
        connection.close()


def checks(port):
    assert (
        shell("from apps.users.models import User; print(User.objects.count())") == "0"
    )
    assert (
        shell(
            "from django.db import connection; c=connection.cursor(); "
            "c.execute('SELECT rolsuper, rolcreatedb, rolcreaterole FROM pg_roles "
            "WHERE rolname=current_user'); print(c.fetchone())"
        )
        == "(False, False, False)"
    )
    task = json.loads(
        shell(
            "import json; from apps.reminders.tasks import dispatch_due_reminders; "
            "print(json.dumps(dispatch_due_reminders.delay().get(timeout=30)))"
        )
    )
    assert task == {"due": 0, "fired": 0, "skipped": 0}
    status, body, headers = request(port, "/ideas")
    assert status == 200 and b"theme.js" in body
    assert "no-store" in headers.get("cache-control", "")
    assert "default-src 'self'" in headers.get("content-security-policy", "")
    assert request(port, "/static/admin/css/base.css")[0] == 200
    assert request(port, "/media/probe.txt")[0] == 404
    assert request(port, "/internal-media/probe.txt")[0] == 404
    password = secrets.token_urlsafe(24)
    shell(
        "from apps.users.models import User; "
        f"User.objects.create_user(username='smoke', password={password!r}, is_premium=True)"
    )
    cookies = {}
    assert request(port, "/api/auth/csrf/", cookies=cookies)[0] == 200
    data = {"username": "smoke", "password": password}
    assert (
        request(port, "/api/auth/login/", cookies=cookies, method="POST", data=data)[0]
        == 403
    )
    assert (
        request(
            port,
            "/api/auth/login/",
            cookies=cookies,
            method="POST",
            data=data,
            csrf=cookies["braindock_csrftoken"],
        )[0]
        == 200
    )
    status, body, headers = request(port, "/api/auth/me/", cookies=cookies)
    assert status == 200 and json.loads(body)["username"] == "smoke"
    assert "Secure" in headers.get("set-cookie", "")
    attachment = json.loads(
        shell("""
import json
from django.core.files.base import ContentFile
from apps.users.models import User
from apps.ideas.models import Idea, Attachment
u=User.objects.get(username='smoke')
i=Idea.objects.create(owner=u, title='Before backup')
a=Attachment(idea=i, owner=u, kind='image', content_type='text/plain', size_bytes=13,
             original_name='probe.txt')
a.file.save('probe.txt', ContentFile(b'private-media'), save=True)
print(json.dumps({'id': a.pk, 'path': a.file.name, 'idea': i.pk}))
""")
    )
    path = f"/api/attachments/{attachment['id']}/file/"
    assert request(port, path, cookies=cookies)[1] == b"private-media"
    assert request(port, path)[0] in (401, 403)
    assert (
        request(port, "/internal-media/" + attachment["path"], cookies=cookies)[0]
        == 404
    )
    backup = ops.backup()
    shell(
        "from apps.ideas.models import Idea, Attachment; from pathlib import Path; "
        "Idea.objects.update(title='Changed'); "
        "a=Attachment.objects.first(); Path(a.file.path).write_text('changed')"
    )
    with patch("builtins.input", return_value="RESTORE"):
        ops.restore(argparse.Namespace(directory=str(backup)))
    # Restoring also exercises a stopped/recreated backend and the proxy's DNS refresh.
    ops.compose(
        "up",
        "-d",
        "--wait",
        "--wait-timeout",
        "180",
        "backend",
        "worker",
        "beat",
        "frontend",
    )
    ops.health()
    assert (
        shell("from apps.ideas.models import Idea; print(Idea.objects.first().title)")
        == "Before backup"
    )
    assert request(port, path, cookies=cookies)[1] == b"private-media"
    ids = ops.compose("ps", "-q", capture_output=True, text=True).stdout.split()
    inspected = subprocess.run(
        ["docker", "inspect", *ids], check=True, capture_output=True, text=True
    )
    for item in json.loads(inspected.stdout):
        service = item["Config"]["Labels"]["com.docker.compose.service"]
        ports = item["HostConfig"]["PortBindings"] or {}
        if service == "frontend":
            assert ports == {
                "8080/tcp": [{"HostIp": "127.0.0.1", "HostPort": str(port)}]
            }
        else:
            assert not ports, (service, ports)
        if service in ("frontend", "backend", "worker", "beat", "redis"):
            assert item["HostConfig"]["ReadonlyRootfs"]
    print(
        "PASS: fresh database, least-privilege role, worker, proxy, auth/CSRF, private media, backup/restore, persistence, isolated ports."
    )


def main():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    with tempfile.TemporaryDirectory(prefix="braindock-verify-") as temporary:
        root = Path(temporary)
        for name in ("backend", "frontend", "database"):
            (root / name).symlink_to(SOURCE / name, target_is_directory=True)
        (root / "deploy").mkdir()
        shutil.copy2(SOURCE / "compose.yaml", root / "compose.yaml")
        shutil.copy2(
            SOURCE / "deploy/docker-nginx.conf.template",
            root / "deploy/docker-nginx.conf.template",
        )
        ops.ROOT, ops.SECRETS = root, root / ".secrets"
        ops.setup(argparse.Namespace(domain=DOMAIN, port=port))
        env = root / ".env"
        env.write_text(
            env.read_text().replace(
                "COMPOSE_PROJECT_NAME=braindock\n",
                "COMPOSE_PROJECT_NAME=braindock-check-" + secrets.token_hex(4) + "\n",
            )
        )
        try:
            ops.up()
            checks(port)
        except BaseException:
            # Preserve the original failure if Docker itself is unavailable.
            try:
                ops.compose("logs", "--tail", "60")
            except subprocess.CalledProcessError:
                pass
            raise
        finally:
            # This project was generated above; no existing deployment is selected.
            ops.compose("down", "--volumes", "--remove-orphans")


if __name__ == "__main__":
    main()
