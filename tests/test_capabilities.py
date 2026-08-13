from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from meta_ads_operator.capabilities import capability_report, format_capability
from meta_ads_operator.errors import ValidationError
from meta_ads_operator.planning import build_create_ads_plan
from meta_ads_operator.policy import OperatorPolicy
from meta_ads_operator.util import sha256_file
from tests.helpers import manifest_dict, policy_dict, write_json, write_png


class CapabilityTests(unittest.TestCase):
    def test_shop_ads_are_recognized_with_prerequisites(self) -> None:
        result = format_capability("shop ads")
        self.assertEqual(result["format"], "shop_ads")
        self.assertEqual(result["state"], "RECOGNIZED_NOT_SUPPORTED")
        self.assertFalse(result["mutates_meta"])
        self.assertIn("published Facebook or Instagram Shop", result["prerequisites"][0])

    def test_dynamic_image_is_explicitly_not_catalog_dpa(self) -> None:
        result = capability_report("dynamic_image")["request"]
        self.assertEqual(result["state"], "SUPPORTED")
        self.assertIn("not a catalog/DPA", result["description"])

    def test_every_recognized_family_has_sources_and_extension_estimate(self) -> None:
        report = capability_report()
        for name, capability in report["recognized_not_supported"].items():
            with self.subTest(name=name):
                self.assertTrue(capability["official_sources"])
                self.assertTrue(capability["estimated_extension"])

    def test_playable_and_ar_are_separate_capabilities(self) -> None:
        self.assertEqual(format_capability("playable")["format"], "playable_ad")
        self.assertEqual(format_capability("ar")["format"], "ar_ad")

    def test_recognized_unsupported_format_fails_during_local_planning(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image = write_png(root / "creative.png")
            policy = OperatorPolicy.load(write_json(root / "policy.json", policy_dict(root)))
            manifest = manifest_dict(image, sha256_file(image))
            manifest["ads"][0]["format"] = "shop_ads"
            path = write_json(root / "manifest.json", manifest)
            with self.assertRaisesRegex(ValidationError, "No Meta request was made"):
                build_create_ads_plan(path, policy)


if __name__ == "__main__":
    unittest.main()
