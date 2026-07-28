"""The independent variable: one system prompt per condition.

Each condition is the identical base prompt plus one rule of the kind a real
team writes in good faith. Only the rule varies, so any difference in test
quality is attributable to it.

Prompt text lives in `prompts/` rather than in this file so the exact wording
is reviewable in isolation, and the fully composed prompt is recorded verbatim
with every result.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ruleprobe.execute import SOLUTION_MODULE

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
BASE_PROMPT_FILE = "_base.md"
SOLIDITY_BASE_PROMPT_FILE = "_base_sol.md"
TASK_PROMPT_FILE = "_task.md"
SOLIDITY_TASK_PROMPT_FILE = "_task_sol.md"
# Used only to decide whether a task is testable at all. Deliberately not in
# CONDITION_IDS: screening on a condition's own success would select tasks that
# condition happens to handle well and bias the comparison in its favour.
SCREEN_PROMPT_FILE = "_screen.md"
CONTROL = "control"

# Ordered so `control` is always the comparison baseline in reports.
CONDITION_IDS = [
    CONTROL,
    "coverage_mandate",
    "green_suite",
    "mock_everything",
    "concise_tests",
    "impl_is_truth",
    "no_flaky",
    "rule_bloat",
    "ferit_test_integrity",
]

PREDICTED_FAILURE = {
    CONTROL: "baseline",
    "coverage_mandate": "coverage theater: execute lines without checking them",
    "green_suite": "avoids assertions that might go red",
    "mock_everything": "mocks the system under test",
    "concise_tests": "too few assertions to discriminate",
    "impl_is_truth": "tautological tests mirroring the implementation",
    "no_flaky": "drops boundary and edge-case probes",
    "rule_bloat": "instruction dilution from irrelevant rules",
    "ferit_test_integrity": "none predicted; this is the operator's own ruleset under test",
}


@dataclass(frozen=True)
class Condition:
    id: str
    rule: str
    predicted_failure: str

    def system_prompt(self, base: str) -> str:
        """The exact string sent as the system prompt."""
        return base if not self.rule.strip() else f"{base.rstrip()}\n\n{self.rule.rstrip()}\n"


def load_conditions(prompts_dir: Path = PROMPTS_DIR, lang: str = "py") -> list[Condition]:
    """Loads each condition, preferring a language-specific variant when present.

    `rule_bloat` must be irrelevant-but-plausible in the language under test:
    Python style rules shown to a Solidity task are irrelevant for the wrong
    reason and stop being the manipulation they were meant to be.
    """
    return [
        Condition(
            id=condition_id,
            rule=_read_rule(prompts_dir, condition_id, lang),
            predicted_failure=PREDICTED_FAILURE[condition_id],
        )
        for condition_id in CONDITION_IDS
    ]


def _read_rule(prompts_dir: Path, condition_id: str, lang: str) -> str:
    specific = prompts_dir / f"{condition_id}_{lang}.md"
    if specific.exists():
        return specific.read_text()
    return (prompts_dir / f"{condition_id}.md").read_text()


def load_base_prompt(prompts_dir: Path = PROMPTS_DIR, lang: str = "py") -> str:
    """The shared preamble, which must name the right language.

    Telling the model it writes "unit tests for a Python codebase" and then
    handing it a Solidity contract is a confound in every condition at once.
    """
    name = SOLIDITY_BASE_PROMPT_FILE if lang == "sol" else BASE_PROMPT_FILE
    return (prompts_dir / name).read_text()


def render_task_prompt(entry_point: str, solution: str, prompts_dir: Path = PROMPTS_DIR) -> str:
    """The user message, identical across every condition."""
    template = (prompts_dir / TASK_PROMPT_FILE).read_text()
    return (
        template.replace("{module}", SOLUTION_MODULE)
        .replace("{entry_point}", entry_point)
        .replace("{solution}", solution)
    )


def render_solidity_task_prompt(
    contract: str, import_path: str, source: str, prompts_dir: Path = PROMPTS_DIR
) -> str:
    """The user message for a Solidity task, identical across every condition."""
    template = (prompts_dir / SOLIDITY_TASK_PROMPT_FILE).read_text()
    return (
        template.replace("{contract}", contract)
        .replace("{import_path}", import_path)
        .replace("{source}", source)
    )


def load_screen_prompt(prompts_dir: Path = PROMPTS_DIR) -> str:
    """The feasibility screener, which is not one of the experimental arms.

    Composed from the same base prompt and the same rule-joining rule as every
    condition, so the persona sentence exists once. A hardcoded second copy
    would go stale the moment the base prompt is reworded, and the screener
    would then be selecting tasks under a different persona than the
    experiment runs under.
    """
    screen = Condition(
        id="screen",
        rule=(prompts_dir / SCREEN_PROMPT_FILE).read_text(),
        predicted_failure="not an experimental condition",
    )
    return screen.system_prompt(load_base_prompt(prompts_dir, lang="sol"))
