from __future__ import annotations

import copy
import json
import time
from decimal import Decimal
from pathlib import Path
from typing import Any

from .errors import PolicyError, ReadbackError, ValidationError
from .graph import MetaGraphClient
from .planning import verify_plan
from .policy import OperatorPolicy
from .util import sanitize, sha256_file, stable_hash, utc_now, write_json_atomic


READ_FIELDS = {
    "campaign": "id,name,status,effective_status,daily_budget,lifetime_budget,budget_remaining,issues_info",
    "ad_set": "id,name,campaign_id,status,effective_status,daily_budget,lifetime_budget,optimization_goal,billing_event,targeting,issues_info",
    "ad": "id,name,adset_id,campaign_id,status,effective_status,creative,issues_info,ad_review_feedback",
}


def _receipt_plan(plan: dict[str, Any]) -> dict[str, Any]:
    clean = copy.deepcopy(plan)
    clean.pop("_local", None)
    for ad in clean.get("ads", []):
        ad.pop("media_path", None)
        for media in ad.get("media_assets", []):
            media.pop("media_path", None)
        for card in ad.get("cards", []):
            card.pop("media_path", None)
    return sanitize(clean)


def _receipt_path(policy: OperatorPolicy, plan: dict[str, Any]) -> Path:
    stamp = utc_now().replace(":", "").replace("-", "")
    return policy.receipt_dir / f"{stamp}_{plan['action']}_{plan['plan_sha256'][:12]}.json"


def _save(receipt_path: Path, receipt: dict[str, Any]) -> None:
    write_json_atomic(receipt_path, sanitize(receipt))


def _assert_approval(
    plan: dict[str, Any], policy: OperatorPolicy, *, confirmation: str | None, standing: bool
) -> None:
    if not plan.get("write"):
        return
    if confirmation == plan["plan_sha256"]:
        return
    if standing and policy.standing_authority_allows(plan["action"]):
        return
    raise PolicyError(
        "Write approval is missing. Re-read the plan and pass its exact plan_sha256 as "
        "--confirm, or use a currently valid execute-within-policy authority."
    )


def _account_preflight(client: MetaGraphClient, account_id: str) -> dict[str, Any]:
    account = client.get(
        f"act_{account_id}",
        params={
            "fields": "id,account_id,name,account_status,disable_reason,currency,timezone_name,business",
        },
    )
    if str(account.get("account_id")) != account_id:
        raise ReadbackError("Ad-account readback did not match the locked account")
    if int(account.get("account_status", 0) or 0) != 1:
        raise ReadbackError(
            f"Ad account is not active; account_status={account.get('account_status')}, "
            f"disable_reason={account.get('disable_reason')}"
        )
    return account


def _spend_today_minor(
    client: MetaGraphClient, campaign_id: str, policy: OperatorPolicy
) -> tuple[int | None, dict[str, Any]]:
    response = client.get(
        f"{campaign_id}/insights",
        params={"fields": "spend", "date_preset": "today", "limit": 1},
    )
    rows = response.get("data")
    if not isinstance(rows, list) or not rows:
        return None, response
    raw = rows[0].get("spend")
    if raw in (None, ""):
        return None, response
    try:
        amount = Decimal(str(raw))
    except Exception as exc:
        raise ReadbackError(f"Could not parse today's campaign spend: {raw!r}") from exc
    multiplier = Decimal(10) ** policy.currency_minor_exponent
    return int(amount * multiplier), response


def _read_object(client: MetaGraphClient, kind: str, object_id: str) -> dict[str, Any]:
    return client.get(object_id, params={"fields": READ_FIELDS[kind]})


def _assert_parent_preflight(
    client: MetaGraphClient,
    plan: dict[str, Any],
    policy: OperatorPolicy,
) -> dict[str, Any]:
    ad_set = client.get(
        plan["ad_set_id"],
        params={
            "fields": (
                "id,name,campaign_id,status,effective_status,daily_budget,lifetime_budget,"
                "optimization_goal,billing_event,targeting,issues_info,"
                "campaign{id,name,status,effective_status,daily_budget,lifetime_budget,"
                "insights.date_preset(today).limit(1){spend}}"
            )
        },
    )
    campaign = ad_set.get("campaign")
    if not isinstance(campaign, dict):
        raise ReadbackError("Expanded campaign preflight was UNAVAILABLE; creation fails closed")
    if str(ad_set.get("campaign_id")) != plan["campaign_id"]:
        raise ReadbackError("Ad set is not attached to the approved campaign")
    if str(campaign.get("id")) != plan["campaign_id"]:
        raise ReadbackError("Expanded campaign ID did not match the approved campaign")
    if policy.require_parent_paused_for_create:
        if campaign.get("status") != "PAUSED" or ad_set.get("status") != "PAUSED":
            raise PolicyError(
                "This policy requires both parents configured PAUSED before ad creation"
            )
    spend_raw = campaign.get("insights") or {}
    spend_rows = spend_raw.get("data") if isinstance(spend_raw, dict) else None
    spend_minor: int | None = None
    if isinstance(spend_rows, list) and spend_rows:
        raw = spend_rows[0].get("spend")
        if raw not in (None, ""):
            try:
                multiplier = Decimal(10) ** policy.currency_minor_exponent
                spend_minor = int(Decimal(str(raw)) * multiplier)
            except Exception as exc:
                raise ReadbackError(f"Could not parse today's campaign spend: {raw!r}") from exc
    if policy.max_spend_today_minor_for_create is not None:
        if spend_minor is None:
            raise ReadbackError("Today's spend is UNAVAILABLE; the creation spend gate fails closed")
        if spend_minor > policy.max_spend_today_minor_for_create:
            raise PolicyError(
                f"Today's spend {spend_minor} exceeds the creation cap "
                f"{policy.max_spend_today_minor_for_create} minor units"
            )
    return {
        "campaign": campaign,
        "ad_set": ad_set,
        "spend_today_minor": spend_minor if spend_minor is not None else "UNAVAILABLE",
        "spend_response": spend_raw,
    }


def _existing_ads(client: MetaGraphClient, ad_set_id: str) -> list[dict[str, Any]]:
    return client.get_all(
        f"{ad_set_id}/ads",
        params={"fields": READ_FIELDS["ad"], "limit": 100},
    )


def _image_hash(upload: dict[str, Any]) -> str:
    images = upload.get("images")
    if not isinstance(images, dict) or not images:
        raise ReadbackError("Meta image upload returned no images")
    first = next(iter(images.values()))
    value = first.get("hash") if isinstance(first, dict) else None
    if not value:
        raise ReadbackError("Meta image upload returned no image hash")
    return str(value)


def _wait_for_video(
    client: MetaGraphClient,
    video_id: str,
    *,
    max_attempts: int = 6,
    interval_seconds: int = 10,
) -> dict[str, Any]:
    for attempt in range(1, max_attempts + 1):
        observed = client.get(
            video_id,
            params={"fields": "id,title,status,length,thumbnails"},
        )
        status = observed.get("status") or {}
        processing = status.get("processing_phase") if isinstance(status, dict) else {}
        processing = processing if isinstance(processing, dict) else {}
        state = str(processing.get("status", "unknown")).lower()
        if state == "complete":
            thumbnails = observed.get("thumbnails") or {}
            rows = thumbnails.get("data", []) if isinstance(thumbnails, dict) else []
            return {
                "ready": True,
                "attempts": attempt,
                "status": observed,
                "thumbnail_url": rows[0].get("uri") if rows else None,
            }
        if state == "error":
            raise ReadbackError(
                f"Meta video processing failed for {video_id}: {processing.get('error')}"
            )
        if attempt < max_attempts:
            time.sleep(interval_seconds)
    raise ReadbackError(
        f"Meta video {video_id} is still processing after {max_attempts} bounded reads. "
        "The run stopped to protect the API request budget; resume later."
    )


def _identity_story(identity: dict[str, Any], body: dict[str, Any]) -> dict[str, Any]:
    story: dict[str, Any] = {"page_id": identity["page_id"], **body}
    if identity.get("instagram_user_id"):
        story["instagram_user_id"] = identity["instagram_user_id"]
    return story


def _creative_payload(
    ad: dict[str, Any], identity: dict[str, Any], uploaded: dict[str, Any]
) -> dict[str, Any]:
    creative_format = ad["format"]
    image_hashes = uploaded.get("image_hashes", [])
    if creative_format == "single_image":
        link_data = {
            "link": ad["destination_url"],
            "message": ad["primary_text"],
            "name": ad["headline"],
            "description": ad["description"],
            "image_hash": image_hashes[0],
            "call_to_action": {
                "type": ad["cta"],
                "value": {"link": ad["destination_url"]},
            },
        }
        story = _identity_story(identity, {"link_data": link_data})
        creative_body: dict[str, Any] = {"object_story_spec": story}
    elif creative_format == "carousel":
        children = []
        for card, image_hash in zip(ad["cards"], image_hashes):
            children.append(
                {
                    "link": card["destination_url"],
                    "name": card["headline"],
                    "description": card["description"],
                    "image_hash": image_hash,
                    "call_to_action": {
                        "type": card["cta"],
                        "value": {"link": card["destination_url"]},
                    },
                }
            )
        link_data = {
            "link": ad["destination_url"],
            "message": ad["primary_text"],
            "child_attachments": children,
            "multi_share_optimized": False,
            "multi_share_end_card": bool(ad.get("multi_share_end_card", True)),
            "call_to_action": {
                "type": ad["cta"],
                "value": {"link": ad["destination_url"]},
            },
        }
        story = _identity_story(identity, {"link_data": link_data})
        creative_body = {"object_story_spec": story}
    elif creative_format == "single_video":
        video_data: dict[str, Any] = {
            "video_id": uploaded["video_id"],
            "message": ad["primary_text"],
            "title": ad["headline"],
            "call_to_action": {
                "type": ad["cta"],
                "value": {"link": ad["destination_url"]},
            },
        }
        if ad["description"]:
            video_data["description"] = ad["description"]
        thumbnail_url = (uploaded.get("video_processing") or {}).get("thumbnail_url")
        if thumbnail_url:
            video_data["image_url"] = thumbnail_url
        story = _identity_story(identity, {"video_data": video_data})
        creative_body = {"object_story_spec": story}
    else:
        ad_format = "SINGLE_IMAGE" if creative_format == "dynamic_image" else "AUTOMATIC_FORMAT"
        asset_feed_spec = {
            "ad_formats": [ad_format],
            "images": [{"hash": value} for value in image_hashes],
            "bodies": [{"text": value} for value in ad["bodies"]],
            "titles": [{"text": value} for value in ad["headlines"]],
            "descriptions": [{"text": value} for value in ad["descriptions"]],
            "call_to_action_types": [ad["cta"]],
            "link_urls": [{"website_url": ad["destination_url"]}],
        }
        creative_body = {
            "object_story_spec": _identity_story(identity, {}),
            "asset_feed_spec": asset_feed_spec,
        }
    payload: dict[str, Any] = {
        "name": ad["creative_name"],
        **creative_body,
        "contextual_multi_ads": {"enroll_status": "OPT_OUT"},
    }
    if ad.get("url_tags"):
        payload["url_tags"] = ad["url_tags"]
    return payload


def _verify_created_ad(
    client: MetaGraphClient,
    *,
    ad_id: str,
    creative_id: str,
    plan_ad: dict[str, Any],
    plan: dict[str, Any],
    uploaded: dict[str, Any],
) -> dict[str, Any]:
    ad = _read_object(client, "ad", ad_id)
    creative = client.get(
        creative_id,
        params={
            "fields": "id,name,object_story_spec,asset_feed_spec,instagram_user_id,url_tags,link_destination_display_url,contextual_multi_ads,degrees_of_freedom_spec",
        },
    )
    story = creative.get("object_story_spec") or {}
    link = story.get("link_data") or {}
    video = story.get("video_data") or {}
    feed = creative.get("asset_feed_spec") or {}
    observed_ig = story.get("instagram_user_id") or creative.get("instagram_user_id")
    creative_format = plan_ad["format"]
    image_hashes = uploaded.get("image_hashes", [])
    checks = {
        "ad_id": str(ad.get("id")) == ad_id,
        "ad_name": ad.get("name") == plan_ad["name"],
        "ad_set": str(ad.get("adset_id")) == plan["ad_set_id"],
        "campaign": str(ad.get("campaign_id")) == plan["campaign_id"],
        "status": ad.get("status") == plan_ad["status"],
        "creative_id": str((ad.get("creative") or {}).get("id")) == creative_id,
        "creative_name": str(creative.get("name", "")).startswith(plan_ad["creative_name"]),
        "page_id": str(story.get("page_id")) == plan["identity"]["page_id"],
        "instagram_user_id": str(observed_ig or "")
        == str(plan["identity"].get("instagram_user_id") or ""),
        "url_tags": (creative.get("url_tags") or "") == plan_ad["url_tags"],
        "no_custom_display_link": not link.get("caption")
        and not creative.get("link_destination_display_url"),
        "contextual_multi_ads_opt_out": creative.get("contextual_multi_ads")
        == {"enroll_status": "OPT_OUT"},
    }
    if creative_format == "single_image":
        checks.update(
            {
                "image_hash": link.get("image_hash") == image_hashes[0],
                "destination": link.get("link") == plan_ad["destination_url"],
                "primary_text": link.get("message") == plan_ad["primary_text"],
                "headline": link.get("name") == plan_ad["headline"],
                "description": (link.get("description") or "") == plan_ad["description"],
            }
        )
    elif creative_format == "carousel":
        children = link.get("child_attachments") or []
        checks.update(
            {
                "card_count": len(children) == len(plan_ad["cards"]),
                "card_image_hashes": [row.get("image_hash") for row in children] == image_hashes,
                "card_destinations": [row.get("link") for row in children]
                == [row["destination_url"] for row in plan_ad["cards"]],
                "card_headlines": [row.get("name") for row in children]
                == [row["headline"] for row in plan_ad["cards"]],
                "primary_text": link.get("message") == plan_ad["primary_text"],
            }
        )
    elif creative_format == "single_video":
        checks.update(
            {
                "video_id": str(video.get("video_id")) == str(uploaded["video_id"]),
                "destination": ((video.get("call_to_action") or {}).get("value") or {}).get("link")
                == plan_ad["destination_url"],
                "primary_text": video.get("message") == plan_ad["primary_text"],
                "headline": video.get("title") == plan_ad["headline"],
            }
        )
    else:
        expected_format = "SINGLE_IMAGE" if creative_format == "dynamic_image" else "AUTOMATIC_FORMAT"
        checks.update(
            {
                "image_hashes": [row.get("hash") for row in feed.get("images", [])] == image_hashes,
                "bodies": [row.get("text") for row in feed.get("bodies", [])] == plan_ad["bodies"],
                "headlines": [row.get("text") for row in feed.get("titles", [])]
                == plan_ad["headlines"],
                "descriptions": [row.get("text") for row in feed.get("descriptions", [])]
                == plan_ad["descriptions"],
                "destination": [row.get("website_url") for row in feed.get("link_urls", [])]
                == [plan_ad["destination_url"]],
                "ad_format": feed.get("ad_formats") == [expected_format],
            }
        )
    mismatches = [key for key, value in checks.items() if not value]
    return {
        "verified": not mismatches,
        "checks": checks,
        "mismatches": mismatches,
        "observed": {"ad": ad, "creative": creative},
    }


def _apply_create_ads(
    client: MetaGraphClient,
    plan: dict[str, Any],
    policy: OperatorPolicy,
    receipt: dict[str, Any],
    receipt_path: Path,
) -> None:
    receipt["preflight"] = _assert_parent_preflight(client, plan, policy)
    existing = _existing_ads(client, plan["ad_set_id"])
    by_name: dict[str, list[dict[str, Any]]] = {}
    for row in existing:
        by_name.setdefault(str(row.get("name")), []).append(row)
    local_paths = plan.get("_local", {}).get("media_paths", {})
    pending_write_index = 0
    for plan_ad in plan["ads"]:
        matches = by_name.get(plan_ad["name"], [])
        if len(matches) > 1:
            raise ReadbackError(f"Duplicate live ad name exists: {plan_ad['name']}")
        if len(matches) == 1:
            receipt["results"].append(
                {
                    "name": plan_ad["name"],
                    "result": "idempotent_existing",
                    "ad_id": str(matches[0].get("id")),
                    "status": matches[0].get("status"),
                    "effective_status": matches[0].get("effective_status"),
                }
            )
            _save(receipt_path, receipt)
            continue
        if pending_write_index > 0:
            _assert_parent_preflight(client, plan, policy)
        pending_write_index += 1
        local_path_values = local_paths.get(plan_ad["name"])
        if not local_path_values:
            raise ValidationError(f"Internal media path missing for {plan_ad['name']}")
        if isinstance(local_path_values, str):
            local_path_values = [local_path_values]
        if len(local_path_values) != len(plan_ad["media_assets"]):
            raise ValidationError(f"Internal media mapping changed for {plan_ad['name']}")
        for local_path, frozen_media in zip(local_path_values, plan_ad["media_assets"]):
            if sha256_file(Path(local_path)) != frozen_media["media_sha256"]:
                raise ValidationError(f"Media bytes changed after planning: {plan_ad['name']}")

        uploaded: dict[str, Any] = {"image_hashes": []}
        if plan_ad["format"] == "single_video":
            video_upload = client.post_file(
                f"act_{plan['account_id']}/advideos",
                file_field="source",
                file_path=local_path_values[0],
                fields={"title": plan_ad["creative_name"]},
            )
            video_id = str(video_upload.get("id") or "")
            if not video_id:
                raise ReadbackError("Meta video upload returned no video ID")
            uploaded["video_id"] = video_id
            uploaded["video_processing"] = _wait_for_video(client, video_id)
        else:
            for local_path in local_path_values:
                upload = client.post_file(
                    f"act_{plan['account_id']}/adimages",
                    file_field="filename",
                    file_path=local_path,
                )
                uploaded["image_hashes"].append(_image_hash(upload))

        creative_payload = _creative_payload(plan_ad, plan["identity"], uploaded)
        creative_result = client.post(
            f"act_{plan['account_id']}/adcreatives", data=creative_payload
        )
        creative_id = str(creative_result.get("id") or "")
        if not creative_id:
            raise ReadbackError("Creative creation returned no ID")
        ad_payload = {
            "name": plan_ad["name"],
            "adset_id": plan["ad_set_id"],
            "creative": {"creative_id": creative_id},
            "status": plan_ad["status"],
        }
        validation = client.post(
            f"act_{plan['account_id']}/ads",
            data={**ad_payload, "execution_options": ["validate_only"]},
        )
        created = client.post(f"act_{plan['account_id']}/ads", data=ad_payload)
        ad_id = str(created.get("id") or "")
        if not ad_id:
            raise ReadbackError("Ad creation returned no ID")
        verification = _verify_created_ad(
            client,
            ad_id=ad_id,
            creative_id=creative_id,
            plan_ad=plan_ad,
            plan=plan,
            uploaded=uploaded,
        )
        result = {
            "name": plan_ad["name"],
            "result": "created",
            "format": plan_ad["format"],
            "source_sha256s": [row["media_sha256"] for row in plan_ad["media_assets"]],
            "uploaded": uploaded,
            "creative_id": creative_id,
            "ad_id": ad_id,
            "validation": validation,
            "verification": verification,
        }
        receipt["results"].append(result)
        _save(receipt_path, receipt)
        if not verification["verified"]:
            raise ReadbackError(
                f"Post-write verification failed for {plan_ad['name']}: "
                f"{verification['mismatches']}"
            )
    receipt["final_parent_readback"] = _assert_parent_preflight(client, plan, policy)


def _name_matches(
    client: MetaGraphClient, *, account_id: str, edge: str, name: str
) -> list[dict[str, Any]]:
    rows = client.get_all(
        f"act_{account_id}/{edge}",
        params={"fields": "id,name,status,effective_status", "limit": 100},
    )
    return [row for row in rows if row.get("name") == name]


def _apply_create_entity(
    client: MetaGraphClient,
    plan: dict[str, Any],
    receipt: dict[str, Any],
) -> None:
    edge = "campaigns" if plan["action"] == "create_campaign" else "adsets"
    kind = "campaign" if plan["action"] == "create_campaign" else "ad_set"
    matches = _name_matches(
        client, account_id=plan["account_id"], edge=edge, name=plan["payload"]["name"]
    )
    if len(matches) > 1:
        raise ReadbackError(f"Multiple live {kind} objects share this exact name")
    if matches:
        receipt["results"].append(
            {"result": "idempotent_existing", "object": matches[0]}
        )
        return
    client.post(
        f"act_{plan['account_id']}/{edge}",
        data={**plan["payload"], "execution_options": ["validate_only"]},
    )
    created = client.post(f"act_{plan['account_id']}/{edge}", data=plan["payload"])
    object_id = str(created.get("id") or "")
    if not object_id:
        raise ReadbackError(f"{kind} creation returned no ID")
    observed = _read_object(client, kind, object_id)
    verified = observed.get("name") == plan["payload"]["name"] and observed.get("status") == "PAUSED"
    receipt["results"].append(
        {
            "result": "created",
            "object_id": object_id,
            "verification": {"verified": verified, "observed": observed},
        }
    )
    if not verified:
        raise ReadbackError(f"{kind} readback mismatch")


def _apply_status(client: MetaGraphClient, plan: dict[str, Any], receipt: dict[str, Any]) -> None:
    before = _read_object(client, plan["kind"], plan["object_id"])
    client.post(plan["object_id"], data={"status": plan["target_status"]})
    after = _read_object(client, plan["kind"], plan["object_id"])
    verified = after.get("status") == plan["target_status"]
    receipt["results"].append(
        {"result": "status_changed", "before": before, "after": after, "verified": verified}
    )
    if not verified:
        raise ReadbackError("Status readback did not match the approved target")


def _apply_budget(
    client: MetaGraphClient,
    plan: dict[str, Any],
    policy: OperatorPolicy,
    receipt: dict[str, Any],
) -> None:
    before = _read_object(client, plan["kind"], plan["object_id"])
    current_raw = before.get("daily_budget")
    if current_raw in (None, ""):
        raise ReadbackError("Current daily budget is UNAVAILABLE; budget change fails closed")
    current = int(current_raw)
    requested = int(plan["daily_budget_minor"])
    policy.assert_budget(requested, current)
    client.post(plan["object_id"], data={"daily_budget": requested})
    after = _read_object(client, plan["kind"], plan["object_id"])
    verified = int(after.get("daily_budget") or -1) == requested
    receipt["results"].append(
        {"result": "budget_changed", "before": before, "after": after, "verified": verified}
    )
    if not verified:
        raise ReadbackError("Budget readback did not match the approved value")


def execute_plan(
    plan: dict[str, Any],
    policy: OperatorPolicy,
    client: MetaGraphClient,
    *,
    confirmation: str | None = None,
    standing_authority: bool = False,
) -> dict[str, Any]:
    verify_plan(plan, policy)
    _assert_approval(
        plan, policy, confirmation=confirmation, standing=standing_authority
    )
    account_id = plan.get("account_id")
    if account_id:
        policy.assert_account(account_id)
    receipt_path = _receipt_path(policy, plan)
    receipt: dict[str, Any] = {
        "schema_version": 1,
        "started_at": utc_now(),
        "status": "running",
        "plan": _receipt_plan(plan),
        "plan_sha256": plan["plan_sha256"],
        "policy_sha256": policy.policy_hash,
        "approval": {
            "mode": policy.approval_mode,
            "mechanism": "plan_hash" if confirmation else "standing_authority",
        },
        "results": [],
    }
    _save(receipt_path, receipt)
    try:
        if account_id:
            receipt["account_preflight"] = _account_preflight(client, account_id)
        if plan["action"] == "create_ads":
            _apply_create_ads(client, plan, policy, receipt, receipt_path)
        elif plan["action"] in {"create_campaign", "create_ad_set"}:
            _apply_create_entity(client, plan, receipt)
        elif plan["action"] == "set_status":
            _apply_status(client, plan, receipt)
        elif plan["action"] == "set_budget":
            _apply_budget(client, plan, policy, receipt)
        else:
            raise ValidationError(f"No executor for action {plan['action']!r}")
        receipt["status"] = "verified"
    except Exception as exc:
        receipt["status"] = "blocked"
        receipt["error"] = str(exc)
        receipt["error_type"] = type(exc).__name__
        receipt["api_usage"] = client.request_stats()
        receipt["finished_at"] = utc_now()
        receipt["receipt_sha256"] = stable_hash(receipt)
        _save(receipt_path, receipt)
        raise
    receipt["finished_at"] = utc_now()
    receipt["api_usage"] = client.request_stats()
    receipt["receipt_sha256"] = stable_hash(receipt)
    _save(receipt_path, receipt)
    return {
        "verified": True,
        "receipt_path": str(receipt_path),
        "receipt_sha256": receipt["receipt_sha256"],
        "results": receipt["results"],
    }
