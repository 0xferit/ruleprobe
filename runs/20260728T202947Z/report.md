# ruleprobe results — 20260728T202947Z

Kill rate is the share of killable mutants the suite caught, averaged over tasks.
Only suites that pass the correct implementation are scored; the rest are counted
as invalid and excluded from kill rate.

| condition | valid | kill rate | Δ vs control | 95% CI | n | tests | asserts/test | invalid: error | invalid: assert | wrong import | tautological | mocks SUT |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `control` | 100% | 0.917 | — | — | — | 20.6 | 1.54 | 0 | 0 | 0 | 0 | 0 |
| `coverage_mandate` | 88% | 0.952 | +0.000 | [+0.000, +0.000] | 7 | 21.5 | 1.64 | 0 | 1 | 0 | 1 | 0 |
| `green_suite` | 88% | 0.940 | -0.012 | [-0.036, +0.000] | 7 | 21.8 | 1.52 | 0 | 1 | 0 | 2 | 0 |
| `mock_everything` | 100% | 0.938 | +0.021 | [+0.000, +0.063] | 8 | 19.2 | 1.41 | 0 | 0 | 0 | 0 | 0 |
| `concise_tests` | 100% | 0.875 | -0.042 | [-0.104, +0.000] | 8 | 3.0 | 1.00 | 0 | 0 | 0 | 0 | 0 |
| `impl_is_truth` | 100% | 0.938 | +0.021 | [+0.000, +0.063] | 8 | 19.9 | 1.63 | 0 | 0 | 0 | 1 | 0 |
| `no_flaky` | 88% | 0.881 | -0.024 | [-0.107, +0.060] | 7 | 23.0 | 1.46 | 0 | 1 | 0 | 1 | 0 |
| `rule_bloat` | 88% | 0.952 | +0.000 | [+0.000, +0.000] | 7 | 15.8 | 1.52 | 0 | 1 | 0 | 0 | 0 |
| `ferit_test_integrity` | 100% | 0.938 | +0.021 | [+0.000, +0.063] | 8 | 12.2 | 1.90 | 0 | 0 | 0 | 0 | 0 |

`invalid: error` counts suites that failed to import or collect — a broken
mechanical contract, not a judgement about behaviour. `invalid: assert` counts
suites that ran but disagreed with the correct implementation. Both are excluded
from kill rate; only the second is evidence about test quality.

`wrong import` counts suites that ignored the explicit `from solution import ...`
contract in the user prompt. Those imports are rewritten before scoring so that
test quality can be measured separately; no assertion is altered.
