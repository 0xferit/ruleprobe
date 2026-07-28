# Runs

Each directory holds the complete record of one run: every system prompt, user
prompt, raw model response, extracted suite, and score. `report.md` is
regenerable from `records.jsonl` with `python -m ruleprobe report <dir>`.

| run | status | what it is |
|---|---|---|
| `20260728T185754Z` | smoke | 2 tasks x 8 conditions, pipeline check only |
| `20260728T185922Z` | **invalid — do not cite** | contaminated by a prompt-template edit made while the run was in flight; 151/192 prompts contain the literal `{module}` placeholder. Kept as evidence, see RESULTS.md §5 |
| `20260728T191229Z` | **canonical** | the clean 24 x 8 run all reported figures come from |

The invalid run is retained rather than deleted. A harness built to detect
results that look better than they are should not quietly bin its own.
