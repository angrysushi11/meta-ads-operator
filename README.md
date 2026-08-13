# Meta Ads Operator

Release candidate. Not yet published.

A policy-controlled local CLI for creating and operating Meta ads with validated
manifests, paused-by-default creation, bounded activation and budget controls,
idempotency, and verified readback receipts.

The operator freezes an exact plan, checks account and budget boundaries,
requires the configured approval, stops on API pressure or mismatches, and
verifies Meta's readback. Those controls are operating behavior, not the brand
name and not a claim that version 0.1 supports every Meta advertising product.

The CLI is deterministic. Codex or Claude Code provides the conversational
layer: it can inspect an existing account, propose sensible defaults, draft
copy from approved product materials, and turn a natural-language instruction
into a frozen plan. The CLI validates and executes that exact plan.

```text
You + Codex/Claude
       |
       | conversation, current official guidance, proposed copy
       v
approved policy + frozen manifest + plan hash
       |
       v
Meta Ads Operator
       |
       | fresh reads and validated Marketing API calls
       v
Meta: image -> creative -> ad -> exact readback receipt
```

MCP is not required. The production writer uses Meta's Marketing API directly.
An MCP can remain useful as a separate read/reporting interface, but it must
not bypass this operator's policy and receipt gates.

## What it does

- reads accessible Meta businesses, ad accounts, Pages, and linked Instagram identities;
- reads configured and effective status separately;
- inventories only the creative folder the user explicitly supplies;
- validates media hashes, dimensions, destinations, identities, names, and batch limits;
- plans PAUSED campaigns, PAUSED ad sets, and five creative formats;
- uploads single-image, carousel, single-video, dynamic-image, and flexible-image ads sequentially;
- skips exact existing ad names and stops on duplicates or mismatches;
- plans and applies exact pause/activation and bounded daily-budget changes;
- reads insights without converting missing conversions or revenue into zero;
- evaluates conditional rules as proposals before generating exact write plans;
- writes redacted, durable receipts with post-write readback;
- records every HTTP attempt and Meta usage bucket in receipts;
- stops before exceeding a local request budget or configured Meta-usage threshold;
- opens an immediate circuit breaker on Meta code 17/subcode 2446079 instead of retrying it.
- reports whether a requested format is supported, recognized but missing a
  dedicated handler, or unknown—without making a Meta request;

The example safety policy uses resumable 10-ad batches, a 100-call run cap,
and an 80% Meta-usage stop. A one-image creation path uses 10 HTTP attempts in
the normal no-pagination case; larger batches reuse the initial orientation
and remain exact-name idempotent.

The current alpha intentionally excludes billing, payment methods, account
roles, Pixel/CAPI or storefront instrumentation, arbitrary Graph calls,
deletion/archive, and delivery families that still need their own verified
handlers: catalog/DPA, Shops and product tags, collection, lead forms and call
ads, app promotion, partnership, click-to-message, existing-post promotion,
Instant Experience, playable, and AR ads.

If a user asks for Shop ads, catalog/DPA, lead forms, or another unsupported
family, the agent does not guess and the CLI does not substitute a different
format. `meta-ads capabilities --format "shop ads"` explains the missing
handler and current prerequisites, then planning fails locally before any Meta
request. See [docs/FORMAT_SUPPORT.md](docs/FORMAT_SUPPORT.md).

The five included formats use payload families already proven through Meta's
live review/delivery path in the originating implementation. Missing families
can be added as plug-in handlers without rewriting the policy, planning,
idempotency, rate-limit, receipt, or agent layers. This clean-room package must
still begin each new account and each new handler with one PAUSED proof ad
because permissions, objectives, assets, and Meta behavior vary by account.

## Conversational behavior

The agent should be useful before it is inquisitive.

- It inspects an existing account before asking the user to describe facts the account already exposes.
- It recommends a default when the user has no naming, UTM, structure, or reporting preference.
- It groups only the questions that materially change the plan.
- It labels assumptions and asks about contradictions or business facts it cannot verify.
- Before execution, it gives one complete shared-understanding checkpoint.
- It may execute matching future commands without repeated confirmation only after the user explicitly enables a bounded, expiring `execute_within_policy` authority.

See [INSTALL.md](INSTALL.md) and [docs/OPERATOR_CONTRACT.md](docs/OPERATOR_CONTRACT.md).

## Minimal local flow

```bash
python3 --version  # must be 3.11+
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .

meta-ads doctor --policy examples/policy.example.json
meta-ads inventory /absolute/path/to/launch-folder --output inventory.json

meta-ads plan create-ads \
  --policy policy.json \
  --manifest manifest.json \
  --output plan.json

# Only after reviewing the complete plan:
meta-ads apply \
  --policy policy.json \
  --plan plan.json \
  --confirm THE_EXACT_PLAN_SHA256
```

Use [examples/manifest.example.json](examples/manifest.example.json) for a
single image and [examples/manifest-advanced.example.json](examples/manifest-advanced.example.json)
for all five supported creative formats.

Never put a Meta token in a manifest, command argument, chat transcript, Git
file, or receipt. Use `meta-ads auth-store` on macOS or inject
`META_ADS_OPERATOR_ACCESS_TOKEN` from a secret manager for the current process.

## Attribution

This clean-room generalized implementation is informed by the MIT-licensed
[`brandu-mos/konquest-meta-ads-mcp`](https://github.com/brandu-mos/konquest-meta-ads-mcp)
at commit `762c224b060b233b66fb9af8a2f3865303ed757b`. See
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

This project is not affiliated with or endorsed by Meta.
