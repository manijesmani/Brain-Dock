"""Small, explicit operations for the Docker deployment; Python standard library only."""

import argparse
import gzip
import hashlib
import io
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tarfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
APPS = ["frontend", "beat", "worker", "backend"]
SECRETS = ROOT / ".secrets"


def run(args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def compose(*args, **kwargs):
    settings = config()
    kwargs.setdefault("env", {**os.environ, **settings})
    return run(
        [
            "docker",
            "compose",
            "--project-name",
            settings["COMPOSE_PROJECT_NAME"],
            "--project-directory",
            str(ROOT),
            "--env-file",
            str(ROOT / ".env"),
            "-f",
            str(ROOT / "compose.yaml"),
            *args,
        ],
        **kwargs,
    )


def config():
    path = ROOT / ".env"
    if not path.is_file():
        raise ValueError("First run: ./dock setup --domain braindock.ir")
    settings = dict(
        line.split("=", 1)
        for line in path.read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )
    domain_name(settings["SITE_DOMAIN"])
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", settings["COMPOSE_PROJECT_NAME"]):
        raise ValueError("Invalid Compose project name.")
    if not re.fullmatch(r"[A-Za-z0-9_-]+/", settings["DJANGO_ADMIN_URL_PATH"]):
        raise ValueError("The admin path must be a single name with a trailing slash.")
    if not 1024 <= int(settings["APP_PORT"]) <= 65535:
        raise ValueError("Invalid internal port.")
    return settings


def domain_name(value):
    name = value.strip().lower()
    if "://" in name:
        parsed = urlsplit(name)
        if (
            parsed.scheme != "https"
            or parsed.path not in ("", "/")
            or parsed.query
            or parsed.fragment
        ):
            raise argparse.ArgumentTypeError(
                "Enter a domain or its HTTPS home address."
            )
        name = parsed.netloc
    if len(name) > 253 or not re.fullmatch(
        r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}", name
    ):
        raise argparse.ArgumentTypeError("Invalid domain; example: braindock.ir")
    return name


def private_file(path, value, mode=0o600):
    # Exclusive creation prevents an accidental rerun from rotating secrets.
    with os.fdopen(
        os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode), "w"
    ) as handle:
        handle.write(value)
    path.chmod(mode)


def setup(args):
    if (ROOT / ".env").exists() or SECRETS.exists():
        raise ValueError(
            "Configuration already exists; setup never replaces it or rotates passwords."
        )
    if not 1024 <= args.port <= 65535:
        raise ValueError("The internal port must be between 1024 and 65535.")
    SECRETS.mkdir(mode=0o700)
    SECRETS.chmod(0o700)
    db_password = secrets.token_hex(32)
    redis_password = secrets.token_hex(32)
    values = {
        "postgres_admin_password": secrets.token_hex(32),
        "db_app_password": db_password,
        "database_url": f"postgres://braindock:{db_password}@database:5432/braindock",
        "django_secret_key": secrets.token_urlsafe(64),
        "redis_password": redis_password,
        "redis_url": f"redis://:{redis_password}@redis:6379/0",
        "telegram_bot_token": "",
        "telegram_webhook_secret": secrets.token_urlsafe(32),
    }
    for name, value in values.items():
        # Compose file secrets preserve the host file permissions. Readable
        # files work for non-root containers; the enclosing 0700 directory
        # prevents other host users from opening them.
        private_file(SECRETS / name, value, mode=0o444)
    settings = {
        "COMPOSE_PROJECT_NAME": "braindock",
        "SITE_DOMAIN": args.domain,
        "SITE_URL": f"https://{args.domain}",
        "APP_PORT": str(args.port),
        "DJANGO_ALLOWED_HOSTS": args.domain,
        "DJANGO_CSRF_TRUSTED_ORIGINS": f"https://{args.domain}",
        "DJANGO_ADMIN_URL_PATH": secrets.token_hex(12) + "/",
        "OWNER_TELEGRAM_USERNAME": "manijesmani",
        "TELEGRAM_BOT_USERNAME": "",
        "FREE_IDEA_LIMIT": "2",
    }
    private_file(
        ROOT / ".env", "".join(f"{key}={value}\n" for key, value in settings.items())
    )
    nginx_config(settings)
    print("Configuration created. No default account or password was added.")
    print("Next: ./dock up, then ./dock owner")


def nginx_config(settings=None):
    settings = settings or config()
    domain = domain_name(settings["SITE_DOMAIN"])
    port = int(settings["APP_PORT"])
    if not 1024 <= port <= 65535:
        raise ValueError("Invalid internal port.")
    target = ROOT / "deploy/generated"
    target.mkdir(parents=True, exist_ok=True)
    template = (ROOT / "deploy/docker-nginx.conf.template").read_text()
    result = template.replace("@DOMAIN@", domain).replace("@PORT@", str(port))
    (target / "braindock.conf").write_text(result)
    print("Host Nginx configuration: deploy/generated/braindock.conf")


def running_apps():
    output = compose(
        "ps", "--services", "--status", "running", capture_output=True, text=True
    )
    return [name for name in APPS if name in output.stdout.splitlines()]


def database_command(command, **kwargs):
    # No password on the command line or in Compose's inspectable environment.
    return compose(
        "exec",
        "-T",
        "database",
        "sh",
        "-ec",
        'export PGPASSWORD="$(cat /run/secrets/db_app_password)"; exec ' + command,
        **kwargs,
    )


def media_command(action, **kwargs):
    return compose(
        "run",
        "--rm",
        "--no-deps",
        "-T",
        "backend",
        "python",
        "container/media_archive.py",
        action,
        **kwargs,
    )


def checksum(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def backup(*, resume=True):
    active = running_apps()
    stamp = (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        + "-"
        + secrets.token_hex(2)
    )
    target = ROOT / "backups" / stamp
    target.mkdir(parents=True, mode=0o700)
    target.chmod(0o700)
    completed = False
    try:
        if active:
            compose("stop", *active)
        with (target / "database.dump").open("wb") as handle:
            database_command(
                "pg_dump -h 127.0.0.1 -U braindock -d braindock --format=custom --no-owner --no-privileges",
                stdout=handle,
            )
        with (target / "database.dump").open("rb") as handle:
            compose(
                "exec",
                "-T",
                "database",
                "pg_restore",
                "--list",
                stdin=handle,
                stdout=subprocess.DEVNULL,
            )
        with (target / "media.tar.gz").open("wb") as handle:
            media_command("pack", stdout=handle)
        validate_archive(target / "media.tar.gz")
        shutil.copy2(ROOT / ".env", target / "config.env")
        shutil.copytree(SECRETS, target / "secrets")
        manifest = {
            name: checksum(target / name) for name in ("database.dump", "media.tar.gz")
        }
        private_file(target / "checksums.json", json.dumps(manifest, indent=2) + "\n")
        print(f"Verified backup: {target}")
        completed = True
        return target
    finally:
        if (resume or not completed) and active:
            compose("start", *active)


def validate_archive(path):
    # Inspect the entire archive before any service is stopped or data replaced.
    # Tar readers stop at end-of-tar before gzip's checksum/footer; read both.
    with gzip.open(path, "rb") as compressed:
        while compressed.read(1024 * 1024):
            pass
    with tarfile.open(path, "r:gz") as archive:
        for member in archive:
            parts = PurePosixPath(member.name).parts
            if (
                PurePosixPath(member.name).is_absolute()
                or ".." in parts
                or not (member.isdir() or member.isfile())
            ):
                raise ValueError("The media archive contains an unsafe path or a link.")


def up():
    # Build first: a failed download/build cannot take down the running app.
    compose("build", "--pull", "database", "backend", "frontend")
    active = running_apps()
    if active:
        backup(resume=False)
    compose("up", "-d", "--wait", "--wait-timeout", "180", "database", "redis")
    compose(
        "up",
        "--no-deps",
        "--force-recreate",
        "--abort-on-container-exit",
        "--exit-code-from",
        "migrate",
        "migrate",
    )
    compose("up", "-d", "--no-deps", "--wait", "--wait-timeout", "180", "backend")
    compose(
        "up",
        "-d",
        "--no-deps",
        "--wait",
        "--wait-timeout",
        "180",
        "worker",
        "beat",
        "frontend",
    )
    health()


def health():
    settings = config()
    for endpoint in ("/", "/api/health/"):
        request = Request(
            f"http://127.0.0.1:{settings['APP_PORT']}{endpoint}",
            headers={
                "Host": settings["SITE_DOMAIN"],
                "X-Forwarded-Proto": "https",
                "X-Forwarded-For": "127.0.0.1",
                "X-Real-IP": "127.0.0.1",
            },
        )
        with urlopen(request, timeout=10) as response:
            if endpoint != "/" and json.load(response).get("status") != "ok":
                raise ValueError("The API health check did not pass.")
    print(
        f"Containers are healthy. Public address after the Nginx switch: {settings['SITE_URL']}"
    )


def restore(args):
    source = Path(args.directory).resolve()
    dump, media = source / "database.dump", source / "media.tar.gz"
    manifest = json.loads((source / "checksums.json").read_text())
    for path in (dump, media):
        if checksum(path) != manifest.get(path.name):
            raise ValueError(f"Backup checksum mismatch: {path.name}")
    validate_archive(media)
    with dump.open("rb") as handle:
        compose(
            "exec",
            "-T",
            "database",
            "pg_restore",
            "--list",
            stdin=handle,
            stdout=subprocess.DEVNULL,
        )
    print(
        "This will replace this Docker installation's database and all uploaded files."
    )
    if input("Type RESTORE to continue: ") != "RESTORE":
        raise ValueError("Cancelled; data was not changed.")
    backup(resume=False)
    compose("stop", *APPS)
    with dump.open("rb") as handle:
        database_command(
            "pg_restore -h 127.0.0.1 -U braindock -d braindock --no-owner --no-privileges --clean --if-exists --single-transaction --exit-on-error",
            stdin=handle,
        )
    with media.open("rb") as handle:
        media_command("unpack", stdin=handle)
    # Redis is private to this installation. Tasks/caches from the newer
    # database must not run against restored IDs; periodic jobs rebuild them.
    compose(
        "exec",
        "-T",
        "redis",
        "sh",
        "-ec",
        'export REDISCLI_AUTH="$(cat /run/secrets/redis_password)"; exec redis-cli FLUSHDB',
    )
    compose(
        "run",
        "--rm",
        "--no-deps",
        "-T",
        "--entrypoint",
        "python",
        "beat",
        "-c",
        "from pathlib import Path; "
        "[p.unlink() for p in Path('/var/lib/braindock').glob('celerybeat-schedule*') "
        "if p.is_file()]",
    )
    print(
        "Restored. Services remain stopped; run ./dock up to migrate and verify before reopening."
    )


def bundle():
    """Package this laptop's source, including uncommitted edits, without secrets."""
    files = (
        run(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            cwd=ROOT,
            capture_output=True,
        )
        .stdout.decode()
        .split("\0")
    )
    target = ROOT / "releases"
    target.mkdir(mode=0o700, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive_path = target / f"braindock-{stamp}.tar.gz"
    with tarfile.open(archive_path, "x:gz") as archive:
        for name in sorted(set(files)):
            path = ROOT / name
            relative = Path(name)
            private = (
                any(
                    part
                    in {
                        ".secrets",
                        ".git",
                        "backups",
                        "releases",
                        "node_modules",
                        ".venv",
                    }
                    for part in relative.parts
                )
                or (
                    relative.name.startswith(".env") and relative.name != ".env.example"
                )
                or relative.parts[:2]
                in (("backend", "media"), ("backend", "staticfiles"))
            )
            if name and not private and path.is_file() and not path.is_symlink():
                info = archive.gettarinfo(path, arcname=f"BrainDock/{name}")
                if name == "dock" or path.suffix == ".sh":
                    # A Windows checkout has no executable bit and may have
                    # CRLF endings. The release must run on a Linux server.
                    content = path.read_bytes().replace(b"\r\n", b"\n")
                    info.mode = 0o755
                    info.size = len(content)
                    archive.addfile(info, io.BytesIO(content))
                else:
                    with path.open("rb") as source:
                        archive.addfile(info, source)
    print(f"Source package (no live data or credentials): {archive_path}")


def main():
    parser = argparse.ArgumentParser(description="BrainDock Docker operations")
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser(
        "setup", help="generate configuration and secrets exactly once"
    )
    init.add_argument("--domain", required=True, type=domain_name)
    init.add_argument("--port", type=int, default=8088)
    for name in (
        "up",
        "down",
        "status",
        "backup",
        "owner",
        "health",
        "nginx",
        "bundle",
    ):
        commands.add_parser(name)
    restore_parser = commands.add_parser("restore")
    restore_parser.add_argument("directory")
    logs = commands.add_parser("logs")
    logs.add_argument("services", nargs="*")
    manage = commands.add_parser("manage")
    manage.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    os.umask(0o077)
    if args.command == "bundle":
        bundle()
        return
    if os.name != "posix":
        raise ValueError(
            "Deployment commands require Linux. On Windows, use "
            "python deploy/docker.py bundle and upload the package to the server."
        )
    if args.command == "setup":
        setup(args)
        return
    config()
    if args.command == "nginx":
        nginx_config()
        return
    compose("version", stdout=subprocess.DEVNULL)
    # Serialize writes so a scheduled backup cannot overlap a deploy/restore.
    lock = None
    if args.command not in ("status", "logs", "health"):
        import fcntl

        lock = (ROOT / ".dock.lock").open("a")
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError(
                "Another deployment/backup is running. Try again when it finishes."
            ) from None
    if args.command == "up":
        up()
    elif args.command == "down":
        # Deliberately no -v: databases, uploads and certificates are not disposable.
        compose("down", "--remove-orphans")
    elif args.command == "status":
        compose("ps", "--all")
    elif args.command == "logs":
        compose("logs", "--tail", "100", "--follow", *args.services)
    elif args.command == "backup":
        backup()
    elif args.command == "restore":
        restore(args)
    elif args.command == "health":
        health()
    elif args.command == "owner":
        compose("exec", "backend", "python", "manage.py", "createsuperuser")
    elif args.command == "manage":
        compose(
            "exec",
            *([] if sys.stdin.isatty() else ["-T"]),
            "backend",
            "python",
            "manage.py",
            *args.arguments,
        )


if __name__ == "__main__":
    try:
        main()
    except (
        ValueError,
        argparse.ArgumentTypeError,
        OSError,
        subprocess.CalledProcessError,
        tarfile.TarError,
    ) as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
    except (KeyboardInterrupt, EOFError):
        print("Cancelled. Run ./dock status to inspect services.", file=sys.stderr)
        sys.exit(130)
