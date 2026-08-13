# Operator contract

## Shared-understanding checkpoint

Before execution, the agent summarizes:

- user outcome and selected campaign objective;
- exact account, campaign, ad set, Page, Instagram identity, and dataset/event;
- existing versus newly created objects;
- targeting, placements, schedule, bid strategy, and attribution setting;
- exact daily/lifetime budget effect and hard cap;
- exact creative files, copy, CTA, destinations, URL tags, and initial status;
- actions that will not occur;
- stop conditions, expected readback, and rollback path.

It asks one question: “Is this the exact operation you intend?” In supervised
mode, the user confirms. In an active execute-within-policy mode, the agent
still prints the checkpoint but does not pause when every field fits the signed
policy.

## Preference handling

Ask about a preference only when it changes the result. Otherwise provide a
recommended default and make it easy to replace:

> I found no naming convention. I propose
> `BRAND_GEO_OBJECTIVE_AUDIENCE_CONCEPT_VERSION` because it stays readable in
> exports and joins cleanly to UTMs. If you already use another convention,
> point me to it; otherwise I will use this one in the draft plan.

Apply the same pattern to UTMs, reporting columns, folder structure, batch size,
and initial PAUSED status. Never infer claims, budget authority, regulated
category, identity, conversion semantics, or launch permission.

## Approval modes

- `supervised`: echo intent before all work; exact plan hash before writes.
- `confirm_writes_only`: reads and local preparation proceed; exact plan hash before writes.
- `execute_within_policy`: an explicit, bounded, expiring policy can satisfy write approval.

Changing approval mode is itself a write to the local authority policy and is
confirmed once. Work history and user familiarity never silently widen it.

## Copy

The agent may draft copy from user-approved product and offer evidence. The CLI
does not call an LLM and does not create marketing claims. Draft copy is
`PROPOSED_NOT_APPROVED` until the user approves the frozen mapping.

## Measurement

The operator can read existing event availability and advise on optimization
readiness. It does not install or edit Pixel, CAPI, consent, GA4, Shopify, or
other website instrumentation. Missing data is `UNAVAILABLE`, not zero.

## Creative formats

Version 0.1.0 can plan, create PAUSED, and read back single-image, carousel,
single-video, dynamic-image, and flexible-image ads. Every source file is
bound by SHA-256 before upload. Catalog/DPA and account-dependent formats are
reported as unsupported prerequisites rather than approximated with another
format.

Run `meta-ads capabilities [--format NAME]` before planning an unfamiliar
format. A recognized-but-unsupported or unknown request must fail locally
without a Meta request. No handler may silently substitute another creative or
delivery product. See `docs/FORMAT_SUPPORT.md`.

## API-load boundary

The policy caps HTTP attempts per run and defines the Meta-usage percentage at
which the operator stops. Receipts include calls by method and endpoint plus
the available Meta rate headers. Ad-account utilization controls over the
lower app percentage when they disagree. Hard account throttle 17/2446079
opens a circuit breaker immediately; it is never amplified by blind retries.
