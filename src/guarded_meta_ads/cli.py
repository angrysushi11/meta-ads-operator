from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .capabilities import capability_report
from .doctor import run as run_doctor
from .errors import OperatorError
from .executor import execute_plan
from .graph import MetaGraphClient
from .media import inventory
from .planning import (
    build_budget_plan,
    build_create_ad_set_plan,
    build_create_ads_plan,
    build_create_campaign_plan,
    build_status_plan,
)
from .policy import OperatorPolicy
from .reads import DEFAULT_INSIGHT_FIELDS, discover, insights, read_object
from .rules import evaluate
from .secrets import load_access_token, store_access_token
from .util import read_json, sanitize, write_json_atomic


def _emit(value: Any) -> None:
    print(json.dumps(sanitize(value), ensure_ascii=False, indent=2, sort_keys=True))


def _add_policy(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--policy", required=True, help="Path to the locked local policy JSON")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="guarded-meta",
        description="Plan, verify, and operate Meta ads through explicit policies and receipts.",
    )
    parser.add_argument("--version", action="version", version="guarded-meta 0.1.0")
    commands = parser.add_subparsers(dest="command", required=True)

    doctor = commands.add_parser("doctor", help="Check local runtime, policy, and token availability")
    doctor.add_argument("--policy")

    commands.add_parser("auth-store", help="Store a token in the OS credential store without echoing it")

    capabilities = commands.add_parser(
        "capabilities",
        help="List supported formats and explain recognized formats that need another handler",
    )
    capabilities.add_argument("--format", help="Check one format name, alias, or requested ad family")

    inv = commands.add_parser("inventory", help="Inventory only one explicitly supplied creative folder")
    inv.add_argument("folder")
    inv.add_argument("--output")

    discovery = commands.add_parser("discover", help="Read accessible Meta businesses, accounts, Pages, and IG links")
    discovery.add_argument("--graph-version", default="v25.0")

    read = commands.add_parser("read", help="Read one locked campaign, ad set, or ad")
    _add_policy(read)
    read.add_argument("--kind", choices=["campaign", "ad_set", "ad"], required=True)
    read.add_argument("--id", required=True)

    report = commands.add_parser("insights", help="Read selected official insight fields")
    _add_policy(report)
    report.add_argument("--id", required=True)
    report.add_argument("--level", choices=["campaign", "adset", "ad"], required=True)
    report.add_argument("--date-preset", default="last_7d")
    report.add_argument("--fields", default=DEFAULT_INSIGHT_FIELDS)
    report.add_argument("--time-increment", type=int)
    report.add_argument("--output")

    rule = commands.add_parser("evaluate-rule", help="Evaluate a local rule without mutating Meta")
    _add_policy(rule)
    rule.add_argument("--insights", required=True)
    rule.add_argument("--rule", required=True)
    rule.add_argument("--output")

    plan = commands.add_parser("plan", help="Build an immutable write plan; no live mutation")
    plan_commands = plan.add_subparsers(dest="plan_command", required=True)

    ads = plan_commands.add_parser("create-ads", help="Plan fresh image -> creative -> ad objects")
    _add_policy(ads)
    ads.add_argument("--manifest", required=True)
    ads.add_argument("--output", required=True)

    campaign = plan_commands.add_parser("create-campaign", help="Plan one PAUSED campaign")
    _add_policy(campaign)
    campaign.add_argument("--spec", required=True)
    campaign.add_argument("--output", required=True)

    ad_set = plan_commands.add_parser("create-ad-set", help="Plan one PAUSED ad set")
    _add_policy(ad_set)
    ad_set.add_argument("--spec", required=True)
    ad_set.add_argument("--output", required=True)

    status = plan_commands.add_parser("status", help="Plan one exact status change")
    _add_policy(status)
    status.add_argument("--kind", choices=["campaign", "ad_set", "ad"], required=True)
    status.add_argument("--id", required=True)
    status.add_argument("--status", choices=["PAUSED", "ACTIVE"], required=True)
    status.add_argument("--output", required=True)

    budget = plan_commands.add_parser("budget", help="Plan one bounded daily-budget change")
    _add_policy(budget)
    budget.add_argument("--kind", choices=["campaign", "ad_set"], required=True)
    budget.add_argument("--id", required=True)
    budget.add_argument("--daily-budget-minor", type=int, required=True)
    budget.add_argument("--output", required=True)

    apply = commands.add_parser("apply", help="Apply exactly one immutable plan and verify readback")
    _add_policy(apply)
    apply.add_argument("--plan", required=True)
    approval = apply.add_mutually_exclusive_group(required=True)
    approval.add_argument("--confirm", help="Exact plan_sha256 printed by the planning step")
    approval.add_argument(
        "--standing-authority",
        action="store_true",
        help="Use a non-expired execute-within-policy authority",
    )
    return parser


def _client(policy: OperatorPolicy | None = None, graph_version: str | None = None) -> MetaGraphClient:
    return MetaGraphClient(
        load_access_token(),
        graph_version=graph_version or (policy.graph_version if policy else "v25.0"),
        max_http_attempts=policy.max_http_attempts_per_run if policy else 250,
        stop_at_usage_percent=policy.stop_at_usage_percent if policy else 90,
    )


def _save_or_emit(value: dict[str, Any], output: str | None) -> None:
    if output:
        target = write_json_atomic(output, value)
        _emit({"written": str(target), "result": value})
    else:
        _emit(value)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "doctor":
            _emit(run_doctor(args.policy))
            return 0
        if args.command == "auth-store":
            _emit(store_access_token())
            return 0
        if args.command == "capabilities":
            _emit(capability_report(args.format))
            return 0
        if args.command == "inventory":
            result = {"folder": str(Path(args.folder).expanduser().resolve()), "media": inventory(args.folder)}
            _save_or_emit(result, args.output)
            return 0
        if args.command == "discover":
            client = _client(graph_version=args.graph_version)
            result = discover(client)
            result["api_usage"] = client.request_stats()
            _emit(result)
            return 0

        policy = OperatorPolicy.load(args.policy)
        if args.command == "read":
            client = _client(policy)
            result = read_object(client, policy, kind=args.kind, object_id=args.id)
            result["api_usage"] = client.request_stats()
            _emit(result)
        elif args.command == "insights":
            client = _client(policy)
            result = insights(
                client, policy, object_id=args.id, level=args.level,
                date_preset=args.date_preset, fields=args.fields,
                time_increment=args.time_increment,
            )
            result["api_usage"] = client.request_stats()
            _save_or_emit(result, args.output)
        elif args.command == "evaluate-rule":
            _save_or_emit(evaluate(args.insights, args.rule, policy), args.output)
        elif args.command == "plan":
            if args.plan_command == "create-ads":
                result = build_create_ads_plan(args.manifest, policy)
            elif args.plan_command == "create-campaign":
                result = build_create_campaign_plan(args.spec, policy)
            elif args.plan_command == "create-ad-set":
                result = build_create_ad_set_plan(args.spec, policy)
            elif args.plan_command == "status":
                result = build_status_plan(
                    kind=args.kind, object_id=args.id, status=args.status, policy=policy
                )
            elif args.plan_command == "budget":
                result = build_budget_plan(
                    kind=args.kind, object_id=args.id,
                    daily_budget_minor=args.daily_budget_minor, policy=policy,
                )
            else:
                raise OperatorError(f"Unsupported planning command: {args.plan_command}")
            target = write_json_atomic(args.output, result)
            _emit(
                {
                    "planned": True,
                    "plan_path": str(target),
                    "plan_sha256": result["plan_sha256"],
                    "summary": result["summary"],
                    "next_step": (
                        f"Review the complete plan, then apply with --confirm {result['plan_sha256']}"
                    ),
                }
            )
        elif args.command == "apply":
            plan = read_json(args.plan)
            plan.pop("_source_path", None)
            _emit(
                execute_plan(
                    plan,
                    policy,
                    _client(policy),
                    confirmation=args.confirm,
                    standing_authority=args.standing_authority,
                )
            )
        return 0
    except (OperatorError, OSError, ValueError) as exc:
        _emit({"ok": False, "error_type": type(exc).__name__, "error": str(exc)})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
