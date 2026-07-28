# Results: repository task set

Run `20260728T203738Z` — claude-sonnet-5, 8 functions sliced from
`bitfinex-maker-kit`, 9 conditions, 72 suites, $5.52.

Includes the operator's own `CLAUDE.md` test rules as a ninth condition.

## Headline

**Nothing is resolved at n=8. Every interval touches or crosses zero.**

Moving off HumanEval did remove the hard ceiling — control scores 0.917 raw
rather than an exact 1.000, and a hand-written assertion-free suite scores 0.17
on these tasks against 1.000 on HumanEval. But eight tasks is too few to
resolve effects of the size present here.

| condition | valid | kill rate | Δ vs control | 95% CI | tests/suite | asserts/test |
|---|---|---|---|---|---|---|
| `control` | 100% | 0.917 | — | — | 20.6 | 1.54 |
| `coverage_mandate` | 88% | 0.952 | +0.000 | [+0.000, +0.000] | 21.5 | 1.64 |
| `green_suite` | 88% | 0.940 | −0.012 | [−0.036, +0.000] | 21.8 | 1.52 |
| `mock_everything` | 100% | 0.938 | +0.021 | [+0.000, +0.063] | 19.2 | 1.41 |
| `concise_tests` | 100% | 0.875 | −0.042 | [−0.104, +0.000] | 3.0 | 1.00 |
| `impl_is_truth` | 100% | 0.938 | +0.021 | [+0.000, +0.063] | 19.9 | 1.63 |
| `no_flaky` | 88% | 0.881 | −0.024 | [−0.107, +0.060] | 23.0 | 1.46 |
| `rule_bloat` | 88% | 0.952 | +0.000 | [+0.000, +0.000] | 15.8 | 1.52 |
| **`ferit_test_integrity`** | **100%** | **0.938** | **+0.021** | **[+0.000, +0.063]** | **12.2** | **1.90** |

## The operator's own ruleset

The question this run existed to answer: do the Test Integrity rules in
`~/.claude/CLAUDE.md` measurably improve the tests the model writes?

**Not resolvable as improving bug detection.** Δ = +0.021, CI [+0.000, +0.063].
The interval touches zero, so the direction is suggestive at best and n=8 cannot
settle it.

**But the descriptive signal is clean and consistent with the rules' stated
intent:**

- **12.2 tests per suite against control's 20.6** — a 41% reduction in volume.
- **1.90 assertions per test, the highest of any condition** (control 1.54).
- **100% validity**, tied for best, with zero tautological tests, zero
  assertion-free tests, and zero suites mocking the system under test.
- Bug detection unchanged or marginally better while doing all of the above.

Rule #4 says a test is worth writing only if it buys information. What the data
shows is fewer, denser tests catching the same bugs. That is the intended
effect, observed — it is just not a *statistically resolved* improvement in kill
rate, and should not be described as one.

## `concise_tests` is the only effect consistent across both task sets

| task set | Δ vs control | 95% CI | resolved |
|---|---|---|---|
| HumanEval+ (n=18 paired) | −0.095 | [−0.172, −0.031] | yes |
| bitfinex-maker-kit (n=8 paired) | −0.042 | [−0.104, +0.000] | no |

Same sign, overlapping magnitude, two independent task sets, one of them
resolved. That consistency is worth more than either interval alone. Capping
test and assertion counts reduces bug detection; everything else remains
unproven in either direction.

Note the volume collapse is identical in both: 3.0 tests per suite here, 3.5 on
HumanEval, against controls of 20.6 and 34.4. The rule does exactly what it says
and the detection cost follows from it.

## The post-hoc equivalent-mutant filter compresses rather than clarifies

Of 48 mutants, 43 were killed by at least one suite; 5 were killed by none and
dropped as possibly equivalent. Filtered figures:

| condition | filtered kill rate | Δ | 95% CI |
|---|---|---|---|
| `control` | 0.975 | — | — |
| `mock_everything` | 1.000 | +0.025 | [+0.000, +0.075] |
| `impl_is_truth` | 1.000 | +0.025 | [+0.000, +0.075] |
| `rule_bloat` | 1.000 | +0.000 | [+0.000, +0.000] |
| `ferit_test_integrity` | 1.000 | +0.025 | [+0.000, +0.075] |
| `coverage_mandate` | 0.971 | +0.000 | [+0.000, +0.000] |
| `green_suite` | 0.982 | −0.018 | [−0.054, +0.000] |
| `no_flaky` | 0.946 | −0.025 | [−0.125, +0.068] |
| `concise_tests` | 0.928 | −0.047 | [−0.109, +0.000] |

**This filter is honest but counterproductive here, and the reason matters.**
The mutants no suite killed are precisely the hardest ones. Dropping them
removes the discriminating cases and pushes every condition back toward 1.000 —
control rises 0.917 → 0.975. It removes noise and signal together.

The unfiltered figures are the more informative ones at this sample size. The
filter earns its place only when the mutant pool is large enough that genuinely
equivalent mutants outnumber merely-hard ones.

## What would actually settle this

Not more conditions. More tasks and more samples per cell.

1. **n=8 is the binding constraint.** The slicer yields 8 tasks from this repo
   because the stdlib-only safety rule excludes 6 that import the package, and
   11 more were rejected as unsafe. Pointing it at a non-trading Python repo
   would lift n without weakening the safety guarantee.
2. **One sample per cell** means run-to-run variance is inseparable from
   condition effects, and the CLI exposes no temperature control. n=3 per cell
   would separate them at 3x the cost.
3. Effects of ±0.02 need roughly an order of magnitude more paired observations
   than this run has.

## Cost

$5.52 for the 72 calls. The re-scoring pass that added per-mutant kill vectors
cost $0.00 — responses are cached by prompt hash, so re-analysis is free.
