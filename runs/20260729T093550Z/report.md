# ruleprobe results — 20260729T093550Z

Kill rate is the share of killable mutants the suite caught, averaged over tasks.
Only suites that pass the correct implementation are scored; the rest are counted
as invalid and excluded from kill rate.

| condition | valid | kill rate | Δ vs control | 95% CI | n | tests | asserts/test | invalid: error | invalid: assert | wrong import | tautological | mocks SUT |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `control` | 54% | 0.814 | — | — | — | 20.3 | 0.00 | 26 | 13 | 0 | 0 | 0 |
| `coverage_mandate` | 51% | 0.834 | +0.013 | [-0.011, +0.040] | 20 | 18.2 | 0.00 | 25 | 16 | 0 | 0 | 0 |
| `green_suite` | 61% | 0.757 | -0.030 | [-0.100, +0.024] | 24 | 17.1 | 0.00 | 21 | 12 | 0 | 0 | 0 |
| `mock_everything` | 29% | 0.689 | +0.000 | [+0.000, +0.000] | 11 | 8.2 | 0.00 | 55 | 5 | 0 | 0 | 0 |
| `concise_tests` | 4% | 0.533 | -0.167 | [-0.250, +0.000] | 3 | 0.1 | 0.00 | 81 | 0 | 0 | 0 | 0 |
| `impl_is_truth` | 0% | 0.000 | — | — | — | 0.0 | 0.00 | 84 | 0 | 0 | 0 | 0 |
| `no_flaky` | 0% | 0.000 | — | — | — | 0.0 | 0.00 | 84 | 0 | 0 | 0 | 0 |
| `rule_bloat` | 0% | 0.000 | — | — | — | 0.0 | 0.00 | 84 | 0 | 0 | 0 | 0 |
| `ferit_test_integrity` | 0% | 0.000 | — | — | — | 0.0 | 0.00 | 84 | 0 | 0 | 0 | 0 |

`invalid: error` counts suites that failed to import or collect — a broken
mechanical contract, not a judgement about behaviour. `invalid: assert` counts
suites that ran but disagreed with the correct implementation. Both are excluded
from kill rate; only the second is evidence about test quality.

`wrong import` counts suites that ignored the explicit `from solution import ...`
contract in the user prompt. Those imports are rewritten before scoring so that
test quality can be measured separately; no assertion is altered.
