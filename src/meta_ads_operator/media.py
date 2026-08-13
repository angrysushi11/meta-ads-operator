from __future__ import annotations

import mimetypes
import struct
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .util import sha256_file


SUPPORTED_SUFFIXES = {".png", ".jpg", ".jpeg", ".mp4", ".mov"}


def _png_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as handle:
        header = handle.read(24)
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise ValidationError(f"Invalid PNG header: {path}")
    return struct.unpack(">II", header[16:24])


def _jpeg_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as handle:
        if handle.read(2) != b"\xff\xd8":
            raise ValidationError(f"Invalid JPEG header: {path}")
        while True:
            marker_start = handle.read(1)
            if not marker_start:
                break
            if marker_start != b"\xff":
                continue
            marker = handle.read(1)
            while marker == b"\xff":
                marker = handle.read(1)
            if not marker or marker in {b"\xd8", b"\xd9"}:
                continue
            length_raw = handle.read(2)
            if len(length_raw) != 2:
                break
            length = struct.unpack(">H", length_raw)[0]
            if length < 2:
                break
            if marker[0] in {
                0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF,
            }:
                payload = handle.read(5)
                if len(payload) != 5:
                    break
                height, width = struct.unpack(">HH", payload[1:5])
                return width, height
            handle.seek(length - 2, 1)
    raise ValidationError(f"Could not read JPEG dimensions: {path}")


def image_dimensions(path: Path) -> tuple[int, int] | None:
    suffix = path.suffix.lower()
    if suffix == ".png":
        return _png_dimensions(path)
    if suffix in {".jpg", ".jpeg"}:
        return _jpeg_dimensions(path)
    return None


def inspect_media(path: str | Path, *, relative_to: Path | None = None) -> dict[str, Any]:
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise ValidationError(f"Media file not found: {source}")
    if source.suffix.lower() not in SUPPORTED_SUFFIXES:
        raise ValidationError(f"Unsupported media type: {source.suffix}")
    dimensions = image_dimensions(source)
    display_path = str(source)
    if relative_to:
        try:
            display_path = str(source.relative_to(relative_to.resolve()))
        except ValueError:
            pass
    result: dict[str, Any] = {
        "path": display_path,
        "sha256": sha256_file(source),
        "bytes": source.stat().st_size,
        "mime_type": mimetypes.guess_type(source.name)[0] or "application/octet-stream",
        "kind": "video" if source.suffix.lower() in {".mp4", ".mov"} else "image",
    }
    if dimensions:
        width, height = dimensions
        result.update(
            {
                "width": width,
                "height": height,
                "aspect_ratio": round(width / height, 6) if height else None,
            }
        )
    return result


def inventory(folder: str | Path) -> list[dict[str, Any]]:
    root = Path(folder).expanduser().resolve()
    if not root.is_dir():
        raise ValidationError(f"Creative folder not found: {root}")
    rows: list[dict[str, Any]] = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        if path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        rows.append(inspect_media(path, relative_to=root))
    return rows

