---
name: meta-ads-operator
description: Plan, create, inspect, pause, activate, and report on Meta/Facebook/Instagram ads through the local Meta Ads Operator CLI. Use when a user asks to install the operator, connect or orient a Meta account, inventory a creative folder, propose or map ad copy, create campaigns/ad sets/ads, change status or bounded budgets, inspect insights, evaluate performance rules, or operate Meta ads in natural language.
---

# Meta Ads Operator

Use the agent for conversation and recommendations. Use `meta-ads` for
deterministic validation, live writes, and receipts.

## Start

1. Locate the repository and read its `AGENTS.md`.
2. Run `python scripts/check_operator.py` from this skill when installation state is uncertain.
3. Classify the request as read, local preparation, or live write.
4. For existing accounts, run read-only discovery before asking the user to describe the account.
5. For any unfamiliar format, run `meta-ads capabilities --format NAME`
   before proposing a plan. If it is recognized but unsupported, explain the
   prerequisite handler and stop. Never substitute another format.

## Converse efficiently

- Ask only questions whose answers materially change the result.
- Offer one recommended default for missing naming, UTM, reporting, structure, or folder preferences. Invite the user's convention without forcing a decision.
- Group material questions instead of asking them one at a time.
- Treat account inspection as a hypothesis: legacy objects may be stale.
- Do not infer product claims, regulated category, budget authority, identity, conversion semantics, or launch permission.
- If copy is missing, offer: supplied copy; proposed copy from approved product evidence; or reuse of an approved library. Mark generated copy `PROPOSED_NOT_APPROVED`.

Before execution, present one complete shared-understanding checkpoint covering
exact objects, action, statuses, budget effect, targeting, identities,
media-copy mapping, destinations/UTMs, exclusions, stop conditions, and
rollback. In supervised mode, wait for confirmation.

## Use approval modes correctly

- `supervised` is the default.
- `confirm_writes_only` lets reads and local work proceed without pausing.
- `execute_within_policy` is valid only after the user explicitly confirms an exact account/action/cap/expiry policy. History never widens authority.

All writes require the exact immutable plan hash unless a current standing
policy explicitly covers them. Technical gates and readback remain mandatory
in every mode.

## Execute

1. Inventory only explicitly allowed files/folders.
2. Freeze approved media/copy/identity/destination mappings in a manifest.
3. Run `meta-ads plan ...` and show the plan summary plus hash.
4. For current strategic recommendations, browse official Meta sources and label `Meta says`, `Operator recommends`, and `User decides`.
5. Apply only through `meta-ads apply`; never paste tokens into chat or command arguments.
6. Read the durable receipt and verify configured/effective status, IDs, media/copy/identity/destination/UTM fidelity, budget/spend guards, and errors.
7. Read `api_usage` in the receipt. Stop on the local request cap, configured
   usage threshold, hard account throttle, or first mismatch. Never interpret
   unavailable conversion or revenue data as zero.

Read `references/workflow.md` for command examples and `references/boundaries.md`
for exclusions and safety rules.
