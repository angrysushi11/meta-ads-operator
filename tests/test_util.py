from __future__ import annotations

import unittest

from guarded_meta_ads.util import sanitize


class UtilTests(unittest.TestCase):
    def test_secrets_are_redacted(self) -> None:
        result = sanitize({"access_token": "EA" + "A" * 50, "nested": {"client_secret": "abc"}})
        self.assertEqual(result["access_token"], "[REDACTED]")
        self.assertEqual(result["nested"]["client_secret"], "[REDACTED]")


if __name__ == "__main__":
    unittest.main()
