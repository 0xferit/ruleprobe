# Morning report

Run `20260728T222435Z` — 45 of 45 planned units, 15 tasks x 1 conditions x 3 samples, $15.80.

## Kill rate, paired against control

| condition | valid | kill rate | Δ vs control | 95% CI | paired n | verdict |
|---|---|---|---|---|---|---|
| `control` | 31% | 0.667 | — | — | — | baseline |

## Suites that failed to build

A suite that does not compile says nothing about whether a mutation was
detected, so these are excluded from kill rate and counted here instead.

| condition | units | build errors | assertion failures | other invalid |
|---|---|---|---|---|
| `control` | 45 | 24 | 7 | 0 |

## Test volume

| condition | mean tests per suite |
|---|---|
| `control` | 9.6 |

## Caveats that survive any result above

- Intervals crossing zero mean the effect was not resolved, not that it is
  absent. Resolving effects near 0.014 needs roughly 33 tasks.
- Three samples per cell, chosen on evidence: the variance pilot measured
  mean within-cell SD at 0.0312 with a median of 0.0000, so variance lives
  between tasks rather than within cells.
- Tasks were feasibility-screened by a prompt outside the nine conditions.
  Screening on a condition's own success would have biased the comparison.
- Absolute rates do not transfer to a bare API call: the Claude Code CLI
  contributes fixed harness context to every call, and exposes no
  temperature control.

