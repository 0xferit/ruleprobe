# Architecture

One dated entry per structural decision: what talks to what, where state
lives, which guarantees hold at a boundary. Not implementation detail — the
code shows that.

## 2026-07-28 — Mutation kill rate is the primary metric, not an LLM judge

**Decision.** Test quality is scored by whether a generated suite kills known
mutants of the correct implementation, not by asking a model to grade the
suite.

**Alternatives weighed.** An LLM-judge scorer was rejected: it would be one
more component the prompt under test could influence, and it would make
results impossible to re-derive offline from committed transcripts. Coverage
percentage was rejected: TestGenEval already showed models can hit high
coverage while catching almost no mutants (18.8% mutation score at 35.2%
coverage) — coverage cannot tell a real test from a non-test.

**Consequences accepted.** Every secondary signal (`ruleprobe/detect.py`) is a
deterministic AST rule with no model in the loop. The tradeoff is that static
detectors can miss smells a judge might catch; kill rate is treated as the
verdict and detectors as supporting evidence only.

## 2026-07-28 — Validity gate precedes mutation scoring

**Decision.** A suite is scored against mutants only after it is shown to pass
the *correct* implementation. A suite that fails on correct code is marked
invalid and excluded from kill rate; its kill rate is `null`, never `0`.

**Alternatives weighed.** Scoring every suite against every mutant regardless
of baseline correctness was rejected: a suite that fails on correct code fails
on every mutant too, and would otherwise register as the strongest suite in
the experiment.

**Consequences accepted.** "Could not measure" and "caught nothing" are kept
as distinct claims throughout the statistics layer, which is more code than
collapsing them, but conflating them would misreport a rule that breaks
suites mechanically as a rule that degrades detection.

## 2026-07-28 — Prompt isolation from the operator's own CLAUDE.md

**Decision.** The model backend calls the Claude Code CLI headless
(`claude -p`) with `--setting-sources ""`, so no `CLAUDE.md`, project rule, or
skill loads into the experimental prompt.

**Alternatives weighed.** `--system-prompt` combined with
`--exclude-dynamic-system-prompt-sections` looks sufficient and is not:
verified by asking the model in headless mode to repeat any test-integrity
rules it had been given. Without the isolation flag it quoted the operator's
own Test Integrity section verbatim, which would have applied the rules under
test to themselves in every condition at once.

**Consequences accepted.** Absolute rates measured this way do not transfer to
a bare API call, since the CLI still contributes its own fixed harness
context (~20-40k tokens) to every call. Only the *comparison* between
conditions is guaranteed clean, not the absolute numbers.

## 2026-07-28 — Response and score caching, keyed by content hash

**Decision.** Every model response and every scoring result is cached to disk
keyed by a hash of its full inputs (prompt, model, sample index for
responses; language, task, mutant set, suite text for scores). A campaign is
resumable: re-invoking it after a crash or a deliberate pause re-derives
nothing already paid for.

**Alternatives weighed.** Caching only model responses (the initial design)
was tried and found insufficient: scoring is the CPU-heavy half of a unit, so
every restart still replayed forge or pytest over the entire completed
prefix, and the replay grew with each restart.

**Consequences accepted.** A change to prompt wording, model, or mutant set
invalidates the relevant cache entries silently rather than erroring, by
design — that is what "content-addressed" means. The cache-key format itself
is frozen by test once real spend sits behind it, because changing the
hashing scheme orphans every entry on disk.

## 2026-07-29 — Two independent language backends share one Score record

**Decision.** Python (HumanEval+, and functions sliced from a target repo) and
Solidity (contracts sliced from a target repo) are scored through the same
`Score` dataclass and the same statistics layer. Only task extraction,
mutation, and execution are language-specific.

**Alternatives weighed.** A parallel Solidity-only pipeline was rejected: it
would need its own paired-delta and bootstrap-interval implementation, which
is exactly the kind of duplicated knowledge that silently diverges.

**Consequences accepted.** Every language backend must produce a `Score` with
the same field set, including fields (like the AST-based `Report`) that don't
apply to Solidity; those are populated with an empty/zero value rather than
omitted.

## 2026-07-29 — A Solidity task is a minimal, sandboxed, isolated Foundry project

**Decision.** A Solidity task is one contract plus the transitive closure of
project-local files it imports (`ruleprobe/solidity.py:resolve_closure`),
assembled into a fresh, minimal Foundry project per scoring call. External
dependencies resolve through remappings, never by copying a dependency tree.

**Alternatives weighed.** Running suites inside the full source repository
was rejected on measured grounds: the full `octant-v2-core` project takes
13.5s to build incrementally; a minimal isolated project runs `forge test` in
0.33s warm. At the campaign's scale (tens of thousands of forge invocations)
that difference is the difference between feasible and not.

**Consequences accepted.** A task's project must be reassembled per mutant
(each on its own temp directory), which is more process spawning than
mutating in place, but it's what makes concurrent scoring safe: mutants for
different conditions never share a filesystem location.

## 2026-07-29 — The sandbox is structurally forbidden from reaching a live trading client

**Decision.** When the task-supply repository is a live trading tool
(`bitfinex-maker-kit`), any candidate function whose slice imports the host
package at all is excluded from the task set — not filtered by inspecting
what the generated test does, but excluded before any model ever sees it.

**Alternatives weighed.** A signature-level filter (reject functions taking a
`client` parameter) was tried first and found insufficient:
`cancel_order(order_id)` takes no client parameter at all — it calls
`get_client()` internally — so a generated test for it could silently place
or cancel real orders if credentials were present in the environment. A
slice-level filter (reject calls to known client-factory functions, reject
imports of client/websocket/api modules) closed that gap but still depends on
recognizing every dangerous pattern.

**Consequences accepted.** The stdlib-only-imports rule is the one guarantee
in the safety model that holds regardless of what a generated test writes: if
the host package is not importable in the sandbox, no test can reach a live
client no matter what it contains. This is a structural guarantee, not an
audited one, and it costs task-set size: 11 of 25 candidate functions were
excluded this way, including every order-placement and order-cancellation
function in the repository.

## 2026-07-29 — Feasibility screening is a prompt outside the nine experimental conditions

**Decision.** Before running the paired experiment, every Solidity task is
screened by a single prompt (distinct from all nine conditions) asking only
whether the contract can be unit-tested in isolation at all. Tasks that fail
this screen are dropped from the task set entirely.

**Alternatives weighed.** Screening on whether the `control` condition
produces a valid suite was considered and rejected: it would select tasks
`control` happens to handle well, biasing every comparison in `control`'s
favour before the experiment even starts.

**Consequences accepted.** The screen itself costs real model calls and time
(and can be wrong — a task it keeps may still turn out infeasible under a
specific condition, which is why per-condition validity is still tracked and
reported after screening).

## 2026-07-31 — Backfilled this file

No prior `ARCHITECTURE.md` existed. This entry and the six above it record
decisions already made and shipped; nothing here changes existing behavior.
