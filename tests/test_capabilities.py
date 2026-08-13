from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from guarded_meta_ads.capabilities import capability_report, format_capability
from guarded_meta_ads.errors import ValidationError
from guarded_meta_ads.planning import build_create_ads_plan
from guarded_meta_ads.policy import OperatorPolicy
from guarded_meta_ads.util import sha256_file
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
