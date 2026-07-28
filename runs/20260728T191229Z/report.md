# ruleprobe results — 20260728T191229Z

Kill rate is the share of killable mutants the suite caught, averaged over tasks.
Only suites that pass the correct implementation are scored; the rest are counted
as invalid and excluded from kill rate.

| condition | valid | kill rate | Δ vs control | 95% CI | n | tests | asserts/test | invalid: error | invalid: assert | wrong import | tautological | mocks SUT |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `control` | 79% | 1.000 | — | — | — | 34.4 | 1.05 | 0 | 5 | 0 | 3 | 0 |
| `coverage_mandate` | 83% | 1.000 | +0.000 | [+0.000, +0.000] | 18 | 30.5 | 1.05 | 0 | 4 | 0 | 2 | 0 |
| `green_suite` | 83% | 1.000 | +0.000 | [+0.000, +0.000] | 18 | 77.5 | 1.06 | 0 | 4 | 0 | 3 | 0 |
| `mock_everything` | 62% | 1.000 | +0.000 | [+0.000, +0.000] | 14 | 26.5 | 1.02 | 0 | 9 | 0 | 2 | 0 |
| `concise_tests` | 88% | 0.898 | -0.095 | [-0.172, -0.031] | 18 | 3.5 | 0.99 | 0 | 3 | 0 | 1 | 0 |
| `impl_is_truth` | 67% | 1.000 | +0.000 | [+0.000, +0.000] | 14 | 111.0 | 1.08 | 0 | 8 | 0 | 2 | 0 |
| `no_flaky` | 79% | 1.000 | +0.000 | [+0.000, +0.000] | 17 | 21.7 | 1.04 | 0 | 5 | 0 | 3 | 0 |
| `rule_bloat` | 75% | 1.000 | +0.000 | [+0.000, +0.000] | 15 | 22.5 | 1.04 | 0 | 6 | 0 | 2 | 0 |

`invalid: error` counts suites that failed to import or collect — a broken
mechanical contract, not a judgement about behaviour. `invalid: assert` counts
suites that ran but disagreed with the correct implementation. Both are excluded
from kill rate; only the second is evidence about test quality.

`wrong import` counts suites that ignored the explicit `from solution import ...`
contract in the user prompt. Those imports are rewritten before scoring so that
test quality can be measured separately; no assertion is altered.
