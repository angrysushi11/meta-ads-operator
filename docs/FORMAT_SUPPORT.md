# Format support and capability negotiation

Verified: 2026-08-13. Current official-source links are included below; Meta
can change account eligibility and payload requirements independently of this
repository.

## Why the operator does not claim every Meta format

“Format” can mean either a creative layout or an entire delivery product.
Single-image, carousel, and video ads primarily change creative payloads.
Shops ads, catalog/DPA, lead forms, app-install, partnership, messaging, and
Instant Experience ads introduce other Meta objects, permissions, eligibility,
destinations, and data relationships.

Version 0.1.0 supports only five payload families that had a bounded live proof
in the originating private implementation and deterministic coverage in this
clean package:

| Manifest value | Public description | Catalog/Shop product selection |
| --- | --- | --- |
| `single_image` | one image | no |
| `carousel` | 2–10 image cards | no |
| `single_video` | one video | no |
| `dynamic_image` | supplied multi-asset image/copy feed | no |
| `flexible_image` | supplied flexible image/copy feed | no |

The `dynamic_image` name does **not** mean dynamic product ads. It never reads
products from a catalog.

## Shops and catalog ads

Meta says that a Shop is required for Shops ads, while ordinary ads with
product tags can be available without a Shop. Shops also depend on Commerce
Manager, approved catalog inventory, connected identities, country eligibility,
and product relationships. See Meta's current
[business Shops surface](https://www.facebook.com/business/shops),
then verify the commerce account's current country eligibility in Commerce
Manager before planning.

Advantage+ catalog ads require a populated catalog and product inventory. Meta's
[Sales ads guidance](https://www.facebook.com/business/ads/ad-objectives/sales)
describes catalog inventory as a prerequisite, and Meta's official Marketing
API Postman workspace exposes separate catalog/product-set discovery calls:
[Get catalog and product set](https://www.postman.com/meta/facebook-marketing-api/request/0w6p8rh/get-catalog-and-product-set).

Because those prerequisites cannot be inferred from a creative folder, v0.1.0
does not approximate a Shops or catalog ad with an ordinary image ad.

## What happens when a user requests another format

Run:

```bash
guarded-meta capabilities --format "shop ads"
```

The operator returns one of three states without making a Meta request:

- `SUPPORTED`: use the existing deterministic handler.
- `RECOGNIZED_NOT_SUPPORTED`: name the missing handler and prerequisites.
- `UNKNOWN`: clarify the exact current Meta product before implementation.

Planning an unsupported format fails locally. The operator never silently
substitutes a single-image ad or improvises an unverified Graph payload.

## Extension rule

Add a new live-write handler only after:

1. documenting its current official object and permission prerequisites;
2. adding a typed manifest/schema and policy locks;
3. covering payload and exact readback behavior with deterministic tests;
4. running one separately authorized PAUSED live proof in an eligible account;
5. recording the proven fields and account-dependent limitations.

Catalog/DPA and Shops are the recommended next bundle because they unlock the
largest missing e-commerce surface. They are not part of v0.1.0.
