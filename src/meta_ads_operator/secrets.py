from __future__ import annotations

import getpass
import os
import subprocess
import sys

from .errors import ValidationError


ENV_NAME = "META_ADS_OPERATOR_ACCESS_TOKEN"
KEYRING_SERVICE = "meta-ads-operator"
KEYRING_ACCOUNT = "meta-access-token"


def load_access_token() -> str:
    value = os.environ.get(ENV_NAME, "").strip()
    if value:
        return value
    if sys.platform == "darwin":
        result = subprocess.run(
            [
                "/usr/bin/security",
                "find-generic-password",
                "-s",
                KEYRING_SERVICE,
                "-a",
                KEYRING_ACCOUNT,
                "-w",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    raise ValidationError(
        f"No Meta token available. Set {ENV_NAME} only for the current process, "
        "or run `meta-ads auth-store` on macOS. Never paste a token into chat."
    )


def store_access_token() -> dict[str, str]:
    if sys.platform != "darwin":
        raise ValidationError(
            "Secure interactive storage is currently implemented for macOS Keychain. "
            f"On this platform, inject {ENV_NAME} from your own secret manager."
        )
    token = getpass.getpass("Meta access token (input is hidden): ").strip()
    if len(token) < 20:
        raise ValidationError("Token was empty or unexpectedly short")
    result = subprocess.run(
        [
            "/usr/bin/security",
            "add-generic-password",
            "-U",
            "-s",
            KEYRING_SERVICE,
            "-a",
            KEYRING_ACCOUNT,
            "-w",
            token,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    token = ""
    if result.returncode != 0:
        raise ValidationError("macOS Keychain rejected the token write")
    return {"stored": "yes", "service": KEYRING_SERVICE, "account": KEYRING_ACCOUNT}


def token_available() -> bool:
    if os.environ.get(ENV_NAME, "").strip():
        return True
    if sys.platform != "darwin":
        return False
    result = subprocess.run(
        [
            "/usr/bin/security",
            "find-generic-password",
            "-s",
            KEYRING_SERVICE,
            "-a",
            KEYRING_ACCOUNT,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0

