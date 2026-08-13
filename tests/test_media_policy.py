from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from guarded_meta_ads.errors import PolicyError
from guarded_meta_ads.media import inventory
from guarded_meta_ads.policy import OperatorPolicy
from tests.helpers import policy_dict, write_json, write_png


class MediaPolicyTests(unittest.TestCase):
    def test_inventory_reads_hash_and_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_png(root / "creative.png", 1080, 1350)
            rows = inventory(root)
            self.assertEqual(len(rows), 1)
            self.assertEqual((rows[0]["width"], rows[0]["height"]), (1080, 1350))
            self.assertEqual(len(rows[0]["sha256"]), 64)

    def test_policy_blocks_destination_and_budget(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            policy = OperatorPolicy.load(write_json(root / "policy.json", policy_dict(root)))
            policy.assert_destination("https://shop.example.com/products/one")
            with self.assertRaises(PolicyError):
                policy.assert_destination("https://evil.example/products/one")
            with self.assertRaises(PolicyError):
                policy.assert_budget(6000)
            with self.assertRaises(PolicyError):
                policy.assert_budget(1300, 1000)


if __name__ == "__main__":
    unittest.main()

