from __future__ import annotations

import platform
import sys
from pathlib import Path
from typing import Any

from .policy import OperatorPolicy
from .secrets import token_available
from .util import utc_now


def run(policy_path: str | Path | None = None) -> dict[str, Any]:
    checks: dict[str, Any] = {
        "python": {
            "passed": sys.version_info >= (3, 11),
            "version": platform.python_version(),
        },
        "token": {
            "passed": token_available(),
            "detail": "available through environment or OS credential store"
            if token_available()
            else "not configured; live commands will remain blocked",
        },
    }
    if policy_path:
        try:
            policy = OperatorPolicy.load(policy_path)
            checks["policy"] = {
                "passed": True,
                "path": str(policy.source_path),
                "policy_sha256": policy.policy_hash,
                "approval_mode": policy.approval_mode,
                "allowed_actions": sorted(policy.allowed_actions),
            }
        except Exception as exc:
            checks["policy"] = {"passed": False, "error": str(exc)}
    return {
        "checked_at": utc_now(),
        "passed": all(value["passed"] for value in checks.values()),
        "checks": checks,
        "live_write": False,
    }

