"""Stream private media backups and replace files only after full validation."""

import argparse
import gzip
import shutil
import sys
import tarfile
import tempfile
from pathlib import Path, PurePosixPath


def pack(root, output):
    with tarfile.open(fileobj=output, mode="w|gz") as archive:
        archive.add(root, arcname=".")


def unpack(root, source):
    # Staging is on the media volume, not the small in-memory /tmp mount.
    with tempfile.TemporaryDirectory(prefix=".restore-", dir=root) as temporary:
        staging = Path(temporary)
        backup = staging / "archive.tar.gz"
        with backup.open("wb") as output:
            shutil.copyfileobj(source, output)
        fresh = staging / "new"
        fresh.mkdir()
        with gzip.open(backup, "rb") as compressed:
            while compressed.read(1024 * 1024):
                pass
        with tarfile.open(backup, "r:gz") as archive:
            for member in archive.getmembers():
                path = PurePosixPath(member.name)
                if (
                    path.is_absolute()
                    or ".." in path.parts
                    or not (member.isfile() or member.isdir())
                ):
                    raise ValueError("Unsafe file in media archive")
            archive.extractall(fresh, filter="data")

        previous = staging / "previous"
        previous.mkdir()
        moved = []
        try:
            for entry in root.iterdir():
                if entry != staging:
                    entry.rename(previous / entry.name)
            for entry in fresh.iterdir():
                destination = root / entry.name
                entry.rename(destination)
                moved.append(destination)
        except Exception:
            for entry in moved:
                entry.rename(fresh / entry.name)
            for entry in previous.iterdir():
                entry.rename(root / entry.name)
            raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["pack", "unpack"])
    args = parser.parse_args()
    media = Path("/app/media")
    if args.action == "pack":
        pack(media, sys.stdout.buffer)
    else:
        unpack(media, sys.stdin.buffer)
