# Security model

## Never commit

- Meta access tokens, app secrets, authorization codes, or PKCE values;
- real account, campaign, ad-set, Page, Instagram, pixel, or dataset IDs unless the repository itself is private and the user explicitly accepts that disclosure;
- private media, copy, receipts, customer data, or absolute home-directory paths;
- exported browser sessions, Keychain values, `.env`, or shell history.

## Built-in boundaries

- Tokens are read from process environment or an OS credential store and are never accepted as CLI arguments.
- Output and receipts redact token- and secret-shaped fields.
- Every write plan is bound to a policy hash and immutable plan hash.
- The natural-language layer has no raw Graph command.
- New objects start PAUSED.
- Media is restricted to explicitly allowed roots.
- Destinations, accounts, identities, parents, counts, budgets, and names are policy-scoped.
- Exact-name idempotency prevents blind duplicate retries.
- Post-write readback is mandatory; unavailable data fails closed when it is a required gate.
- Deletion and archive are absent from this alpha.

## Before each release

Run the test suite, the repository privacy scan, an independent secret scanner,
and a full Git-history scan. Review every example, documentation file, fixture,
receipt path, and generated package. A source release never authorizes a live
Meta write; account access and ad execution remain separate user decisions.
