# ruleprobe results — 20260728T185754Z

Kill rate is the share of killable mutants the suite caught, averaged over tasks.
Only suites that pass the correct implementation are scored; the rest are counted
as invalid and excluded from kill rate.

| condition | valid | kill rate | Δ vs control | 95% CI | tests | asserts/test | tautological | assertion-free | mocks SUT |
|---|---|---|---|---|---|---|---|---|---|
| `control` | 100% | 1.000 | — | — | 21.0 | 1.00 | 0 | 0 | 0 |
| `coverage_mandate` | 100% | 1.000 | +0.000 | [+0.000, +0.000] | 22.5 | 1.00 | 0 | 0 | 0 |
| `green_suite` | 100% | 1.000 | +0.000 | [+0.000, +0.000] | 17.5 | 1.00 | 1 | 0 | 0 |
| `mock_everything` | 50% | 1.000 | +0.000 | [+0.000, +0.000] | 20.0 | 1.00 | 1 | 0 | 0 |
| `concise_tests` | 100% | 1.000 | +0.000 | [+0.000, +0.000] | 5.0 | 1.00 | 0 | 0 | 0 |
| `impl_is_truth` | 50% | 1.000 | +0.000 | [+0.000, +0.000] | 27.5 | 1.02 | 1 | 0 | 0 |
| `no_flaky` | 100% | 1.000 | +0.000 | [+0.000, +0.000] | 15.0 | 1.00 | 0 | 0 | 0 |
| `rule_bloat` | 100% | 1.000 | +0.000 | [+0.000, +0.000] | 15.0 | 1.00 | 0 | 0 | 0 |
