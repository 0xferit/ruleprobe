# ruleprobe results — 20260728T185922Z

Kill rate is the share of killable mutants the suite caught, averaged over tasks.
Only suites that pass the correct implementation are scored; the rest are counted
as invalid and excluded from kill rate.

| condition | valid | kill rate | Δ vs control | 95% CI | tests | asserts/test | tautological | assertion-free | mocks SUT |
|---|---|---|---|---|---|---|---|---|---|
| `control` | 79% | 1.000 | — | — | 34.4 | 1.05 | 3 | 0 | 0 |
| `coverage_mandate` | 62% | 1.000 | +0.000 | [+0.000, +0.000] | 25.1 | 1.05 | 1 | 0 | 0 |
| `green_suite` | 25% | 1.000 | +0.000 | [+0.000, +0.000] | 9.7 | 1.07 | 3 | 0 | 0 |
| `mock_everything` | 0% | 0.000 | — | — | 2.0 | 1.03 | 3 | 1 | 0 |
| `concise_tests` | 8% | 1.000 | +0.000 | [+0.000, +0.000] | 2.1 | 1.00 | 0 | 0 | 0 |
| `impl_is_truth` | 21% | 1.000 | +0.000 | [+0.000, +0.000] | 8.2 | 1.07 | 2 | 0 | 0 |
| `no_flaky` | 4% | 1.000 | +0.000 | [+0.000, +0.000] | 3.7 | 1.04 | 3 | 0 | 0 |
| `rule_bloat` | 46% | 1.000 | +0.000 | [+0.000, +0.000] | 16.5 | 1.05 | 2 | 0 | 0 |
