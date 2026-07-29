# Resuming the phase-1 Solidity campaign

Paused mid-run. Nothing is lost: both caches are on disk, so resuming pays only
for units not yet completed.

## State at pause

- **317 of 756 units usable** across 4 of 9 conditions
- Response cache: 1013 entries. Score cache: 324 entries.
- Spend to date: $182
- Remaining: 5 conditions x 28 tasks x 3 samples, plus stragglers

## Resume

```bash
cd "$HOME/Library/Mobile Documents/com~apple~CloudDocs/Projects/0xferit/ruleprobe"
LOG_DIR=/tmp WORKERS=10 ./scripts/watchdog.sh &
```

Watch it with:

```bash
.venv/bin/python scripts/progress.py
```

## Do not raise WORKERS above 10

28 workers exceeded the API rate limit and 465 of 756 units were written off as
permanent failures, wiping four conditions. 6 workers ran clean at 0.9
units/min; 18 ran clean at 4.25. The limit sits somewhere between 18 and 28.

The retry now carries 930 seconds of patience across 6 attempts, so throttling
costs time rather than data, but that is a safety net, not a licence.

## Conditions still needed

`concise_tests`, `impl_is_truth`, `no_flaky`, `rule_bloat`,
`ferit_test_integrity` — the last being the operator's own CLAUDE.md rules, the
question the campaign exists to answer.

## Numbers that are already trustworthy

| condition | valid | kill rate |
|---|---|---|
| `control` | 54% | 0.814 |
| `coverage_mandate` | 51% | 0.834 |
| `green_suite` | 61% | 0.757 |

`mock_everything` at 66/84 usable is incomplete. Do not read it yet.
