from __future__ import annotations

from typing import Any

from .errors import ValidationError
from .graph import MetaGraphClient
from .policy import OperatorPolicy
from .util import normalize_meta_id, utc_now


DEFAULT_INSIGHT_FIELDS = (
    "impressions,reach,spend,clicks,inline_link_clicks,outbound_clicks,"
    "landing_page_views,actions,action_values"
)


def discover(client: MetaGraphClient) -> dict[str, Any]:
    businesses = client.get_all("me/businesses", params={"fields": "id,name", "limit": 100})
    accounts = client.get_all(
        "me/adaccounts",
        params={
            "fields": "id,account_id,name,account_status,currency,timezone_name,business",
            "limit": 100,
        },
    )
    pages = client.get_all(
        "me/accounts",
        params={"fields": "id,name,instagram_business_account", "limit": 100},
    )
    return {
        "read_at": utc_now(),
        "businesses": businesses,
        "ad_accounts": accounts,
        "pages": pages,
        "note": "This is a read-only orientation. It is a provisional account hypothesis, not business truth.",
    }


def read_object(
    client: MetaGraphClient,
    policy: OperatorPolicy,
    *,
    kind: str,
    object_id: Any,
) -> dict[str, Any]:
    policy.assert_action("read")
    if kind not in {"campaign", "ad_set", "ad"}:
        raise ValidationError("kind must be campaign, ad_set, or ad")
    normalized = policy.assert_existing_id(kind, object_id)
    fields = {
        "campaign": "id,name,status,effective_status,objective,daily_budget,lifetime_budget,budget_remaining,issues_info",
        "ad_set": "id,name,campaign_id,status,effective_status,daily_budget,lifetime_budget,optimization_goal,billing_event,targeting,promoted_object,issues_info",
        "ad": "id,name,adset_id,campaign_id,status,effective_status,creative,issues_info,ad_review_feedback",
    }[kind]
    return {"read_at": utc_now(), "kind": kind, "object": client.get(normalized, params={"fields": fields})}


def insights(
    client: MetaGraphClient,
    policy: OperatorPolicy,
    *,
    object_id: Any,
    level: str,
    date_preset: str,
    fields: str = DEFAULT_INSIGHT_FIELDS,
    time_increment: int | None = None,
) -> dict[str, Any]:
    policy.assert_action("insights")
    if level not in {"campaign", "adset", "ad"}:
        raise ValidationError("Insight level must be campaign, adset, or ad")
    normalized = normalize_meta_id(object_id, field="object_id")
    allowed_fields = {
        "date_start", "date_stop", "campaign_id", "campaign_name", "adset_id", "adset_name",
        "ad_id", "ad_name", "impressions", "reach", "spend", "clicks", "inline_link_clicks",
        "outbound_clicks", "landing_page_views", "actions", "action_values", "purchase_roas",
        "cpm", "cpc", "ctr", "frequency",
    }
    requested = [value.strip() for value in fields.split(",") if value.strip()]
    unknown = sorted(set(requested) - allowed_fields)
    if unknown:
        raise ValidationError(f"Unsupported insight fields: {unknown}")
    params: dict[str, Any] = {
        "fields": ",".join(requested),
        "date_preset": date_preset,
        "level": level,
        "limit": 500,
    }
    if time_increment is not None:
        params["time_increment"] = time_increment
    rows = client.get_all(f"{normalized}/insights", params=params)
    return {
        "read_at": utc_now(),
        "object_id": normalized,
        "level": level,
        "date_preset": date_preset,
        "fields": requested,
        "rows": rows,
        "availability_rule": "Missing metrics are UNAVAILABLE, never implicitly zero.",
    }

