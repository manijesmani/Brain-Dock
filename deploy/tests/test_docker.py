"""Deployment safety checks that need no Docker daemon."""

import argparse
import importlib.util
import io
import json
import os
import stat
import tarfile
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


ROOT = Path(__file__).resolve().parents[2]
ops = module("docker_ops", ROOT / "deploy/docker.py")
media = module("media_archive", ROOT / "backend/container/media_archive.py")


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "deploy").mkdir()
        (self.root / "deploy/docker-nginx.conf.template").write_text(
            (ROOT / "deploy/docker-nginx.conf.template").read_text()
        )
        for name, value in (("ROOT", self.root), ("SECRETS", self.root / ".secrets")):
            mock = patch.object(ops, name, value)
            mock.start()
            self.addCleanup(mock.stop)
        ops.setup(argparse.Namespace(domain="braindock.test", port=8088))

    def test_setup_is_private_and_never_rotates_existing_credentials(self):
        key = (ops.SECRETS / "django_secret_key").read_bytes()
        self.assertGreater(len(key), 50)
        self.assertNotEqual(
            (ops.SECRETS / "db_app_password").read_bytes(),
            (ops.SECRETS / "postgres_admin_password").read_bytes(),
        )
        with self.assertRaises(ValueError):
            ops.setup(argparse.Namespace(domain="different.test", port=9000))
        self.assertEqual(key, (ops.SECRETS / "django_secret_key").read_bytes())

    @unittest.skipUnless(os.name == "posix", "POSIX permissions require Linux")
    def test_setup_uses_private_posix_permissions(self):
        self.assertEqual(stat.S_IMODE(ops.SECRETS.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE((self.root / ".env").stat().st_mode), 0o600)

    def test_proxy_template_values_cannot_inject_nginx_directives(self):
        for domain in (
            "a.test;",
            "a.test:443",
            "https://a.test/path",
            "https://user@a.test",
        ):
            with (
                self.subTest(domain=domain),
                self.assertRaises(argparse.ArgumentTypeError),
            ):
                ops.domain_name(domain)
        path = self.root / ".env"
        path.write_text(
            path.read_text().replace(
                "DJANGO_ADMIN_URL_PATH=", "DJANGO_ADMIN_URL_PATH=../"
            )
        )
        with self.assertRaises(ValueError):
            ops.config()

    def test_failed_update_backup_restarts_previously_running_services(self):
        with (
            patch.object(ops, "running_apps", return_value=["backend", "worker"]),
            patch.object(ops, "compose") as compose,
            patch.object(ops, "database_command", side_effect=OSError("disk full")),
            self.assertRaises(OSError),
        ):
            ops.backup(resume=False)
        self.assertEqual(compose.call_args.args, ("start", "backend", "worker"))

    def test_corrupt_restore_is_rejected_before_stopping_any_service(self):
        source = self.root / "bad"
        source.mkdir()
        (source / "database.dump").write_bytes(b"corrupt")
        (source / "media.tar.gz").write_bytes(b"corrupt")
        (source / "checksums.json").write_text(json.dumps({"database.dump": "wrong"}))
        with patch.object(ops, "compose") as compose, self.assertRaises(ValueError):
            ops.restore(argparse.Namespace(directory=source))
        compose.assert_not_called()

    def test_source_package_excludes_credentials_even_if_tracked_by_mistake(self):
        (self.root / "example.py").write_text("print('source')")
        names = b"example.py\0.env\0.secrets/django_secret_key\0"
        with patch.object(ops, "run", return_value=SimpleNamespace(stdout=names)):
            ops.bundle()
        package = next((self.root / "releases").glob("*.tar.gz"))
        with tarfile.open(package) as archive:
            self.assertEqual(archive.getnames(), ["BrainDock/example.py"])

    def test_source_package_makes_windows_shell_scripts_linux_executable(self):
        script = b"#!/bin/sh\r\nset -eu\r\n"
        for name in ("dock", "deploy/start.sh"):
            (self.root / name).write_bytes(script)
            (self.root / name).chmod(0o644)
        names = b"dock\0deploy/start.sh\0"
        with patch.object(ops, "run", return_value=SimpleNamespace(stdout=names)):
            ops.bundle()
        package = next((self.root / "releases").glob("*.tar.gz"))
        with tarfile.open(package) as archive:
            for name in ("dock", "deploy/start.sh"):
                member = archive.getmember(f"BrainDock/{name}")
                self.assertEqual(member.mode, 0o755)
                self.assertEqual(
                    archive.extractfile(member).read(), script.replace(b"\r\n", b"\n")
                )


class MediaTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "old.txt").write_text("original")

    def test_round_trip_removes_files_added_after_backup(self):
        output = io.BytesIO()
        media.pack(self.root, output)
        (self.root / "old.txt").write_text("changed")
        (self.root / "extra.txt").write_text("new")
        output.seek(0)
        media.unpack(self.root, output)
        self.assertEqual((self.root / "old.txt").read_text(), "original")
        self.assertFalse((self.root / "extra.txt").exists())

    def test_unsafe_archives_preserve_current_media(self):
        for name, kind in (
            ("../escape", tarfile.REGTYPE),
            ("/absolute", tarfile.REGTYPE),
            ("link", tarfile.SYMTYPE),
            ("hardlink", tarfile.LNKTYPE),
        ):
            with self.subTest(name=name):
                output = io.BytesIO()
                with tarfile.open(fileobj=output, mode="w:gz") as archive:
                    entry = tarfile.TarInfo(name)
                    entry.type = kind
                    entry.linkname = "../outside"
                    archive.addfile(entry)
                output.seek(0)
                with self.assertRaises(ValueError):
                    media.unpack(self.root, output)
                self.assertEqual((self.root / "old.txt").read_text(), "original")
                self.assertEqual(len(list(self.root.iterdir())), 1)

    def test_truncated_gzip_preserves_current_media(self):
        output = io.BytesIO()
        media.pack(self.root, output)
        with self.assertRaises(EOFError):
            media.unpack(self.root, io.BytesIO(output.getvalue()[:-6]))
        self.assertEqual((self.root / "old.txt").read_text(), "original")


if __name__ == "__main__":
    unittest.main()
