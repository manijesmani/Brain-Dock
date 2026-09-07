"""Builders for real media files used by the attachment tests.

Generating genuine bytes rather than stubbing the inspectors means the tests
exercise Pillow and ffprobe exactly as production does.
"""

import shutil
import subprocess
import tempfile
from io import BytesIO
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image


def image_bytes(
    *,
    size: tuple[int, int] = (1200, 900),
    image_format: str = "JPEG",
    exif: bytes | None = None,
) -> bytes:
    image = Image.new("RGB", size, color=(16, 185, 129))
    buffer = BytesIO()
    if exif is not None:
        image.save(buffer, format=image_format, exif=exif)
    else:
        image.save(buffer, format=image_format)
    return buffer.getvalue()


def image_upload(
    name: str = "photo.jpg",
    *,
    size: tuple[int, int] = (1200, 900),
    image_format: str = "JPEG",
    exif: bytes | None = None,
    content_type: str = "image/jpeg",
) -> SimpleUploadedFile:
    return SimpleUploadedFile(
        name,
        image_bytes(size=size, image_format=image_format, exif=exif),
        content_type=content_type,
    )


def exif_with_gps() -> bytes:
    """An EXIF block carrying GPS coordinates, to prove they are removed."""
    exif = Image.Exif()
    exif[0x8769] = {}
    # GPSInfo IFD: latitude reference and value.
    exif[0x8825] = {1: "N", 2: (35.0, 41.0, 0.0), 3: "E", 4: (51.0, 25.0, 0.0)}
    return exif.tobytes()


def has_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def audio_bytes(*, seconds: float = 1.5, codec: str = "libmp3lame", suffix: str = ".mp3") -> bytes:
    """Renders a short tone with ffmpeg."""
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / f"tone{suffix}"
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-f",
                "lavfi",
                "-i",
                f"sine=frequency=440:duration={seconds}",
                "-c:a",
                codec,
                str(output),
            ],
            check=True,
            capture_output=True,
            timeout=60,
        )
        return output.read_bytes()


def audio_upload(
    name: str = "voice.mp3",
    *,
    seconds: float = 1.5,
    codec: str = "libmp3lame",
    suffix: str = ".mp3",
    content_type: str = "audio/mpeg",
) -> SimpleUploadedFile:
    return SimpleUploadedFile(
        name,
        audio_bytes(seconds=seconds, codec=codec, suffix=suffix),
        content_type=content_type,
    )


def video_bytes() -> bytes:
    """A real video file, used to prove the audio endpoint rejects video."""
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "clip.mp4"
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-f",
                "lavfi",
                "-i",
                "testsrc=size=64x64:duration=1",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=440:duration=1",
                "-c:v",
                "libx264",
                "-c:a",
                "aac",
                "-pix_fmt",
                "yuv420p",
                str(output),
            ],
            check=True,
            capture_output=True,
            timeout=60,
        )
        return output.read_bytes()
