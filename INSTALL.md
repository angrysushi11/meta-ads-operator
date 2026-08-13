# Install and onboard

Status: release-candidate instructions; repository URL is assigned at publication.

## The easy route: give this repository to an agent

Use Codex in the ChatGPT desktop workspace, Codex CLI, or Claude Code. A normal
chat window without repository access and command execution cannot install the
tool locally.

Tell the agent:

> Install this repository locally. Run its tests and doctor command. Do not ask
> me for a Meta token in chat. Guide me through the human-only Meta steps, then
> perform read-only discovery. Propose sensible defaults and ask only the
> questions that materially change the campaign. Before any write, show me one
> complete summary of what you understood and the immutable plan hash.

The agent can clone/open the repository, create a Python virtual environment,
install it, run diagnostics, copy placeholder files, and guide onboarding. The
human must handle Meta terms, 2FA, business/app verification, asset approval,
and secret entry.

## Manual installation

Requirements: Python 3.11+, Git, internet access for Meta operations, and your
own Meta developer app/access token/asset permissions.

First verify the runtime. Some macOS installations still map `python3` to 3.9;
the agent must locate or install Python 3.11+ before creating the virtual environment.

```bash
git clone REPOSITORY_URL guarded-meta-ads-operator
cd guarded-meta-ads-operator
python3 --version  # stop unless this is 3.11+
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
python -m unittest discover -s tests -v
guarded-meta doctor
```

For Codex, ask the agent to install the bundled skill from
`skills/guarded-meta-ads-operator` into its local skills directory and restart
Codex after validation. Claude Code reads the repository's `CLAUDE.md` and
`AGENTS.md` directly. The operator code remains the same for both agents.

No hosted server or product domain is required for this local CLI. Meta may
separately require public privacy, terms, or data-deletion URLs for your
developer app. Ads need a real destination URL.

## Secure token setup

On macOS:

```bash
guarded-meta auth-store
```

The prompt is hidden and stores the token in macOS Keychain. On another
platform, inject `GUARDED_META_ACCESS_TOKEN` through your own secret manager
for the process. Do not write it to `.env` unless you fully understand and
accept the local security tradeoff; `.env` is Git-ignored but remains plaintext.

## Existing-account onboarding

Run read-only discovery before interviewing the user:

```bash
guarded-meta discover > discovery.json
```

The agent should turn discovery into a provisional account hypothesis: what
appears to be promoted, through which destinations, with which identities,
objectives, audiences, budgets, and usable events. Legacy objects may be stale,
so the user confirms or corrects the hypothesis.

Then create a local policy from `examples/policy.example.json`. The policy
locks account/object identities, allowed destinations and media roots, actions,
budget ceilings, batch size, naming patterns, and approval mode.

## Creatives and copy

Point the agent to one explicit creative folder. It must not scan the entire
computer. If copy is absent, it offers three routes:

1. use a copy pool you supply;
2. draft proposed copy from an approved product/offer evidence pack;
3. reuse an existing approved copy library.

The CLI does not generate copy. Proposed agent copy stays unapproved until the
user approves the exact media-copy mapping. The final manifest binds exact copy
to exact SHA-256 media bytes.

The manifest can mix `single_image`, `carousel`, `single_video`,
`dynamic_image`, and `flexible_image`. Start with one PAUSED format proof before
widening. Catalog/DPA and account-dependent formats remain explicitly outside
0.1.0 rather than being simulated.

## API-load controls

Set `limits.max_http_attempts_per_run` and `limits.stop_at_usage_percent` in the
policy. Every live receipt reports calls by method and endpoint plus Meta's app,
business-use-case, and ad-account usage headers. The operator stops locally at
the configured threshold and never retries hard ad-account throttle
`17/2446079`. Resume idempotently from the receipt after Meta reports a reset.
The example policy defaults to at most 10 ads, 100 HTTP attempts, and an 80%
usage stop. Widen those numbers only after observing the account's actual tier
and clean receipts.

## First live proof

Start with one new ad in `PAUSED`. Run a plan, read the full plan, confirm its
hash, apply, and inspect the receipt. Do not widen the batch until the one-ad
readback proves the correct account, parents, Page/Instagram identity, copy,
destination, URL tags, media hash, status, and enhancement/display-link state.
