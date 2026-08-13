from __future__ import annotations

import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from typing import Any

from meta_ads_operator.errors import PolicyError
from meta_ads_operator.executor import execute_plan
from meta_ads_operator.planning import build_budget_plan, build_create_ads_plan, build_status_plan
from meta_ads_operator.policy import OperatorPolicy
from meta_ads_operator.util import sha256_file
from tests.helpers import advanced_manifest_dict, manifest_dict, policy_dict, write_json, write_png


class FakeClient:
    def __init__(self) -> None:
        self.last_usage: dict[str, Any] = {}
        self.campaign = {
            "id": "222222", "name": "CAMPAIGN", "status": "PAUSED",
            "effective_status": "PAUSED", "daily_budget": "3000",
        }
        self.ad_set = {
            "id": "333333", "name": "AD_SET", "campaign_id": "222222",
            "status": "PAUSED", "effective_status": "PAUSED", "daily_budget": "3000",
        }
        self.ads: dict[str, dict[str, Any]] = {}
        self.creatives: dict[str, dict[str, Any]] = {}
        self._creative_counter = 700000
        self._ad_counter = 800000
        self.requests: list[tuple[str, str]] = []

    def request_stats(self) -> dict[str, Any]:
        by_method: dict[str, int] = {}
        by_endpoint: dict[str, int] = {}
        for method, endpoint in self.requests:
            by_method[method] = by_method.get(method, 0) + 1
            by_endpoint[endpoint] = by_endpoint.get(endpoint, 0) + 1
        return {
            "total_http_attempts": len(self.requests),
            "by_method": by_method,
            "by_endpoint": by_endpoint,
            "max_observed_usage_percent": 0,
            "headers": deepcopy(self.last_usage),
        }

    def get(self, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self.requests.append(("GET", path))
        if path == "act_111111":
            return {"id": "act_111111", "account_id": "111111", "account_status": 1, "currency": "USD"}
        if path == "222222":
            return deepcopy(self.campaign)
        if path == "333333":
            result = deepcopy(self.ad_set)
            if params and "campaign{" in str(params.get("fields", "")):
                result["campaign"] = {
                    **deepcopy(self.campaign),
                    "insights": {"data": [{"spend": "0.00"}]},
                }
            return result
        if path == "222222/insights":
            return {"data": [{"spend": "0.00"}]}
        if path in self.ads:
            return deepcopy(self.ads[path])
        if path in self.creatives:
            return deepcopy(self.creatives[path])
        if path == "META_VIDEO_ID":
            return {
                "id": "META_VIDEO_ID",
                "status": {"processing_phase": {"status": "complete"}},
                "thumbnails": {"data": [{"uri": "https://example.invalid/thumb.jpg"}]},
            }
        raise AssertionError(f"Unexpected GET: {path} {params}")

    def get_all(self, path: str, *, params: dict[str, Any] | None = None, max_pages: int = 20) -> list[dict[str, Any]]:
        self.requests.append(("GET", path))
        if path == "333333/ads":
            return [deepcopy(value) for value in self.ads.values()]
        raise AssertionError(f"Unexpected GET ALL: {path}")

    def post_file(self, path: str, *, file_field: str, file_path: str | Path, fields: dict[str, Any] | None = None) -> dict[str, Any]:
        self.requests.append(("POST", path))
        self.last_usage = {"x-app-usage": {"call_count": 1}}
        if path == "act_111111/advideos":
            return {"id": "META_VIDEO_ID"}
        return {"images": {"creative.png": {"hash": "META_IMAGE_HASH"}}}

    def post(self, path: str, *, data: dict[str, Any]) -> dict[str, Any]:
        self.requests.append(("POST", path))
        if path == "act_111111/adcreatives":
            self._creative_counter += 1
            creative_id = str(self._creative_counter)
            self.creatives[creative_id] = {
                "id": creative_id,
                "name": data["name"],
                "object_story_spec": deepcopy(data["object_story_spec"]),
                "asset_feed_spec": deepcopy(data.get("asset_feed_spec", {})),
                "url_tags": data.get("url_tags", ""),
                "contextual_multi_ads": deepcopy(data["contextual_multi_ads"]),
            }
            return {"id": creative_id}
        if path == "act_111111/ads":
            if data.get("execution_options") == ["validate_only"]:
                return {"success": True}
            self._ad_counter += 1
            ad_id = str(self._ad_counter)
            creative_id = data["creative"]["creative_id"]
            self.ads[ad_id] = {
                "id": ad_id,
                "name": data["name"],
                "adset_id": "333333",
                "campaign_id": "222222",
                "status": data["status"],
                "effective_status": data["status"],
                "creative": {"id": creative_id},
            }
            return {"id": ad_id}
        if path == "444444" and "status" in data:
            self.ads.setdefault(
                "444444",
                {"id": "444444", "name": "EXISTING_AD", "adset_id": "333333", "campaign_id": "222222", "creative": {"id": "999999"}},
            )
            self.ads["444444"].update(status=data["status"], effective_status=data["status"])
            return {"success": True}
        if path == "333333" and "daily_budget" in data:
            self.ad_set["daily_budget"] = str(data["daily_budget"])
            return {"success": True}
        raise AssertionError(f"Unexpected POST: {path} {data}")


class ExecutorTests(unittest.TestCase):
    def _fixture(self, root: Path) -> tuple[OperatorPolicy, dict[str, Any]]:
        image = write_png(root / "creative.png")
        policy = OperatorPolicy.load(write_json(root / "policy.json", policy_dict(root)))
        manifest = write_json(root / "manifest.json", manifest_dict(image, sha256_file(image)))
        return policy, build_create_ads_plan(manifest, policy)

    def test_exact_confirmation_creates_and_verifies_one_paused_ad(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            policy, plan = self._fixture(root)
            result = execute_plan(plan, policy, FakeClient(), confirmation=plan["plan_sha256"])
            self.assertTrue(result["verified"])
            self.assertEqual(result["results"][0]["result"], "created")
            self.assertTrue(result["results"][0]["verification"]["verified"])
            receipt = Path(result["receipt_path"]).read_text(encoding="utf-8")
            self.assertNotIn(str(root), receipt)
            self.assertNotIn("access_token", receipt)
            payload = json.loads(receipt)
            self.assertEqual(payload["api_usage"]["total_http_attempts"], 10)

    def test_wrong_confirmation_blocks_before_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            policy, plan = self._fixture(Path(tmp))
            with self.assertRaises(PolicyError):
                execute_plan(plan, policy, FakeClient(), confirmation="wrong")

    def test_exact_status_and_bounded_budget_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            policy = OperatorPolicy.load(write_json(root / "policy.json", policy_dict(root)))
            client = FakeClient()
            client.ads["444444"] = {
                "id": "444444", "name": "EXISTING_AD", "adset_id": "333333",
                "campaign_id": "222222", "status": "ACTIVE", "effective_status": "ACTIVE",
                "creative": {"id": "999999"},
            }
            status_plan = build_status_plan(
                kind="ad", object_id="444444", status="PAUSED", policy=policy
            )
            result = execute_plan(
                status_plan, policy, client, confirmation=status_plan["plan_sha256"]
            )
            self.assertTrue(result["results"][0]["verified"])
            budget_plan = build_budget_plan(
                kind="ad_set", object_id="333333", daily_budget_minor=3300, policy=policy
            )
            result = execute_plan(
                budget_plan, policy, client, confirmation=budget_plan["plan_sha256"]
            )
            self.assertTrue(result["results"][0]["verified"])

    def test_all_five_release_formats_create_and_verify(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            policy = OperatorPolicy.load(write_json(root / "policy.json", policy_dict(root)))
            manifest = write_json(root / "advanced.json", advanced_manifest_dict(root))
            plan = build_create_ads_plan(manifest, policy)
            result = execute_plan(plan, policy, FakeClient(), confirmation=plan["plan_sha256"])
            self.assertTrue(result["verified"])
            self.assertEqual(len(result["results"]), 5)
            self.assertTrue(all(row["verification"]["verified"] for row in result["results"]))


if __name__ == "__main__":
    unittest.main()
