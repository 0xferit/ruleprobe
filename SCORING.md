# Scoring notes

What each number means, why it was chosen, and where it is untrustworthy.

## The question

Does a system-prompt rule that a competent team would plausibly write reduce
the information a generated test suite buys?

"Information" is the operative word. A test that runs code without being able
to tell right from wrong is not a weak test; it is a non-test that reports
success. Coverage cannot see the difference. Mutation testing can.

## Primary metric: mutation kill rate

For every task, `data/mutants.jsonl` holds a set of single-site mutations of
the correct implementation, each one already proven killable (see below). A
generated suite is run against every mutant. Kill rate is the fraction that
make the suite go red.

    kill_rate(task) = mutants_killed / mutants_total

The reported figure per condition is the mean of per-task kill rates, not the
pooled total. Tasks contribute between 1 and 12 mutants; pooling would let the
handful of mutation-rich tasks dominate the result.

**Kill definition.** A mutant counts as killed when the suite's outcome is
anything other than `passed`: a failure, an error, or a timeout. That is only
sound because of the validity gate below — the same suite is known to pass the
correct implementation, so any other verdict is attributable to the mutation.

### Why mutants are validated first

A mutation that produces semantically identical behaviour is unkillable by any
suite. Leaving such mutants in would depress every condition equally and
understate what a good suite achieves.

`ruleprobe/validate.py` therefore admits a mutant only if HumanEval+'s expanded
reference suite kills it. That suite is the strongest available oracle for
these functions, so anything it cannot distinguish is treated as an equivalent
mutant and dropped. In the frozen set, 8 of 161 candidates were dropped this
way.

The reference suite is also asserted to pass each canonical solution before it
is used as an oracle. If it did not, the oracle would be broken and the run
aborts rather than producing quiet nonsense.

## The validity gate

Before any mutant is run, the suite must pass the *correct* implementation.

This is the single most important guard in the harness. A suite that fails on
correct code fails on every mutant too, and without the gate it would be
scored as the strongest suite in the experiment. Invalid suites are reported
separately as a validity rate and are excluded from kill rate entirely — their
kill rate is `null`, never `0`, because "we could not measure it" and "it
caught nothing" are different claims.

**Caveat.** Validity failure conflates two causes worth separating by hand:

1. The suite is simply wrong — a miscomputed expected value.
2. The suite asserts something true of the specification that the reference
   implementation does not satisfy, most often exact float equality.

Case 2 is arguably a *good* test failing an imperfect implementation. Both
appear here as "invalid". Read the recorded `test_source` before drawing
conclusions from the validity column.

## Import normalisation, and why it is not a fudge

The user prompt states the import contract explicitly:

    The function is importable as:

        from solution import <entry_point>

`ruleprobe/normalise.py` rewrites the module name in any import of the entry
point back to `solution` before scoring, and records whether it fired.

**It exists because of a harness bug, not a model behaviour.** During the first
full run this file was edited mid-flight, and 151 of 192 prompts went out
containing the literal placeholder `from {module} import <fn>`. The model
substituted a name of its own, the suites failed to import, and this briefly
looked like a rule-induced instruction-following failure. It was not. See
RESULTS.md §5 for the full account.

In the clean run the rewrite fired on **0 of 192** suites. It is retained as a
no-op safety net for other backends, whose prompt handling may differ.

The rewrite is keyed on the entry point, so an import of any other module is
never touched. It changes no assertion, removes no test, and weakens nothing.
`test_source_raw` in every record holds the unmodified model output, so any
rewrite can be audited or undone.

**Operational rule learned the hard way: never edit `prompts/` while a run is
in flight.** `render_task_prompt` re-reads from disk on every call.

## Secondary metrics: static detectors

All are pure AST rules in `ruleprobe/detect.py`. No LLM judge is used
anywhere, for two reasons: a judge is one more component that the prompt under
test could influence, and a deterministic detector lets anyone re-derive every
number offline from the committed transcripts.

| detector | what it counts |
|---|---|
| `assertion_free` | test functions with neither an `assert` nor an asserting context manager |
| `tautological` | expected value produced by calling the function under test, directly or via a variable |
| `mocks_sut` | a patch target naming the solution module or the entry point |
| `trivial_assert` | `assert <constant>`, or a comparison of an expression with itself |
| `assertion_density` | assertions divided by test functions |

Two boundaries are deliberate and pinned by tests:

- `pytest.raises` **is** an assertion. A test whose only check is a `raises`
  block is not assertion-free; counting it as such would penalise the correct
  way to test an error path.
- Mocking a genuine external dependency is **not** flagged. Only mocking the
  system under test is a smell.

These are supporting evidence, not the verdict. A suite can be free of every
smell above and still kill nothing, which is exactly why kill rate leads.

## Statistics

The design is paired: every condition sees the identical task set, so each
task yields one delta against the control. Pairing removes between-task
difficulty variance, which dominates at this sample size.

A task contributes a delta only when it produced a *valid* suite in both arms.
Otherwise the two conditions would be compared on different task sets.

Intervals are 95% bootstrap percentile intervals over 10,000 resamples,
stdlib-only and seeded, so any published interval can be reproduced exactly
from `records.jsonl`.

## Prompt isolation

This matters more than it sounds.

Claude Code loads the operator's `CLAUDE.md` into headless calls even when
`--system-prompt` and `--exclude-dynamic-system-prompt-sections` are both set.
On the machine this was built on, that file contains explicit test-integrity
rules — "Never mock the system under test", "Trivially-satisfied assertions
are failures". Those instructions would have been silently present in all
eight conditions, suppressing the exact behaviours being measured.

`--setting-sources ""` removes them while preserving authentication. This was
verified by asking the model in headless mode to repeat any test-integrity
rules it had been given, before and after the flag:

- without the flag: the model quoted the operator's Test Integrity section verbatim
- with the flag: `NO_TEST_RULES`

Anyone reproducing this on another machine should re-run that check first.
`ruleprobe/backend.py` carries the flag; do not remove it.

## Known limitations

Stated plainly, because a harness that oversells itself is the same failure
mode it is trying to measure.

1. **Pilot scale.** 24 tasks, one sample per cell. Enough for paired deltas
   with intervals, not enough to resolve small effects. Intervals that cross
   zero mean the effect was not resolved, not that it is absent.
2. **Not a bare model.** The Claude Code CLI contributes roughly 20k tokens of
   harness context to every call. It is identical across conditions, so
   between-condition comparisons hold, but absolute rates will not transfer to
   a raw API call.
3. **Temperature is not controllable** through the CLI, so run-to-run variance
   is not separable from condition effects at n=1 per cell.
4. **Ceiling effects on easy tasks.** Tasks with one or two killable mutants
   saturate at 1.0 and cannot discriminate between conditions. They are kept
   for the paired design but contribute little signal.
5. **HumanEval is small, well-known, and likely in training data.** Findings
   are about how the *rule* shifts behaviour on familiar problems, not about
   test quality on novel code, where absolute quality would be lower.
6. **Single model, single day.** No claim is made about other models or about
   stability across model versions.
7. **Execution is not sandboxed.** Generated suites run in a subprocess with a
   wall-clock timeout and CPU/memory caps. That is damage limiting, not
   isolation. Do not point this at untrusted model output on a machine you
   care about.

## The repository task set

`data/tasks-bmk.jsonl` is sliced from `bitfinex-maker-kit` by `ruleprobe/repo.py`.
It exists because HumanEval saturates the metric: on those tasks every valid
suite killed every mutant, so no rule could be shown to do damage.

Verified discrimination on `calculate_order_total`, same task, three suites:

| suite | kill rate |
|---|---|
| assertion-free | 0.17 |
| one shallow assertion | 0.50 |
| thorough, hand-written | 0.67 |

All three score 1.000 on HumanEval-grade code. This set has headroom.

### Slicing

A task is one function plus the transitive closure of module-level names it
needs. Carrying the whole module would give the model context its real callers
never provide, and would add mutation sites outside the function under test.
Relative imports are rewritten to absolute so the slice runs standalone.

### Safety, which is load-bearing here

The model writes test code that is then executed locally, and the host package
is a live trading tool. Three filters apply, in increasing order of strength:

1. **Signature check** — reject functions taking a `client`, `session`,
   `websocket` and similar. Exact name matching, so ordinary parameters like
   `recipient` are not caught.
2. **Slice check** — reject slices that call a client factory or import a
   client, websocket, api, or services module. This is the one that matters:
   `cancel_order(order_id)` declares *no* client parameter, it calls
   `get_client()` in its body, and signature inspection alone would have let
   live order cancellation into the sandbox. Module segments are matched by
   substring, because `bitfinex_client` is not equal to `client` and the costs
   are asymmetric — a false positive drops one task, a false negative places
   real orders.
3. **Stdlib-only check** — reject slices that import the host package at all.
   This is structural rather than advisory: the package is not importable in
   the sandbox, so no generated test can reach a trading client whatever it
   writes. It is the reason the set is 8 tasks rather than 14.

Of 25 candidate functions, 11 were rejected as unsafe, including `submit_order`,
`cancel_order`, `update_order` and `cancel_single_order`.

### Mutant validation differs from HumanEval

There is no independent 80x reference suite for a repository, so mutants cannot
be pre-validated as killable. Instead `score.py` records a per-mutant kill
vector, and equivalent mutants are filtered **post hoc**: a mutant that no suite
in the entire run killed is dropped from the denominator.

This is conservative and does not favour any condition — a mutant killed by only
one condition is still admitted, and that condition still gets the credit. The
frozen mutant file therefore contains all candidates, and the admitted set is a
property of a given run rather than of the dataset.
