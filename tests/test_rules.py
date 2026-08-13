from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from guarded_meta_ads.policy import OperatorPolicy
from guarded_meta_ads.rules import evaluate
from tests.helpers import policy_dict, write_json


class RuleTests(unittest.TestCase):
    def test_unavailable_is_not_zero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            policy = OperatorPolicy.load(write_json(root / "policy.json", policy_dict(root)))
            insights = write_json(
                root / "insights.json",
                {"rows": [
                    {"ad_id": "444444", "ad_name": "A", "impressions": "1600", "outbound_clicks": "0"},
                    {"ad_id": "555555", "ad_name": "B", "impressions": "1600"},
                ]},
            )
            rule = write_json(
                root / "rule.json",
                {"schema_version": 1, "action": "propose_pause", "conditions": [
                    {"metric": "impressions", "operator": "gte", "value": 1500},
                    {"metric": "outbound_clicks", "operator": "eq", "value": 0},
                ]},
            )
            result = evaluate(insights, rule, policy)
            self.assertEqual(result["candidate_count"], 1)
            self.assertEqual(result["unavailable_count"], 1)
            self.assertEqual(result["unavailable"][0]["missing_metrics"], ["outbound_clicks"])


if __name__ == "__main__":
    unittest.main()

