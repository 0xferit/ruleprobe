"""Single-site mutation of Solidity source.

Python mutation goes through `ast`, which cannot accidentally touch a comment.
Solidity has no such module in the standard library, and a naive regex over raw
source will happily rewrite an operator inside a NatSpec comment or a revert
string. Both are silent corruptions: the first alters the specification the
model is scored against, the second changes nothing but produces a diff that
looks like a real mutant.

So the source is masked first: strings and comments are blanked to spaces,
preserving length, and operator positions are found in the masked text and
applied to the original.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass

# Longest first: `<=` must match before `<`, or the mutant becomes `<==`.
OPERATOR_SWAPS: list[tuple[str, str, str]] = [
    ("comparison", "<=", "<"),
    ("comparison", ">=", ">"),
    ("comparison", "==", "!="),
    ("comparison", "!=", "=="),
    ("boolean", "&&", "||"),
    ("boolean", "||", "&&"),
    ("comparison", "<", "<="),
    ("comparison", ">", ">="),
    ("arithmetic", "+", "-"),
    ("arithmetic", "-", "+"),
    ("arithmetic", "*", "/"),
    ("arithmetic", "/", "*"),
]

# An operator preceded or followed by any of these is part of a larger token:
# `+=`, `=>`, `->`, `**`, `//`. Mutating those changes syntax, not behaviour.
GLUE_CHARACTERS = frozenset("=<>+-*/&|!")
INTEGER_LITERAL = re.compile(r"\b\d[\d_]*\b")
ASSEMBLY_BLOCK = re.compile(r"\bassembly\b[^{]*\{")
BOUNDARY_SHIFT = 1


@dataclass(frozen=True)
class Mutant:
    operator: str
    source: str


def mask_strings_and_comments(source: str) -> str:
    """Blanks strings and comments to spaces, preserving every offset.

    Length preservation is what lets positions found in the masked text be
    applied directly to the original.
    """
    out = list(source)
    index = 0
    length = len(source)

    while index < length:
        char = source[index]

        if char == "/" and index + 1 < length and source[index + 1] == "/":
            while index < length and source[index] != "\n":
                out[index] = " "
                index += 1
        elif char == "/" and index + 1 < length and source[index + 1] == "*":
            while index < length and not (source[index] == "*" and index + 1 < length and source[index + 1] == "/"):
                out[index] = " "
                index += 1
            for _ in range(2):
                if index < length:
                    out[index] = " "
                    index += 1
        elif char in ('"', "'"):
            quote = char
            out[index] = " "
            index += 1
            while index < length and source[index] != quote:
                if source[index] == "\\" and index + 1 < length:
                    out[index] = " "
                    index += 1
                out[index] = " "
                index += 1
            if index < length:
                out[index] = " "
                index += 1
        else:
            index += 1

    return "".join(out)


def mask_assembly(source: str, masked: str) -> str:
    """Blanks Yul blocks, preserving offsets.

    Literals inside `assembly` are memory offsets, selectors and revert
    arguments, not domain values. Shifting `revert(0, 0)` to `revert(1, 0)`
    produces a diff no test can observe, so mutating there fills the pool with
    unkillable noise and depresses every condition's score equally.
    """
    out = list(masked)
    for match in ASSEMBLY_BLOCK.finditer(masked):
        depth = 0
        for index in range(match.end() - 1, len(masked)):
            if masked[index] == "{":
                depth += 1
            elif masked[index] == "}":
                depth -= 1
                if depth == 0:
                    break
            out[index] = " "
    return "".join(out)


def generate_solidity_mutants(source: str, max_mutants: int, seed: int) -> list[Mutant]:
    """Up to `max_mutants` distinct single-site mutants, spread across operators."""
    masked = mask_assembly(source, mask_strings_and_comments(source))
    candidates: list[Mutant] = []

    for operator, original, replacement in OPERATOR_SWAPS:
        for position in _find_isolated(masked, original):
            mutated = source[:position] + replacement + source[position + len(original) :]
            candidates.append(Mutant(operator, mutated))

    for match in INTEGER_LITERAL.finditer(masked):
        text = match.group()
        if not text.replace("_", "").isdigit():
            continue
        shifted = str(int(text.replace("_", "")) + BOUNDARY_SHIFT)
        candidates.append(
            Mutant("boundary", source[: match.start()] + shifted + source[match.end() :])
        )

    unique: dict[str, Mutant] = {}
    for mutant in candidates:
        if mutant.source != source and mutant.source not in unique:
            unique[mutant.source] = mutant

    ordered = sorted(unique.values(), key=lambda m: (m.operator, m.source))
    if len(ordered) <= max_mutants:
        return ordered
    return sorted(_stratified_sample(ordered, max_mutants, seed), key=lambda m: (m.operator, m.source))


def _stratified_sample(mutants: list[Mutant], count: int, seed: int) -> list[Mutant]:
    """Round-robins across operators before taking a second from any one.

    Integer literals outnumber comparisons several-fold in real contracts, so a
    uniform sample returns almost nothing but boundary shifts and never
    exercises the comparison flips a test suite most needs to catch.
    """
    rng = random.Random(seed)
    buckets: dict[str, list[Mutant]] = {}
    for mutant in mutants:
        buckets.setdefault(mutant.operator, []).append(mutant)
    for bucket in buckets.values():
        rng.shuffle(bucket)

    picked: list[Mutant] = []
    while len(picked) < count and any(buckets.values()):
        for operator in sorted(buckets):
            if buckets[operator] and len(picked) < count:
                picked.append(buckets[operator].pop())
    return picked


def _find_isolated(masked: str, token: str) -> list[int]:
    """Positions of `token` that are not part of a longer operator.

    Without the neighbour check, `a += 1` yields `a =+ 1`, which compiles and
    means something else, and `mapping(address => uint)` gets rewritten into
    invalid syntax.
    """
    positions = []
    start = 0
    while True:
        index = masked.find(token, start)
        if index == -1:
            return positions
        start = index + 1

        before = masked[index - 1] if index > 0 else ""
        after_index = index + len(token)
        after = masked[after_index] if after_index < len(masked) else ""

        if before in GLUE_CHARACTERS or after in GLUE_CHARACTERS:
            continue
        positions.append(index)
