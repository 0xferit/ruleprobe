# Morning report

Run `20260729T093550Z` — 756 of 756 planned units, 28 tasks x 9 conditions x 3 samples, $22.60.

## Kill rate, paired against control

| condition | valid | kill rate | Δ vs control | 95% CI | paired n | verdict |
|---|---|---|---|---|---|---|
| `control` | 54% | 0.814 | — | — | — | baseline |
| `coverage_mandate` | 51% | 0.834 | +0.013 | [-0.011, +0.040] | 20 | not resolved |
| `green_suite` | 61% | 0.757 | -0.030 | [-0.100, +0.024] | 24 | not resolved |
| `mock_everything` | 29% | 0.689 | +0.000 | [+0.000, +0.000] | 11 | not resolved |
| `concise_tests` | 4% | 0.533 | -0.167 | [-0.250, +0.000] | 3 | not resolved |
| `impl_is_truth` | 0% | 0.000 | — | — | 0 | no shared tasks |
| `no_flaky` | 0% | 0.000 | — | — | 0 | no shared tasks |
| `rule_bloat` | 0% | 0.000 | — | — | 0 | no shared tasks |
| `ferit_test_integrity` | 0% | 0.000 | — | — | 0 | no shared tasks |

## Suites that failed to build

A suite that does not compile says nothing about whether a mutation was
detected, so these are excluded from kill rate and counted here instead.

| condition | units | build errors | assertion failures | other invalid |
|---|---|---|---|---|
| `control` | 84 | 26 | 13 | 0 |
| `coverage_mandate` | 84 | 25 | 16 | 0 |
| `green_suite` | 84 | 21 | 12 | 0 |
| `mock_everything` | 84 | 55 | 5 | 0 |
| `concise_tests` | 84 | 81 | 0 | 0 |
| `impl_is_truth` | 84 | 84 | 0 | 0 |
| `no_flaky` | 84 | 84 | 0 | 0 |
| `rule_bloat` | 84 | 84 | 0 | 0 |
| `ferit_test_integrity` | 84 | 84 | 0 | 0 |

## Test volume

| condition | mean tests per suite |
|---|---|
| `control` | 20.3 |
| `coverage_mandate` | 18.2 |
| `green_suite` | 17.1 |
| `mock_everything` | 8.2 |
| `concise_tests` | 0.1 |
| `impl_is_truth` | 0.0 |
| `no_flaky` | 0.0 |
| `rule_bloat` | 0.0 |
| `ferit_test_integrity` | 0.0 |

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

