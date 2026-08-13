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
        "estimated_extension": "3-7 engineering days once an eligible populated catalog and event mapping are available",
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
            "https://www.facebook.com/business/ads/meta-advantage/advantage-plus-shopping-ads",
        ],
        "estimated_extension": "3-7 engineering days after Shop, commerce-account, catalog, and country eligibility are verified",
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
        "estimated_extension": "2-4 engineering days after catalog items and product-tag eligibility are verified",
    },
    "collection_ads": {
        "display_name": "Collection ad",
        "reason": "Collection ads combine a cover asset with a product set and usually an Instant Experience destination.",
        "prerequisites": [
            "accessible populated catalog and product set",
            "eligible Page and commerce assets",
            "validated cover image or video",
            "validated Instant Experience or supported collection destination",
        ],
        "official_sources": [
            "https://www.facebook.com/business/ads/video-ad-format",
            "https://www.facebook.com/business/ads/ad-objectives/sales",
        ],
        "estimated_extension": "3-6 engineering days, sharing catalog and Instant Experience foundations",
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
            "https://www.facebook.com/business/ads/ad-objectives/lead-generation/lead-ads-with-forms",
        ],
        "estimated_extension": "1-3 engineering days after the Page, privacy policy, form fields, and lead access are available",
    },
    "call_ads": {
        "display_name": "Call ad",
        "reason": "Call ads use a telephone destination, call-specific scheduling, optimization, and attribution configuration.",
        "prerequisites": [
            "eligible Page and verified business phone destination",
            "call schedule and supported country configuration",
            "call-specific campaign, ad-set, CTA, and attribution settings",
        ],
        "official_sources": [
            "https://www.facebook.com/business/ads/ad-objectives/lead-generation/lead-ads-with-calling",
        ],
        "estimated_extension": "1-2 engineering days after the verified phone and account eligibility are available",
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
        "official_sources": [
            "https://www.facebook.com/business/ads/meta-advantage-plus/app-campaigns",
        ],
        "estimated_extension": "2-5 engineering days after the registered app, store records, and app events are ready",
    },
    "partnership_ad": {
        "display_name": "Partnership ad",
        "reason": "Partnership ads require an eligible creator/partner identity and explicit partnership permissions.",
        "prerequisites": [
            "eligible partner identity",
            "partnership authorization",
            "supported post or creative identity",
        ],
        "official_sources": [
            "https://www.facebook.com/business/ads/creator-marketplace",
        ],
        "estimated_extension": "2-4 engineering days after creator authorization and eligible content exist",
    },
    "click_to_message": {
        "display_name": "Click-to-message ad",
        "reason": "Messaging destinations require app-specific identity, destination, and thread configuration.",
        "prerequisites": [
            "eligible messaging destination",
            "Page or business identity access",
            "message template and destination validation",
        ],
        "official_sources": [
            "https://www.facebook.com/business/ads/click-to-message-ads",
        ],
        "estimated_extension": "1-3 engineering days per destination family after Messenger, Instagram Direct, or WhatsApp access is verified",
    },
    "existing_post": {
        "display_name": "Existing-post ad",
        "reason": "Promoting an existing Facebook or Instagram post uses post identity, ownership, and ad-eligibility rather than a new unpublished creative.",
        "prerequisites": [
            "eligible Page or Instagram post",
            "verified identity ownership and permissions",
            "placement and objective compatibility",
        ],
        "official_sources": [
            "https://www.facebook.com/business/ads/video-ad-format",
        ],
        "estimated_extension": "1-2 engineering days after eligible post readback is available",
    },
    "instant_experience": {
        "display_name": "Instant Experience",
        "reason": "Instant Experience uses a separate canvas/document object and component tree.",
        "prerequisites": ["eligible Page", "validated Instant Experience document and assets"],
        "official_sources": [
            "https://www.facebook.com/business/ads/video-ad-format",
        ],
        "estimated_extension": "2-4 engineering days because the component document needs its own schema, asset graph, and readback",
    },
    "playable_ad": {
        "display_name": "Playable ad",
        "reason": "Playable ads are app-promotion units with a lead-in video, interactive demo bundle, and store destination.",
        "prerequisites": ["eligible app-ad account", "registered app and store destination", "validated lead-in video and playable bundle"],
        "official_sources": [
            "https://www.facebook.com/business/ads/playable-ad-format",
        ],
        "estimated_extension": "3-7 engineering days after a conforming playable asset bundle is available",
    },
    "ar_ad": {
        "display_name": "AR ad",
        "reason": "AR ads require a currently supported effect/product surface, specialized assets, and account-dependent eligibility.",
        "prerequisites": ["eligible account and current AR product surface", "specialized validated effect assets"],
        "official_sources": [
            "https://www.facebook.com/business/ads/video-ad-format",
        ],
        "estimated_extension": "research spike first, then likely 3-7+ engineering days; current availability must be re-verified before implementation",
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
    "collection": "collection_ads",
    "lead": "lead_form",
    "instant_form": "lead_form",
    "call": "call_ads",
    "call_ad": "call_ads",
    "app": "app_install",
    "partnership": "partnership_ad",
    "message": "click_to_message",
    "messaging": "click_to_message",
    "boosted_post": "existing_post",
    "post": "existing_post",
    "canvas": "instant_experience",
    "playable": "playable_ad",
    "ar": "ar_ad",
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
            "Run `meta-ads capabilities --format " + capability["format"] + "` for the full report."
        )
    return (
        f"Unknown creative format for {ad_name}: {value}. "
        f"Supported: {sorted(SUPPORTED_CREATIVE_FORMATS)}. "
        "No Meta request was made and no substitute format will be used. "
        "Run `meta-ads capabilities` to inspect the current surface."
    )
