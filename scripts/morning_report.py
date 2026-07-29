"""Writes MORNING-REPORT.md from whatever the overnight run produced.

Deliberately tolerant: a partial or failed campaign must still yield an honest
report rather than a crash, because nobody is awake to read a stack trace.

All statistics come from `ruleprobe.stats`. Re-deriving the pairing rule or the
outcome classification here would give the report a second, quietly diverging
implementation of the numbers the repo publishes.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ruleprobe.conditions import CONTROL
from ruleprobe.runs import latest_run, planned_units
from ruleprobe.stats import paired_deltas, summarise

OUT = Path("MORNING-REPORT.md")


def main() -> None:
    directory, records = latest_run(solidity_only=True)
    if not records:
        OUT.write_text("# Morning report\n\nNo Solidity records were produced.\n")
        return

    spent = sum(r.get("cost_usd") or 0.0 for r in records)
    tasks = {r["task_id"] for r in records}
    conditions = {r["condition"] for r in records}
    samples = len({r.get("sample", 0) for r in records})
    expected = planned_units(records)

    table = summarise(records)
    deltas = paired_deltas(records, baseline=CONTROL)

    lines = [
        "# Morning report",
        "",
        f"Run `{directory.name}` — {len(records)} of {expected} planned units, "
        f"{len(tasks)} tasks x {len(conditions)} conditions x {samples} samples, "
        f"${spent:.2f}.",
        "",
    ]
    if len(records) < expected:
        lines += [
            f"**Incomplete: {expected - len(records)} units missing.** Re-running "
            "`scripts/campaign.sh sol` resumes from cache and only pays for the rest.",
            "",
        ]

    lines += [
        "## Kill rate, paired against control",
        "",
        "| condition | valid | kill rate | Δ vs control | 95% CI | paired n | verdict |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in table:
        condition = row["condition"]
        delta = deltas.get(condition)
        if condition == CONTROL:
            lines.append(
                f"| `{condition}` | {row['valid_rate']:.0%} | {row['kill_rate']:.3f} "
                "| — | — | — | baseline |"
            )
        elif delta is None:
            lines.append(
                f"| `{condition}` | {row['valid_rate']:.0%} | {row['kill_rate']:.3f} "
                "| — | — | 0 | no shared tasks |"
            )
        else:
            resolved = delta["low"] > 0 or delta["high"] < 0
            lines.append(
                f"| `{condition}` | {row['valid_rate']:.0%} | {row['kill_rate']:.3f} "
                f"| {delta['mean']:+.3f} | [{delta['low']:+.3f}, {delta['high']:+.3f}] "
                f"| {delta['n']} | {'**resolved**' if resolved else 'not resolved'} |"
            )

    lines += [
        "",
        "## Suites that failed to build",
        "",
        "A suite that does not compile says nothing about whether a mutation was",
        "detected, so these are excluded from kill rate and counted here instead.",
        "",
        "| condition | units | build errors | assertion failures | other invalid |",
        "|---|---|---|---|---|",
    ]
    for row in table:
        lines.append(
            f"| `{row['condition']}` | {row['n']} | {row['invalid_error']} "
            f"| {row['invalid_failed']} | {row['invalid_other']} |"
        )

    lines += [
        "",
        "## Test volume",
        "",
        "| condition | mean tests per suite |",
        "|---|---|",
    ]
    for row in table:
        lines.append(f"| `{row['condition']}` | {row['mean_tests']:.1f} |")

    lines += [
        "",
        "## Caveats that survive any result above",
        "",
        "- Intervals crossing zero mean the effect was not resolved, not that it is",
        "  absent. Resolving effects near 0.014 needs roughly 33 tasks.",
        "- Three samples per cell, chosen on evidence: the variance pilot measured",
        "  mean within-cell SD at 0.0312 with a median of 0.0000, so variance lives",
        "  between tasks rather than within cells.",
        "- Tasks were feasibility-screened by a prompt outside the nine conditions.",
        "  Screening on a condition's own success would have biased the comparison.",
        "- Absolute rates do not transfer to a bare API call: the Claude Code CLI",
        "  contributes fixed harness context to every call, and exposes no",
        "  temperature control.",
        "",
    ]
    OUT.write_text("\n".join(lines) + "\n")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
