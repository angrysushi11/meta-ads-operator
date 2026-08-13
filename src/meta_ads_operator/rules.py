from __future__ import annotations

from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from .errors import ValidationError
from .policy import OperatorPolicy
from .util import read_json, stable_hash, utc_now


OPERATORS = {
    "gt": lambda left, right: left > right,
    "gte": lambda left, right: left >= right,
    "lt": lambda left, right: left < right,
    "lte": lambda left, right: left <= right,
    "eq": lambda left, right: left == right,
}


def _metric(row: dict[str, Any], name: str) -> Decimal | None:
    value = row.get(name)
    if value in (None, "", "UNAVAILABLE", "Not available"):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def evaluate(insights_path: str | Path, rule_path: str | Path, policy: OperatorPolicy) -> dict[str, Any]:
    policy.assert_action("evaluate_rule")
    insight_payload = read_json(insights_path)
    rule = read_json(rule_path)
    insight_payload.pop("_source_path", None)
    rule.pop("_source_path", None)
    if rule.get("schema_version") != 1:
        raise ValidationError("Rule schema_version must equal 1")
    action = str(rule.get("action", ""))
    if action not in {"propose_pause", "propose_budget_increase"}:
        raise ValidationError("Rule action must be propose_pause or propose_budget_increase")
    conditions = rule.get("conditions")
    if not isinstance(conditions, list) or not conditions:
        raise ValidationError("Rule must contain at least one condition")
    rows = insight_payload.get("rows")
    if not isinstance(rows, list):
        raise ValidationError("Insights input must contain a rows list")
    candidates: list[dict[str, Any]] = []
    unavailable: list[dict[str, Any]] = []
    for row in rows:
        failed = False
        missing: list[str] = []
        evidence: dict[str, str] = {}
        for condition in conditions:
            metric = str(condition.get("metric", ""))
            operation = str(condition.get("operator", ""))
            if operation not in OPERATORS:
                raise ValidationError(f"Unsupported rule operator: {operation}")
            actual = _metric(row, metric)
            if actual is None:
                missing.append(metric)
                continue
            try:
                threshold = Decimal(str(condition["value"]))
            except (KeyError, InvalidOperation) as exc:
                raise ValidationError(f"Invalid threshold for {metric}") from exc
            evidence[metric] = str(actual)
            if not OPERATORS[operation](actual, threshold):
                failed = True
        object_id = row.get("ad_id") or row.get("adset_id") or row.get("campaign_id")
        if missing:
            unavailable.append({"object_id": object_id, "missing_metrics": sorted(set(missing))})
        elif not failed:
            candidates.append({"object_id": object_id, "name": row.get("ad_name") or row.get("adset_name") or row.get("campaign_name"), "evidence": evidence})
    result = {
        "evaluated_at": utc_now(),
        "action": action,
        "rule": rule,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "unavailable_count": len(unavailable),
        "unavailable": unavailable,
        "live_write": False,
        "next_step": "Review candidates, then generate exact-ID write plans separately.",
    }
    result["evaluation_sha256"] = stable_hash(result)
    return result
