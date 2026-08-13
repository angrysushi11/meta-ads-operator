# Boundaries

- No billing, payment-method, role, or permission mutation.
- No Pixel, CAPI, consent, website, or storefront instrumentation.
- No raw unrestricted Graph calls.
- No deletion or archive in this alpha.
- Supported ad creatives in 0.1.0: single image, carousel, single video,
  dynamic image, and flexible image.
- Catalog/DPA and account-dependent lead, app-install, partnership,
  click-to-message, Instant Experience, playable, and AR formats remain out.
- No token in chat, shell arguments, files, logs, or receipts.
- New campaigns, ad sets, and ads start PAUSED.
- Account, object IDs, destinations, media roots, names, counts, budgets, and standing authority are policy-scoped.
- Missing status, spend, conversion, value, or attribution data is UNAVAILABLE.
- Exact post-write readback and redacted receipts are mandatory.
