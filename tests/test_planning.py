from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from guarded_meta_ads.errors import ValidationError
from guarded_meta_ads.planning import build_create_ads_plan, verify_plan
from guarded_meta_ads.policy import OperatorPolicy
from guarded_meta_ads.util import sha256_file
from tests.helpers import advanced_manifest_dict, manifest_dict, policy_dict, write_json, write_png


class PlanningTests(unittest.TestCase):
    def test_create_ads_plan_freezes_exact_media_and_copy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image = write_png(root / "creative.png")
            policy = OperatorPolicy.load(write_json(root / "policy.json", policy_dict(root)))
            manifest = write_json(root / "manifest.json", manifest_dict(image, sha256_file(image)))
            plan = build_create_ads_plan(manifest, policy)
            self.assertEqual(plan["ads"][0]["media_sha256"], sha256_file(image))
            self.assertEqual(plan["ads"][0]["status"], "PAUSED")
            self.assertTrue(plan["guards"]["custom_display_link_omitted"])
            verify_plan(plan, policy)
            plan["ads"][0]["headline"] = "Changed after approval"
            with self.assertRaises(ValidationError):
                verify_plan(plan, policy)

    def test_media_hash_mismatch_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image = write_png(root / "creative.png")
            policy = OperatorPolicy.load(write_json(root / "policy.json", policy_dict(root)))
            manifest = write_json(root / "manifest.json", manifest_dict(image, "0" * 64))
            with self.assertRaises(ValidationError):
                build_create_ads_plan(manifest, policy)

    def test_all_five_release_formats_freeze_exact_assets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            policy = OperatorPolicy.load(write_json(root / "policy.json", policy_dict(root)))
            manifest = write_json(root / "advanced.json", advanced_manifest_dict(root))
            plan = build_create_ads_plan(manifest, policy)
            self.assertEqual(
                [row["format"] for row in plan["ads"]],
                ["single_image", "carousel", "dynamic_image", "flexible_image", "single_video"],
            )
            self.assertEqual(len(plan["ads"][1]["cards"]), 3)
            self.assertEqual(len(plan["ads"][2]["media_assets"]), 3)
            self.assertEqual(plan["ads"][4]["media_kind"], "video")
            verify_plan(plan, policy)


if __name__ == "__main__":
    unittest.main()
