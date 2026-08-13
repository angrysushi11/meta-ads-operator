from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from .errors import ValidationError


TOKEN_PATTERNS = (
    re.compile(r"(?i)(access[_-]?token|app[_-]?secret|client[_-]?secret)(\s*[=:]\s*)[^\s,;]+"),
    re.compile(r"\bEA[A-Za-z0-9]{40,}\b"),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def stable_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: str | Path) -> dict[str, Any]:
    source = Path(path).expanduser().resolve()
    try:
        value = json.loads(source.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValidationError(f"JSON file not found: {source}") from exc
    except json.JSONDecodeError as exc:
        raise ValidationError(f"Invalid JSON in {source}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValidationError(f"Expected a JSON object in {source}")
    value["_source_path"] = str(source)
    return value


def write_json_atomic(path: str | Path, value: Any) -> Path:
    target = Path(path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, target)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    return target


def redact_text(value: str) -> str:
    redacted = value
    for pattern in TOKEN_PATTERNS:
        if pattern.groups >= 2:
            redacted = pattern.sub(r"\1\2[REDACTED]", redacted)
        else:
            redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


def sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, child in value.items():
            if any(part in key.lower() for part in ("token", "secret", "authorization")):
                cleaned[key] = "[REDACTED]"
            else:
                cleaned[key] = sanitize(child)
        return cleaned
    if isinstance(value, list):
        return [sanitize(child) for child in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


def normalize_meta_id(value: Any, *, field: str) -> str:
    text = str(value or "").strip()
    if text.startswith("act_"):
        text = text[4:]
    if not text.isdigit() or len(text) < 5:
        raise ValidationError(f"{field} must be a numeric Meta ID")
    return text


def money_minor(value: Any, *, field: str) -> int:
    if isinstance(value, bool):
        raise ValidationError(f"{field} must be an integer in minor currency units")
    try:
        result = int(str(value))
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"{field} must be an integer in minor currency units") from exc
    if result < 0:
        raise ValidationError(f"{field} cannot be negative")
    return result


def decimal_or_unavailable(value: Any) -> Decimal | None:
    if value in (None, "", "UNAVAILABLE", "Not available"):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def assert_within(path: Path, roots: tuple[Path, ...], *, field: str) -> None:
    resolved = path.expanduser().resolve()
    for root in roots:
        try:
            resolved.relative_to(root)
            return
        except ValueError:
            continue
    raise ValidationError(f"{field} is outside the explicitly allowed roots: {resolved}")
