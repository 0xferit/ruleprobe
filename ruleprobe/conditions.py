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
TASK_PROMPT_FILE = "_task.md"
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
}


@dataclass(frozen=True)
class Condition:
    id: str
    rule: str
    predicted_failure: str

    def system_prompt(self, base: str) -> str:
        """The exact string sent as the system prompt."""
        return base if not self.rule.strip() else f"{base.rstrip()}\n\n{self.rule.rstrip()}\n"


def load_conditions(prompts_dir: Path = PROMPTS_DIR) -> list[Condition]:
    return [
        Condition(
            id=condition_id,
            rule=(prompts_dir / f"{condition_id}.md").read_text(),
            predicted_failure=PREDICTED_FAILURE[condition_id],
        )
        for condition_id in CONDITION_IDS
    ]


def load_base_prompt(prompts_dir: Path = PROMPTS_DIR) -> str:
    return (prompts_dir / BASE_PROMPT_FILE).read_text()


def render_task_prompt(entry_point: str, solution: str, prompts_dir: Path = PROMPTS_DIR) -> str:
    """The user message, identical across every condition."""
    template = (prompts_dir / TASK_PROMPT_FILE).read_text()
    return (
        template.replace("{module}", SOLUTION_MODULE)
        .replace("{entry_point}", entry_point)
        .replace("{solution}", solution)
    )
