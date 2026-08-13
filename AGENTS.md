# Agent operating contract

Use this repository as a deterministic Meta Ads control plane. Do not bypass it
with browser clicks, raw Graph calls, or a different writer unless the user
explicitly changes the scope.

## Conversation

1. Inspect existing account evidence before asking the user to repeat it.
2. Infer low-risk defaults and label them. For naming, UTMs, structure, or
   reporting columns, ask whether the user has a preference; if not, recommend
   one concrete convention.
3. Group only questions that materially alter business outcome, targeting,
   budget, claims, identity, destination, or risk.
4. When copy is missing, offer supplied copy, agent-proposed copy from approved
   product materials, or reuse of an approved library. Never invent product facts.
5. Before execution, show one complete shared-understanding checkpoint: exact
   account and objects, action, copy/media mapping, status, budget effect,
   destinations/UTMs, exclusions, stop conditions, and rollback.

## Authority

- Default to `supervised`.
- A user's planning or review request is not live-write approval.
- For a write, create an immutable plan and require its exact hash.
- The user may enable `execute_within_policy`; confirm that mode change once,
  encode exact actions/scope/caps/expiry, and never learn broader authority from history.
- Never treat unavailable conversion, revenue, status, spend, or readback fields as zero.

## Guidance

For current campaign recommendations, browse current official Meta sources.
Separate `Meta says`, `Operator recommends`, and `User decides`, with URLs and
verification dates. Cached examples are not current guidance.

## Safety

Never request a token in chat. Use the OS credential prompt or process-level
secret injection. Run tests, `guarded-meta doctor`, a dry plan, and a one-ad
PAUSED proof before batch widening. Stop on any mismatch. Do not mutate billing,
payments, roles, instrumentation, websites, deletion/archive, or raw Graph APIs.

