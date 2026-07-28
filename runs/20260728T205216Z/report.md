# ruleprobe results — 20260728T205216Z

Kill rate is the share of killable mutants the suite caught, averaged over tasks.
Only suites that pass the correct implementation are scored; the rest are counted
as invalid and excluded from kill rate.

| condition | valid | kill rate | Δ vs control | 95% CI | n | tests | asserts/test | invalid: error | invalid: assert | wrong import | tautological | mocks SUT |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `control` | 97% | 0.938 | — | — | — | 22.8 | 1.51 | 0 | 2 | 0 | 2 | 0 |
| `concise_tests` | 100% | 0.853 | -0.094 | [-0.208, -0.010] | 8 | 3.0 | 0.99 | 0 | 0 | 0 | 0 | 0 |
| `ferit_test_integrity` | 98% | 0.922 | +0.021 | [+0.000, +0.063] | 8 | 12.4 | 1.72 | 1 | 0 | 0 | 4 | 0 |

`invalid: error` counts suites that failed to import or collect — a broken
mechanical contract, not a judgement about behaviour. `invalid: assert` counts
suites that ran but disagreed with the correct implementation. Both are excluded
from kill rate; only the second is evidence about test quality.

`wrong import` counts suites that ignored the explicit `from solution import ...`
contract in the user prompt. Those imports are rewritten before scoring so that
test quality can be measured separately; no assertion is altered.
