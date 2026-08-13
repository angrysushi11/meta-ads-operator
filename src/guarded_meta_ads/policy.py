from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from .errors import PolicyError, ValidationError
from .util import assert_within, money_minor, normalize_meta_id, read_json, stable_hash


APPROVAL_MODES = {"supervised", "confirm_writes_only", "execute_within_policy"}
WRITE_ACTIONS = {
    "create_campaign",
    "create_ad_set",
    "create_ads",
    "set_status",
    "set_budget",
}
KNOWN_ACTIONS = WRITE_ACTIONS | {"read", "inventory", "validate", "insights", "evaluate_rule"}


def _ids(values: Any, field: str) -> frozenset[str]:
    if values is None:
        return frozenset()
    if not isinstance(values, list):
        raise ValidationError(f"{field} must be a list")
    return frozenset(normalize_meta_id(value, field=field) for value in values)


@dataclass(frozen=True)
class OperatorPolicy:
    raw: dict[str, Any]
    source_path: Path
    policy_hash: str
    graph_version: str
    approval_mode: str
    allowed_actions: frozenset[str]
    account_ids: frozenset[str]
    campaign_ids: frozenset[str]
    ad_set_ids: frozenset[str]
    ad_ids: frozenset[str]
    page_ids: frozenset[str]
    instagram_user_ids: frozenset[str]
    allowed_destination_hosts: frozenset[str]
    media_roots: tuple[Path, ...]
    max_ads_per_batch: int
    max_daily_budget_minor: int
    max_budget_increase_percent: float
    max_http_attempts_per_run: int
    stop_at_usage_percent: float
    currency_minor_exponent: int
    require_new_ads_paused: bool
    require_parent_paused_for_create: bool
    max_spend_today_minor_for_create: int | None
    receipt_dir: Path
    naming_patterns: dict[str, str]
    standing_actions: frozenset[str]
    standing_expires_at: str | None

    @classmethod
    def load(cls, path: str | Path) -> "OperatorPolicy":
        raw = read_json(path)
        source_path = Path(raw.pop("_source_path"))
        schema_version = raw.get("schema_version")
        if schema_version != 1:
            raise ValidationError("Policy schema_version must equal 1")
        approval = raw.get("approval", {})
        mode = str(approval.get("mode", "supervised"))
        if mode not in APPROVAL_MODES:
            raise ValidationError(f"Unknown approval mode: {mode}")
        allowed_actions = frozenset(str(value) for value in raw.get("allowed_actions", []))
        unknown = allowed_actions - KNOWN_ACTIONS
        if unknown:
            raise ValidationError(f"Unknown allowed_actions: {sorted(unknown)}")
        scope = raw.get("scope", {})
        limits = raw.get("limits", {})
        invariants = raw.get("invariants", {})
        destinations = frozenset(str(host).lower().strip(".") for host in scope.get("destination_hosts", []))
        media_roots = tuple(
            Path(value).expanduser().resolve() for value in scope.get("media_roots", [])
        )
        if "create_ads" in allowed_actions and not media_roots:
            raise ValidationError("A policy that permits create_ads must set scope.media_roots")
        receipt_dir_value = raw.get("receipt_dir", "receipts")
        receipt_dir = Path(receipt_dir_value).expanduser()
        if not receipt_dir.is_absolute():
            receipt_dir = (source_path.parent / receipt_dir).resolve()
        standing = approval.get("standing_authority", {})
        standing_actions = frozenset(str(value) for value in standing.get("actions", []))
        if standing_actions - WRITE_ACTIONS:
            raise ValidationError("standing_authority.actions may contain write actions only")
        result = cls(
            raw=raw,
            source_path=source_path,
            policy_hash=stable_hash(raw),
            graph_version=str(raw.get("graph_version", "v25.0")),
            approval_mode=mode,
            allowed_actions=allowed_actions,
            account_ids=_ids(scope.get("ad_account_ids"), "scope.ad_account_ids"),
            campaign_ids=_ids(scope.get("campaign_ids"), "scope.campaign_ids"),
            ad_set_ids=_ids(scope.get("ad_set_ids"), "scope.ad_set_ids"),
            ad_ids=_ids(scope.get("ad_ids"), "scope.ad_ids"),
            page_ids=_ids(scope.get("page_ids"), "scope.page_ids"),
            instagram_user_ids=_ids(scope.get("instagram_user_ids"), "scope.instagram_user_ids"),
            allowed_destination_hosts=destinations,
            media_roots=media_roots,
            max_ads_per_batch=money_minor(limits.get("max_ads_per_batch", 1), field="max_ads_per_batch"),
            max_daily_budget_minor=money_minor(
                limits.get("max_daily_budget_minor", 0), field="max_daily_budget_minor"
            ),
            max_budget_increase_percent=float(limits.get("max_budget_increase_percent", 0)),
            max_http_attempts_per_run=money_minor(
                limits.get("max_http_attempts_per_run", 100),
                field="max_http_attempts_per_run",
            ),
            stop_at_usage_percent=float(limits.get("stop_at_usage_percent", 80)),
            currency_minor_exponent=int(limits.get("currency_minor_exponent", 2)),
            require_new_ads_paused=bool(invariants.get("new_ads_must_start_paused", True)),
            require_parent_paused_for_create=bool(
                invariants.get("parents_must_be_paused_for_create", True)
            ),
            max_spend_today_minor_for_create=(
                money_minor(invariants["max_spend_today_minor_for_create"], field="max_spend_today_minor_for_create")
                if "max_spend_today_minor_for_create" in invariants
                else None
            ),
            receipt_dir=receipt_dir,
            naming_patterns={str(key): str(value) for key, value in raw.get("naming_patterns", {}).items()},
            standing_actions=standing_actions,
            standing_expires_at=standing.get("expires_at"),
        )
        if result.max_http_attempts_per_run < 1:
            raise ValidationError("max_http_attempts_per_run must be at least 1")
        if not 1 <= result.stop_at_usage_percent <= 100:
            raise ValidationError("stop_at_usage_percent must be between 1 and 100")
        return result

    def assert_action(self, action: str) -> None:
        if action not in self.allowed_actions:
            raise PolicyError(f"Action {action!r} is not allowed by this policy")

    def assert_account(self, account_id: Any) -> str:
        value = normalize_meta_id(account_id, field="ad_account_id")
        if value not in self.account_ids:
            raise PolicyError(f"Ad account {value} is outside the allowed policy scope")
        return value

    def assert_existing_id(self, kind: str, value: Any) -> str:
        normalized = normalize_meta_id(value, field=f"{kind}_id")
        allowed = {
            "campaign": self.campaign_ids,
            "ad_set": self.ad_set_ids,
            "ad": self.ad_ids,
            "page": self.page_ids,
            "instagram": self.instagram_user_ids,
        }[kind]
        if normalized not in allowed:
            raise PolicyError(f"{kind} {normalized} is outside the allowed policy scope")
        return normalized

    def assert_destination(self, url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ValidationError(f"Destination must be an absolute HTTPS URL: {url}")
        if parsed.hostname.lower().strip(".") not in self.allowed_destination_hosts:
            raise PolicyError(f"Destination host is outside the allowed policy scope: {parsed.hostname}")

    def assert_media_path(self, path: Path) -> None:
        assert_within(path, self.media_roots, field="media_path")

    def assert_batch_count(self, count: int) -> None:
        if count < 1 or count > self.max_ads_per_batch:
            raise PolicyError(
                f"Requested {count} ads; policy maximum is {self.max_ads_per_batch}"
            )

    def assert_budget(self, new_minor: int, current_minor: int | None = None) -> None:
        if new_minor > self.max_daily_budget_minor:
            raise PolicyError(
                f"Requested daily budget {new_minor} exceeds policy cap {self.max_daily_budget_minor}"
            )
        if current_minor is not None and new_minor > current_minor:
            increase = ((new_minor - current_minor) / current_minor * 100) if current_minor else 100.0
            if increase > self.max_budget_increase_percent:
                raise PolicyError(
                    f"Budget increase {increase:.2f}% exceeds policy cap "
                    f"{self.max_budget_increase_percent:.2f}%"
                )

    def assert_name(self, kind: str, name: str) -> None:
        pattern = self.naming_patterns.get(kind)
        if pattern and not re.fullmatch(pattern, name):
            raise PolicyError(f"{kind} name does not match the configured naming pattern")

    def standing_authority_allows(self, action: str) -> bool:
        if self.approval_mode != "execute_within_policy" or action not in self.standing_actions:
            return False
        if not self.standing_expires_at:
            return False
        try:
            expires = datetime.fromisoformat(self.standing_expires_at.replace("Z", "+00:00"))
        except ValueError:
            return False
        return expires > datetime.now(timezone.utc)
