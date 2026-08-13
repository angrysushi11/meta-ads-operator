from __future__ import annotations

import json
import struct
import zlib
from pathlib import Path
from typing import Any


def write_json(path: Path, value: Any) -> Path:
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")
    return path


def write_png(path: Path, width: int = 1080, height: int = 1350) -> Path:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    row = b"\x00" + (b"\xff\xff\xff" * width)
    data = b"\x89PNG\r\n\x1a\n"
    data += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    data += chunk(b"IDAT", zlib.compress(row * height, level=1))
    data += chunk(b"IEND", b"")
    path.write_bytes(data)
    return path


def policy_dict(root: Path) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "graph_version": "v25.0",
        "approval": {"mode": "supervised", "standing_authority": {"actions": [], "expires_at": None}},
        "allowed_actions": [
            "read", "inventory", "validate", "insights", "evaluate_rule",
            "create_campaign", "create_ad_set", "create_ads", "set_status", "set_budget",
        ],
        "scope": {
            "ad_account_ids": ["111111"],
            "campaign_ids": ["222222"],
            "ad_set_ids": ["333333"],
            "ad_ids": ["444444"],
            "page_ids": ["555555"],
            "instagram_user_ids": ["666666"],
            "destination_hosts": ["shop.example.com"],
            "media_roots": [str(root)],
        },
        "limits": {
            "max_ads_per_batch": 5,
            "max_daily_budget_minor": 5000,
            "max_budget_increase_percent": 20,
            "max_http_attempts_per_run": 100,
            "stop_at_usage_percent": 85,
            "currency_minor_exponent": 2,
        },
        "invariants": {
            "new_ads_must_start_paused": True,
            "parents_must_be_paused_for_create": True,
            "max_spend_today_minor_for_create": 0,
        },
        "naming_patterns": {"campaign": "[A-Z0-9_]+", "ad_set": "[A-Z0-9_]+", "ad": "[A-Z0-9_]+"},
        "receipt_dir": str(root / "receipts"),
    }


def manifest_dict(media_path: Path, sha256: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "ad_account_id": "111111",
        "campaign_id": "222222",
        "ad_set_id": "333333",
        "identity": {"page_id": "555555", "instagram_user_id": "666666"},
        "ads": [
            {
                "name": "BRAND_C01_V01",
                "creative_name": "BRAND_C01_V01_CREATIVE",
                "media_path": str(media_path),
                "media_sha256": sha256,
                "primary_text": "Approved primary text",
                "headline": "Approved headline",
                "description": "Approved description",
                "cta": "LEARN_MORE",
                "destination_url": "https://shop.example.com/products/example",
                "url_tags": "utm_source=meta&utm_medium=paid_social&utm_content=c01_v01",
                "status": "PAUSED",
            }
        ],
    }


def advanced_manifest_dict(root: Path) -> dict[str, Any]:
    image_a = write_png(root / "a.png")
    image_b = write_png(root / "b.png", 1200, 1500)
    image_c = write_png(root / "c.png", 1080, 1080)
    video = root / "video.mp4"
    video.write_bytes(b"release-test-video-bytes")

    def media(path: Path) -> dict[str, str]:
        from meta_ads_operator.util import sha256_file

        return {"media_path": str(path), "media_sha256": sha256_file(path)}

    common = {
        "primary_text": "Approved primary text",
        "headline": "Approved headline",
        "description": "Approved description",
        "cta": "LEARN_MORE",
        "destination_url": "https://shop.example.com/products/example",
        "url_tags": "utm_source=meta&utm_medium=paid_social&utm_campaign=test",
        "status": "PAUSED",
    }
    return {
        "schema_version": 1,
        "ad_account_id": "111111",
        "campaign_id": "222222",
        "ad_set_id": "333333",
        "identity": {"page_id": "555555", "instagram_user_id": "666666"},
        "ads": [
            {"name": "SINGLE_IMAGE", "format": "single_image", **media(image_a), **common},
            {
                "name": "CAROUSEL_AD",
                "format": "carousel",
                **common,
                "cards": [
                    {**media(image_a), "headline": "Card one", "description": "One"},
                    {**media(image_b), "headline": "Card two", "description": "Two"},
                    {**media(image_c), "headline": "Card three", "description": "Three"},
                ],
            },
            {
                "name": "DYNAMIC_IMAGE",
                "format": "dynamic_image",
                **common,
                "media": [media(image_a), media(image_b), media(image_c)],
                "bodies": ["Body one", "Body two"],
                "headlines": ["Title one", "Title two"],
                "descriptions": ["Description"],
            },
            {
                "name": "FLEXIBLE_IMAGE",
                "format": "flexible_image",
                **common,
                "media": [media(image_a), media(image_b), media(image_c)],
                "bodies": ["Body one", "Body two"],
                "headlines": ["Title one", "Title two"],
                "descriptions": ["Description"],
            },
            {"name": "SINGLE_VIDEO", "format": "single_video", **media(video), **common},
        ],
    }
