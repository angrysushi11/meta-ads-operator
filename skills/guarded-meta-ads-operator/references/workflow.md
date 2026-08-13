# Workflow and commands

## Install check

```bash
python scripts/check_operator.py
guarded-meta doctor --policy /path/to/policy.json
```

## Creative intake

```bash
guarded-meta inventory /explicit/creative/folder --output inventory.json
```

If approved copy is absent, draft it in the agent layer from an approved brief.
Do not call an LLM from the deterministic CLI.

Before planning an unfamiliar format:

```bash
guarded-meta capabilities --format "shop ads"
```

Stop on `RECOGNIZED_NOT_SUPPORTED` or `UNKNOWN`. Explain prerequisites; do not
substitute another format.

## Plan and apply

```bash
guarded-meta plan create-ads \
  --policy policy.json \
  --manifest manifest.json \
  --output plan.json

guarded-meta apply \
  --policy policy.json \
  --plan plan.json \
  --confirm PLAN_SHA256
```

Status and budget changes use separate plans:

```bash
guarded-meta plan status --policy policy.json --kind ad --id AD_ID --status PAUSED --output plan.json
guarded-meta plan budget --policy policy.json --kind ad_set --id AD_SET_ID --daily-budget-minor 5000 --output plan.json
```

## Reporting and rules

```bash
guarded-meta insights --policy policy.json --id CAMPAIGN_ID --level ad --date-preset last_7d --output insights.json
guarded-meta evaluate-rule --policy policy.json --insights insights.json --rule rule.json --output candidates.json
```

Rule evaluation is read-only. Convert reviewed candidates into exact status or
budget plans. Scheduled monitoring requires an always-on runtime; a sleeping
laptop does not enforce rules.
