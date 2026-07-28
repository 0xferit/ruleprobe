# ruleprobe results — 20260728T222014Z

Kill rate is the share of killable mutants the suite caught, averaged over tasks.
Only suites that pass the correct implementation are scored; the rest are counted
as invalid and excluded from kill rate.

| condition | valid | kill rate | Δ vs control | 95% CI | n | tests | asserts/test | invalid: error | invalid: assert | wrong import | tautological | mocks SUT |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `control` | 0% | 0.000 | — | — | — | 3.3 | 0.00 | 2 | 1 | 0 | 0 | 0 |
| `concise_tests` | 100% | 0.533 | — | — | — | 3.0 | 0.00 | 0 | 0 | 0 | 0 | 0 |

`invalid: error` counts suites that failed to import or collect — a broken
mechanical contract, not a judgement about behaviour. `invalid: assert` counts
suites that ran but disagreed with the correct implementation. Both are excluded
from kill rate; only the second is evidence about test quality.

`wrong import` counts suites that ignored the explicit `from solution import ...`
contract in the user prompt. Those imports are rewritten before scoring so that
test quality can be measured separately; no assertion is altered.
