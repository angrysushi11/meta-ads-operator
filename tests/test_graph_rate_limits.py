from __future__ import annotations

import io
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request

from meta_ads_operator.errors import GraphAPIError
from meta_ads_operator.graph import MetaGraphClient


class GraphRateLimitTests(unittest.TestCase):
    def test_local_request_budget_blocks_before_network(self) -> None:
        client = MetaGraphClient("test-token", max_http_attempts=1)
        client._record_request(Request("https://graph.facebook.com/v25.0/me", method="GET"))
        with self.assertRaisesRegex(GraphAPIError, "Local request budget exhausted"):
            client._record_request(Request("https://graph.facebook.com/v25.0/me", method="GET"))
        self.assertEqual(client.request_stats()["total_http_attempts"], 1)

    def test_ad_account_utilization_is_the_controlling_usage_bucket(self) -> None:
        client = MetaGraphClient("test-token", stop_at_usage_percent=85)
        client.last_usage = {
            "x-app-usage": {"call_count": 2, "total_cputime": 0, "total_time": 1},
            "x-ad-account-usage": {
                "acc_id_util_pct": 87,
                "reset_time_duration": 3600,
                "ads_api_access_tier": "development_access",
            },
        }
        with self.assertRaisesRegex(GraphAPIError, "Meta usage reached 87%"):
            client._record_request(Request("https://graph.facebook.com/v25.0/me", method="GET"))
        snapshot = client.request_stats()
        self.assertEqual(snapshot["max_observed_usage_percent"], 87)
        self.assertEqual(snapshot["ad_account_reset_seconds"], 3600)
        self.assertEqual(snapshot["ads_api_access_tier"], "development_access")

    def test_hard_throttle_is_not_retried(self) -> None:
        client = MetaGraphClient("test-token")
        body = (
            b'{"error":{"message":"Too many calls","code":17,'
            b'"error_subcode":2446079,"fbtrace_id":"trace"}}'
        )
        error = HTTPError(
            "https://graph.facebook.com/v25.0/me",
            400,
            "Bad Request",
            {"x-ad-account-usage": '{"acc_id_util_pct":100}'},
            io.BytesIO(body),
        )
        with patch("meta_ads_operator.graph.urlopen", side_effect=error) as mocked:
            with self.assertRaisesRegex(GraphAPIError, "No retry was attempted") as raised:
                client.get("me")
        self.assertEqual(mocked.call_count, 1)
        self.assertEqual(raised.exception.error_code, 17)
        self.assertEqual(raised.exception.error_subcode, 2446079)
        self.assertEqual(client.request_stats()["total_http_attempts"], 1)


if __name__ == "__main__":
    unittest.main()
