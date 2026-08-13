from __future__ import annotations

import copy
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl

from .errors import ValidationError
from .media import inspect_media
from .policy import OperatorPolicy
from .util import normalize_meta_id, read_json, sha256_file, stable_hash, utc_now


ALLOWED_AD_STATUSES = {"PAUSED", "ACTIVE"}
ALLOWED_ENTITY_KINDS = {"campaign", "ad_set", "ad"}
SUPPORTED_CREATIVE_FORMATS = {
    "single_image",
    "carousel",
    "single_video",
    "dynamic_image",
    "flexible_image",
}


def _finalize(action: str, summary: str, policy: OperatorPolicy, body: dict[str, Any]) -> dict[str, Any]:
    plan = {
        "schema_version": 1,
        "created_at": utc_now(),
        "action": action,
        "write": action in {"create_campaign", "create_ad_set", "create_ads", "set_status", "set_budget"},
        "approval_mode": policy.approval_mode,
        "policy_sha256": policy.policy_hash,
        "summary": summary,
        **body,
    }
    plan["plan_sha256"] = stable_hash(plan)
    return plan


def verify_plan(plan: dict[str, Any], policy: OperatorPolicy) -> None:
    supplied_hash = str(plan.get("plan_sha256", ""))
    unsigned = copy.deepcopy(plan)
    unsigned.pop("plan_sha256", None)
    actual_hash = stable_hash(unsigned)
    if supplied_hash != actual_hash:
        raise ValidationError("Plan hash mismatch; regenerate the plan")
    if plan.get("policy_sha256") != policy.policy_hash:
        raise ValidationError("Plan was created under a different policy; regenerate it")
    policy.assert_action(str(plan.get("action")))


def _read_spec(path: str | Path) -> tuple[dict[str, Any], Path, str]:
    spec = read_json(path)
    source = Path(spec.pop("_source_path"))
    return spec, source, sha256_file(source)


def _required_text(mapping: dict[str, Any], key: str, *, prefix: str = "") -> str:
    value = str(mapping.get(key, "")).strip()
    if not value:
        raise ValidationError(f"Missing required field: {prefix}{key}")
    return value


def _freeze_media(
    raw: dict[str, Any],
    *,
    source: Path,
    policy: OperatorPolicy,
    prefix: str,
) -> tuple[dict[str, Any], str]:
    media_value = _required_text(raw, "media_path", prefix=prefix)
    media_path = Path(media_value).expanduser()
    if not media_path.is_absolute():
        media_path = (source.parent / media_path).resolve()
    policy.assert_media_path(media_path)
    media = inspect_media(media_path, relative_to=source.parent)
    expected_sha = str(raw.get("media_sha256", "")).strip()
    if expected_sha and expected_sha != media["sha256"]:
        raise ValidationError(f"Media SHA-256 mismatch for {prefix.rstrip('.')}")
    frozen = {
        "media_path": media["path"],
        "media_sha256": media["sha256"],
        "media_kind": media["kind"],
        "media_bytes": media["bytes"],
        "width": media.get("width"),
        "height": media.get("height"),
    }
    return frozen, str(media_path)


def build_create_ads_plan(manifest_path: str | Path, policy: OperatorPolicy) -> dict[str, Any]:
    policy.assert_action("create_ads")
    manifest, source, manifest_sha = _read_spec(manifest_path)
    if manifest.get("schema_version") != 1:
        raise ValidationError("Manifest schema_version must equal 1")
    account_id = policy.assert_account(manifest.get("ad_account_id"))
    campaign_id = policy.assert_existing_id("campaign", manifest.get("campaign_id"))
    ad_set_id = policy.assert_existing_id("ad_set", manifest.get("ad_set_id"))
    identity = manifest.get("identity", {})
    page_id = policy.assert_existing_id("page", identity.get("page_id"))
    instagram_user_id = None
    if identity.get("instagram_user_id"):
        instagram_user_id = policy.assert_existing_id(
            "instagram", identity.get("instagram_user_id")
        )
    ads = manifest.get("ads")
    if not isinstance(ads, list):
        raise ValidationError("Manifest ads must be a list")
    policy.assert_batch_count(len(ads))
    frozen_ads: list[dict[str, Any]] = []
    local_media_paths: dict[str, str] = {}
    seen_names: set[str] = set()
    for index, raw in enumerate(ads, start=1):
        if not isinstance(raw, dict):
            raise ValidationError(f"ads[{index}] must be an object")
        name = _required_text(raw, "name", prefix=f"ads[{index}].")
        if name in seen_names:
            raise ValidationError(f"Duplicate ad name in manifest: {name}")
        seen_names.add(name)
        policy.assert_name("ad", name)
        creative_name = str(raw.get("creative_name") or f"{name}_creative").strip()
        creative_format = str(raw.get("format", "single_image")).strip().lower()
        if creative_format not in SUPPORTED_CREATIVE_FORMATS:
            raise ValidationError(
                f"Unsupported creative format for {name}: {creative_format}. "
                f"Supported: {sorted(SUPPORTED_CREATIVE_FORMATS)}"
            )
        destination = _required_text(raw, "destination_url", prefix=f"ads[{index}].")
        policy.assert_destination(destination)
        status = str(raw.get("status", "PAUSED")).upper()
        if status not in ALLOWED_AD_STATUSES:
            raise ValidationError(f"Unsupported initial ad status for {name}: {status}")
        if policy.require_new_ads_paused and status != "PAUSED":
            raise ValidationError(f"Policy requires new ads to start PAUSED: {name}")
        url_tags = str(raw.get("url_tags", "")).strip().lstrip("?")
        if url_tags:
            pairs = parse_qsl(url_tags, keep_blank_values=True)
            if not pairs:
                raise ValidationError(f"Invalid url_tags for {name}")
        primary_text = _required_text(raw, "primary_text", prefix=f"ads[{index}].")
        headline = _required_text(raw, "headline", prefix=f"ads[{index}].")
        description = str(raw.get("description", ""))
        cta = str(raw.get("cta", "LEARN_MORE")).upper()
        local_paths: list[str] = []
        media_assets: list[dict[str, Any]] = []
        cards: list[dict[str, Any]] = []

        if creative_format == "carousel":
            raw_cards = raw.get("cards")
            if not isinstance(raw_cards, list) or not 2 <= len(raw_cards) <= 10:
                raise ValidationError(f"Carousel {name} requires 2–10 cards")
            for card_index, card_raw in enumerate(raw_cards, start=1):
                if not isinstance(card_raw, dict):
                    raise ValidationError(f"ads[{index}].cards[{card_index}] must be an object")
                frozen_media, absolute_path = _freeze_media(
                    card_raw,
                    source=source,
                    policy=policy,
                    prefix=f"ads[{index}].cards[{card_index}].",
                )
                if frozen_media["media_kind"] != "image":
                    raise ValidationError(f"Carousel cards must be images: {name}")
                card_destination = str(card_raw.get("destination_url") or destination).strip()
                policy.assert_destination(card_destination)
                media_assets.append(frozen_media)
                local_paths.append(absolute_path)
                cards.append(
                    {
                        **frozen_media,
                        "headline": _required_text(
                            card_raw, "headline", prefix=f"ads[{index}].cards[{card_index}]."
                        ),
                        "description": str(card_raw.get("description", "")),
                        "destination_url": card_destination,
                        "cta": str(card_raw.get("cta", cta)).upper(),
                    }
                )
        elif creative_format in {"dynamic_image", "flexible_image"}:
            raw_media = raw.get("media")
            if not isinstance(raw_media, list) or not 2 <= len(raw_media) <= 10:
                raise ValidationError(f"{creative_format} {name} requires 2–10 image assets")
            for media_index, media_raw in enumerate(raw_media, start=1):
                if not isinstance(media_raw, dict):
                    raise ValidationError(f"ads[{index}].media[{media_index}] must be an object")
                frozen_media, absolute_path = _freeze_media(
                    media_raw,
                    source=source,
                    policy=policy,
                    prefix=f"ads[{index}].media[{media_index}].",
                )
                if frozen_media["media_kind"] != "image":
                    raise ValidationError(f"{creative_format} assets must be images: {name}")
                media_assets.append(frozen_media)
                local_paths.append(absolute_path)
        else:
            frozen_media, absolute_path = _freeze_media(
                raw,
                source=source,
                policy=policy,
                prefix=f"ads[{index}].",
            )
            expected_kind = "video" if creative_format == "single_video" else "image"
            if frozen_media["media_kind"] != expected_kind:
                raise ValidationError(f"{creative_format} requires {expected_kind} media: {name}")
            media_assets.append(frozen_media)
            local_paths.append(absolute_path)

        bodies = raw.get("bodies", [primary_text])
        headlines = raw.get("headlines", [headline])
        descriptions = raw.get("descriptions", [description] if description else [])
        if creative_format in {"dynamic_image", "flexible_image"}:
            if not isinstance(bodies, list) or not bodies or not all(str(value).strip() for value in bodies):
                raise ValidationError(f"{creative_format} {name} requires non-empty bodies")
            if not isinstance(headlines, list) or not headlines or not all(str(value).strip() for value in headlines):
                raise ValidationError(f"{creative_format} {name} requires non-empty headlines")
            if not isinstance(descriptions, list):
                raise ValidationError(f"{creative_format} descriptions must be a list: {name}")

        first_media = media_assets[0]
        frozen_ads.append(
            {
                "name": name,
                "creative_name": creative_name,
                "format": creative_format,
                "media_path": first_media["media_path"],
                "media_sha256": first_media["media_sha256"],
                "media_kind": first_media["media_kind"],
                "media_bytes": first_media["media_bytes"],
                "width": first_media.get("width"),
                "height": first_media.get("height"),
                "media_assets": media_assets,
                "cards": cards,
                "primary_text": primary_text,
                "headline": headline,
                "description": description,
                "bodies": [str(value).strip() for value in bodies],
                "headlines": [str(value).strip() for value in headlines],
                "descriptions": [str(value).strip() for value in descriptions],
                "cta": cta,
                "destination_url": destination,
                "url_tags": url_tags,
                "status": status,
                "creative_features": raw.get("creative_features", "OPT_OUT"),
            }
        )
        local_media_paths[name] = local_paths
    return _finalize(
        "create_ads",
        f"Create {len(frozen_ads)} fresh ads under campaign {campaign_id} / ad set {ad_set_id}; "
        f"initial status {sorted({row['status'] for row in frozen_ads})}.",
        policy,
        {
            "manifest_sha256": manifest_sha,
            "account_id": account_id,
            "campaign_id": campaign_id,
            "ad_set_id": ad_set_id,
            "identity": {"page_id": page_id, "instagram_user_id": instagram_user_id},
            "ads": frozen_ads,
            "guards": {
                "exact_name_idempotency": True,
                "sequential_creation": True,
                "verify_after_each_write": True,
                "parents_must_be_paused": policy.require_parent_paused_for_create,
                "max_spend_today_minor": policy.max_spend_today_minor_for_create,
                "custom_display_link_omitted": True,
            },
            "_local": {"manifest_path": str(source), "media_paths": local_media_paths},
        },
    )


def build_create_campaign_plan(spec_path: str | Path, policy: OperatorPolicy) -> dict[str, Any]:
    policy.assert_action("create_campaign")
    spec, source, source_sha = _read_spec(spec_path)
    account_id = policy.assert_account(spec.get("ad_account_id"))
    name = _required_text(spec, "name")
    policy.assert_name("campaign", name)
    status = str(spec.get("status", "PAUSED")).upper()
    if status != "PAUSED":
        raise ValidationError("New campaigns must start PAUSED")
    payload: dict[str, Any] = {
        "name": name,
        "objective": _required_text(spec, "objective"),
        "status": status,
        "special_ad_categories": spec.get("special_ad_categories", []),
    }
    if "daily_budget_minor" in spec:
        budget = int(spec["daily_budget_minor"])
        policy.assert_budget(budget)
        payload["daily_budget"] = budget
    if spec.get("buying_type"):
        payload["buying_type"] = spec["buying_type"]
    return _finalize(
        "create_campaign",
        f"Create campaign {name!r} as PAUSED in ad account {account_id}.",
        policy,
        {
            "source_sha256": source_sha,
            "account_id": account_id,
            "payload": payload,
            "_local": {"spec_path": str(source)},
        },
    )


def build_create_ad_set_plan(spec_path: str | Path, policy: OperatorPolicy) -> dict[str, Any]:
    policy.assert_action("create_ad_set")
    spec, source, source_sha = _read_spec(spec_path)
    account_id = policy.assert_account(spec.get("ad_account_id"))
    campaign_id = policy.assert_existing_id("campaign", spec.get("campaign_id"))
    name = _required_text(spec, "name")
    policy.assert_name("ad_set", name)
    status = str(spec.get("status", "PAUSED")).upper()
    if status != "PAUSED":
        raise ValidationError("New ad sets must start PAUSED")
    payload: dict[str, Any] = {
        "name": name,
        "campaign_id": campaign_id,
        "billing_event": _required_text(spec, "billing_event"),
        "optimization_goal": _required_text(spec, "optimization_goal"),
        "targeting": spec.get("targeting"),
        "status": status,
    }
    if not isinstance(payload["targeting"], dict):
        raise ValidationError("Ad-set targeting must be an object")
    for key in ("bid_strategy", "destination_type", "attribution_spec", "promoted_object"):
        if key in spec:
            payload[key] = spec[key]
    if "daily_budget_minor" in spec:
        budget = int(spec["daily_budget_minor"])
        policy.assert_budget(budget)
        payload["daily_budget"] = budget
    return _finalize(
        "create_ad_set",
        f"Create ad set {name!r} as PAUSED under campaign {campaign_id}.",
        policy,
        {
            "source_sha256": source_sha,
            "account_id": account_id,
            "campaign_id": campaign_id,
            "payload": payload,
            "_local": {"spec_path": str(source)},
        },
    )


def build_status_plan(
    *, kind: str, object_id: Any, status: str, policy: OperatorPolicy
) -> dict[str, Any]:
    policy.assert_action("set_status")
    if kind not in ALLOWED_ENTITY_KINDS:
        raise ValidationError(f"Unsupported object kind: {kind}")
    normalized = normalize_meta_id(object_id, field=f"{kind}_id")
    policy.assert_existing_id(kind, normalized)
    target = status.upper()
    if target not in ALLOWED_AD_STATUSES:
        raise ValidationError("Status must be PAUSED or ACTIVE")
    return _finalize(
        "set_status",
        f"Set {kind} {normalized} to {target}; no other object changes.",
        policy,
        {"kind": kind, "object_id": normalized, "target_status": target},
    )


def build_budget_plan(
    *, kind: str, object_id: Any, daily_budget_minor: int, policy: OperatorPolicy
) -> dict[str, Any]:
    policy.assert_action("set_budget")
    if kind not in {"campaign", "ad_set"}:
        raise ValidationError("Budgets can be changed only on campaign or ad_set")
    normalized = policy.assert_existing_id(kind, object_id)
    requested = int(daily_budget_minor)
    policy.assert_budget(requested)
    return _finalize(
        "set_budget",
        f"Set {kind} {normalized} daily budget to {requested} minor currency units, "
        "subject to fresh current-budget readback and policy caps.",
        policy,
        {"kind": kind, "object_id": normalized, "daily_budget_minor": requested},
    )
