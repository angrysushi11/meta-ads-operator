# Format support and expansion roadmap

Verified against current official Meta surfaces: 2026-08-13. Meta can change
payloads, availability, permissions, country eligibility, and account access
independently of this repository. Engineering estimates below are planning
ranges, not Meta guarantees. They assume the user already has the required
eligible assets; waiting for Meta review or external authorization is excluded.

## The word “format” hides three different things

Meta Ads Manager mixes three axes in one interface:

1. **Creative layout** — image, video, carousel, flexible, or multi-asset.
2. **Destination/product** — website, catalog, Shop, app, message thread,
   Instant Form, call, Instant Experience, or creator content.
3. **Delivery configuration** — objective, optimization event, placements,
   identity, audience, budget, and attribution.

Version 0.1 supports the common creative layouts for website campaigns. A new
crop for Reels or Stories is an asset/placement extension. A lead form or app
campaign is different: it adds new Meta objects, permissions, destinations,
eligibility checks, and verification rules. That is why “support every ad
type” is not one extra API switch.

## Supported in 0.1

| Manifest value | Public description | Important boundary |
| --- | --- | --- |
| `single_image` | one image | website-style creative |
| `carousel` | 2–10 independently verified cards | non-catalog carousel |
| `single_video` | one uploaded and processed video | website-style creative |
| `dynamic_image` | supplied multi-asset image/copy feed | not catalog/DPA |
| `flexible_image` | supplied flexible image/copy feed | not catalog/DPA |

The core already handles policy checks, frozen plans, confirmation, rate-limit
protection, idempotency, receipts, and exact Meta readback. Future families add
handlers to that core; they do not require a rewrite.

## Why the remaining families need dedicated handlers

| Family | What is different | Planning estimate |
| --- | --- | --- |
| Existing/boosted post | Uses a Page/Instagram post ID, ownership, eligibility, and objective/placement compatibility instead of a new unpublished creative. | 1–2 days |
| Call ads | Adds a verified phone destination, call CTA, scheduling, optimization, and call attribution. Meta explicitly says the Marketing API can publish call ads. | 1–2 days |
| Instant-form lead ads | Adds an Instant Form object, questions, privacy policy, Page terms/access, lead retrieval, and possibly CRM/CAPI feedback. | 1–3 days |
| Click-to-message | Uses Messenger, Instagram Direct, or WhatsApp identity plus destination-specific templates and optimization. Each destination needs its own proof. | 1–3 days per destination |
| Partnership ads | Requires a real creator/business relationship, creator authorization, eligible content, and permission readback. Code cannot manufacture that authorization. | 2–4 days after authorization exists |
| Product-tagged ads | Adds catalog item identity, tag eligibility, Page/Instagram relationships, and destination verification. A Shop is not always required, but catalog items are. | 2–4 days |
| App-promotion/install ads | Adds a registered app, App Store/Google Play record, app permissions, SDK or MMP events, app optimization, and mobile measurement rules. | 2–5 days |
| Instant Experience | Adds a separate component/document tree, asset graph, validation, publishing, and document readback. | 2–4 days |
| Catalog/DPA | Selects items from a populated catalog/product set and depends on item IDs matching website/app event `content_ids`, dataset/pixel readiness, permissions, and optimization. | 3–7 days |
| Shops ads | Adds an eligible published Shop, commerce account, catalog/product sets, connected identities, supported country/destination, and commerce eligibility. | 3–7 days |
| Collection ads | Combines a cover asset with catalog products and usually an Instant Experience; it reuses both handler foundations. | 3–6 days |
| Playable ads | Adds a registered app/store destination, lead-in video, interactive demo bundle, specialized validation, and eligible placements. | 3–7 days |
| AR ads | Availability and effect tooling must be re-verified first; specialized effect assets and eligibility make this an account/product-dependent integration. | research spike, then likely 3–7+ days |

The fastest next additions are existing-post ads, call ads, and Instant Forms.
For an e-commerce operator, catalog/DPA + product tags + Shops + collection is
the highest-value bundle, but it is also the largest because the shared
catalog/commerce/event foundation has to be correct.

## Official-source grounding

- Meta's [Sales ads guidance](https://www.facebook.com/business/ads/ad-objectives/sales)
  says catalog ads require creating a catalog and adding inventory. Meta's
  official Marketing API Postman workspace exposes separate
  [catalog and product-set discovery](https://www.postman.com/meta/facebook-marketing-api/request/0w6p8rh/get-catalog-and-product-set).
- Meta's [Shops documentation](https://www.facebook.com/business/shops)
  says a Shop is required for Shops ads, while ads with product tags can exist
  without a Shop. Meta's [Advantage+ sales setup](https://www.facebook.com/business/ads/meta-advantage/advantage-plus-shopping-ads)
  can require a pixel, app, or commerce account depending on destination.
- Meta's [lead-form guidance](https://www.facebook.com/business/ads/ad-objectives/lead-generation/lead-ads-with-forms)
  distinguishes Instant Forms and website forms and describes separate CRM/CAPI
  feedback for conversion leads.
- Meta's [call-ad guidance](https://www.facebook.com/business/ads/ad-objectives/lead-generation/lead-ads-with-calling)
  explicitly names the Marketing API as a publishing route.
- Meta says [click-to-message ads](https://www.facebook.com/business/ads/click-to-message-ads)
  can route to Messenger, Instagram Direct, or WhatsApp.
- Meta's [app-campaign guidance](https://www.facebook.com/business/ads/meta-advantage-plus/app-campaigns)
  ties app optimization to the Meta SDK or a mobile measurement partner.
- Meta's [partnership-ads surface](https://www.facebook.com/business/ads/creator-marketplace)
  makes creator content and permission status explicit prerequisites.
- Meta describes [playable ads](https://www.facebook.com/business/ads/playable-ad-format)
  as app-install units comprising a lead-in video, interactive demo, and store
  CTA. Meta's [video-format guide](https://www.facebook.com/business/ads/video-ad-format)
  identifies collection and Instant Experience as distinct immersive products.

## What happens when a user asks for something not yet supported

```bash
meta-ads capabilities --format "shop ads"
```

The operator returns one of three local states without making a Meta request:

- `SUPPORTED`: build a deterministic plan with the existing handler.
- `RECOGNIZED_NOT_SUPPORTED`: explain the prerequisites and estimated handler
  effort; do not silently turn it into a basic image ad.
- `UNKNOWN`: clarify the exact current Meta product and inspect official
  documentation before implementation.

This behavior lets version 0.1 ship honestly. An agent can understand a request
for a missing family, explain the gap, and guide the user; it cannot publish that
family until its handler has passed the extension gate.

## Extension gate

Adding a family later means:

1. refresh current official prerequisites and account eligibility;
2. add its typed manifest/schema and capability discovery;
3. implement its object/payload builder and policy locks;
4. add deterministic success, mismatch, idempotency, and API-pressure tests;
5. add exact post-write readback and redacted receipts;
6. run one separately authorized PAUSED proof in an eligible account;
7. document the proven fields and account-dependent limitations.

The release architecture is deliberately built for that sequence. Missing
families are versioned modules, not a dead end and not a reason to hold 0.1.
