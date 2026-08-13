from __future__ import annotations

from typing import Any


SUPPORTED_CREATIVE_FORMATS = {
    "single_image": {
        "display_name": "Single image",
        "description": "One image, one destination, and one approved copy mapping.",
    },
    "carousel": {
        "display_name": "Carousel",
        "description": "Two to ten image cards with independently verified card destinations.",
    },
    "single_video": {
        "display_name": "Single video",
        "description": "One uploaded video with bounded processing checks before creative creation.",
    },
    "dynamic_image": {
        "display_name": "Multi-asset image",
        "description": (
            "A non-catalog asset-feed creative using supplied images and copy variants. "
            "This is not a catalog/DPA or Shops ad."
        ),
    },
    "flexible_image": {
        "display_name": "Flexible image",
        "description": "A flexible-format image creative using supplied images and copy variants.",
    },
}


RECOGNIZED_NOT_SUPPORTED = {
    "catalog_dpa": {
        "display_name": "Advantage+ catalog / dynamic product ad",
        "reason": "This format selects products from a Meta catalog and needs a dedicated catalog handler.",
        "prerequisites": [
            "accessible commerce product catalog",
            "eligible and populated product set",
            "catalog item IDs aligned with website or app event content IDs",
            "dataset/pixel and optimization-event readiness",
            "catalog permissions and account eligibility",
        ],
        "official_sources": [
            "https://www.facebook.com/business/ads/ad-objectives/sales",
            "https://www.postman.com/meta/facebook-marketing-api/request/0w6p8rh/get-catalog-and-product-set",
        ],
    },
    "shop_ads": {
        "display_name": "Facebook or Instagram Shops ad",
        "reason": "Shops ads depend on an eligible published Shop and commerce assets, not only a creative payload.",
        "prerequisites": [
            "eligible and published Facebook or Instagram Shop",
            "Commerce Manager account and approved catalog inventory",
            "correct Page, Instagram, commerce-account, catalog, and product-set relationships",
            "supported commerce-account country and destination configuration",
            "catalog item IDs aligned with website or app event content IDs",
        ],
        "official_sources": [
            "https://www.facebook.com/business/shops",
        ],
    },
    "product_tagged_ads": {
        "display_name": "Ad with product tags",
        "reason": "Product tags require catalog/product identity handling and account eligibility checks.",
        "prerequisites": [
            "approved catalog items",
            "eligible Page or Instagram identity",
            "product-tag permissions and destination validation",
        ],
        "official_sources": [
            "https://www.facebook.com/business/shops",
        ],
    },
    "lead_form": {
        "display_name": "Instant-form lead ad",
        "reason": "Lead forms have their own form object, privacy-policy, questions, and lead-access requirements.",
        "prerequisites": [
            "eligible Page",
            "approved instant form and privacy policy",
            "lead-access and data-handling configuration",
        ],
        "official_sources": [
            "https://www.facebook.com/business/ads/meta-advantage-plus/leads",
        ],
    },
    "app_install": {
        "display_name": "App-install ad",
        "reason": "App ads depend on an app, store destination, SDK/events, and app-specific optimization configuration.",
        "prerequisites": [
            "registered app and store destination",
            "app asset permissions",
            "SDK or app-event readiness",
            "app-specific campaign and ad-set configuration",
        ],
        "official_sources": [],
    },
    "partnership_ad": {
        "display_name": "Partnership ad",
        "reason": "Partnership ads require an eligible creator/partner identity and explicit partnership permissions.",
        "prerequisites": [
            "eligible partner identity",
            "partnership authorization",
            "supported post or creative identity",
        ],
        "official_sources": [],
    },
    "click_to_message": {
        "display_name": "Click-to-message ad",
        "reason": "Messaging destinations require app-specific identity, destination, and thread configuration.",
        "prerequisites": [
            "eligible messaging destination",
            "Page or business identity access",
            "message template and destination validation",
        ],
        "official_sources": [],
    },
    "instant_experience": {
        "display_name": "Instant Experience",
        "reason": "Instant Experience uses a separate canvas/document object and component tree.",
        "prerequisites": ["eligible Page", "validated Instant Experience document and assets"],
        "official_sources": [],
    },
    "playable_or_ar": {
        "display_name": "Playable or AR ad",
        "reason": "Playable and AR formats require specialized assets and account-dependent eligibility.",
        "prerequisites": ["eligible account", "specialized validated asset bundle"],
        "official_sources": [],
    },
}


ALIASES = {
    "image": "single_image",
    "video": "single_video",
    "multi_asset_image": "dynamic_image",
    "dynamic_creative": "dynamic_image",
    "dpa": "catalog_dpa",
    "dynamic_product_ad": "catalog_dpa",
    "dynamic_product_ads": "catalog_dpa",
    "catalog_ad": "catalog_dpa",
    "catalog_ads": "catalog_dpa",
    "shop": "shop_ads",
    "shop_ad": "shop_ads",
    "shops_ad": "shop_ads",
    "product_tag": "product_tagged_ads",
    "product_tags": "product_tagged_ads",
    "lead": "lead_form",
    "instant_form": "lead_form",
    "app": "app_install",
    "partnership": "partnership_ad",
    "message": "click_to_message",
    "messaging": "click_to_message",
    "canvas": "instant_experience",
    "playable": "playable_or_ar",
    "ar": "playable_or_ar",
}


def normalize_format(value: str) -> str:
    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
    return ALIASES.get(normalized, normalized)


def format_capability(value: str) -> dict[str, Any]:
    requested = value
    normalized = normalize_format(value)
    if normalized in SUPPORTED_CREATIVE_FORMATS:
        return {
            "requested": requested,
            "format": normalized,
            "state": "SUPPORTED",
            "mutates_meta": False,
            **SUPPORTED_CREATIVE_FORMATS[normalized],
            "next_step": "Build and review an immutable PAUSED proof plan before any live write.",
        }
    if normalized in RECOGNIZED_NOT_SUPPORTED:
        return {
            "requested": requested,
            "format": normalized,
            "state": "RECOGNIZED_NOT_SUPPORTED",
            "mutates_meta": False,
            **RECOGNIZED_NOT_SUPPORTED[normalized],
            "next_step": "Use or add a dedicated handler only after its prerequisites and live proof are verified.",
        }
    return {
        "requested": requested,
        "format": normalized,
        "state": "UNKNOWN",
        "mutates_meta": False,
        "reason": "The operator does not recognize this format name and will not guess or substitute another format.",
        "next_step": "Clarify the exact Meta format and inspect current official prerequisites before implementation.",
    }


def capability_report(requested_format: str | None = None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema_version": 1,
        "operator_version": "0.1.0",
        "live_mutation_performed": False,
        "supported": {
            key: {"state": "SUPPORTED", **value}
            for key, value in sorted(SUPPORTED_CREATIVE_FORMATS.items())
        },
        "recognized_not_supported": {
            key: {"state": "RECOGNIZED_NOT_SUPPORTED", **value}
            for key, value in sorted(RECOGNIZED_NOT_SUPPORTED.items())
        },
        "unsupported_behavior": (
            "Fail locally before any Meta request; explain the missing handler and prerequisites; "
            "never silently convert to another format."
        ),
    }
    if requested_format is not None:
        result["request"] = format_capability(requested_format)
    return result


def unsupported_format_message(value: str, *, ad_name: str) -> str:
    capability = format_capability(value)
    if capability["state"] == "RECOGNIZED_NOT_SUPPORTED":
        prerequisites = "; ".join(capability.get("prerequisites", []))
        return (
            f"Recognized but unsupported creative format for {ad_name}: {value}. "
            f"{capability['reason']} Prerequisites: {prerequisites}. "
            "No Meta request was made and no substitute format will be used. "
            "Run `guarded-meta capabilities --format " + capability["format"] + "` for the full report."
        )
    return (
        f"Unknown creative format for {ad_name}: {value}. "
        f"Supported: {sorted(SUPPORTED_CREATIVE_FORMATS)}. "
        "No Meta request was made and no substitute format will be used. "
        "Run `guarded-meta capabilities` to inspect the current surface."
    )
