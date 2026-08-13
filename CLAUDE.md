# Claude Code instructions

Read `AGENTS.md` and follow it as the controlling operating contract. Use the
local `meta-ads` CLI for deterministic plans and writes. Treat natural
language as an intent to clarify and plan, not as permission to improvise a
live Meta mutation.

Be conversational without turning onboarding into a questionnaire: inspect
first, recommend defaults, group material questions, and show one complete
shared-understanding checkpoint before execution. Never ask for or print a
Meta token. Never bypass policy, plan-hash, idempotency, or readback gates.

For Shop/catalog, lead, app, partnership, messaging, Instant Experience, or
another unfamiliar family, run `meta-ads capabilities --format NAME` and
honor its result. Do not improvise raw Graph calls or silently replace the
requested format.
