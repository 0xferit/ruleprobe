"""Single-site AST mutation.

A mutant is a copy of a correct solution with exactly one behaviour-changing
edit. Whether a generated test suite turns red on a mutant is the ground truth
for "did this test buy any information", which is the quantity the experiment
is actually measuring.

Generation is deliberately unvalidated: some mutants are semantically
equivalent to the original and no suite can kill them. Filtering those out
requires executing a reference oracle, which is `validate.py`'s job.
"""

from __future__ import annotations

import ast
import copy
import random
from dataclasses import dataclass

COMPARISON_SWAPS: dict[type, type] = {
    ast.Lt: ast.LtE,
    ast.LtE: ast.Lt,
    ast.Gt: ast.GtE,
    ast.GtE: ast.Gt,
    ast.Eq: ast.NotEq,
    ast.NotEq: ast.Eq,
    ast.Is: ast.IsNot,
    ast.IsNot: ast.Is,
    ast.In: ast.NotIn,
    ast.NotIn: ast.In,
}

ARITHMETIC_SWAPS: dict[type, type] = {
    ast.Add: ast.Sub,
    ast.Sub: ast.Add,
    ast.Mult: ast.FloorDiv,
    ast.FloorDiv: ast.Mult,
    ast.Div: ast.Mult,
    ast.Mod: ast.FloorDiv,
    ast.Pow: ast.Mult,
}

BOOLEAN_SWAPS: dict[type, type] = {ast.And: ast.Or, ast.Or: ast.And}

BOUNDARY_SHIFT = 1


@dataclass(frozen=True)
class Mutant:
    operator: str
    source: str


def generate_mutants(source: str, max_mutants: int, seed: int) -> list[Mutant]:
    """Returns up to `max_mutants` distinct single-site mutants of `source`."""
    tree = ast.parse(source)
    docstrings = _docstring_nodes(tree)

    candidates: list[Mutant] = []
    for index, (operator, apply) in enumerate(_sites(tree, docstrings)):
        mutated = copy.deepcopy(tree)
        target = _nth_site(mutated, docstrings, index)
        apply(target)
        try:
            rendered = ast.unparse(mutated)
        except (ValueError, RecursionError):
            continue
        candidates.append(Mutant(operator=operator, source=rendered))

    baseline = ast.unparse(tree)
    unique: dict[str, Mutant] = {}
    for m in candidates:
        if m.source != baseline and m.source not in unique:
            unique[m.source] = m

    ordered = sorted(unique.values(), key=lambda m: (m.operator, m.source))
    if len(ordered) <= max_mutants:
        return ordered
    return sorted(
        random.Random(seed).sample(ordered, max_mutants),
        key=lambda m: (m.operator, m.source),
    )


def _docstring_nodes(tree: ast.AST) -> set[int]:
    """Ids of string constants that serve as docstrings, which must survive
    mutation intact: they are the spec the model is scored against."""
    protected: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                if isinstance(body[0].value.value, str):
                    protected.add(id(body[0].value))
    return protected


def _sites(tree: ast.AST, docstrings: set[int]) -> list[tuple[str, object]]:
    """Enumerates mutable sites as (operator_name, mutation_function) pairs.

    Order is the deterministic `ast.walk` order, which `_nth_site` relies on to
    locate the same site in a fresh deep copy.
    """
    sites: list[tuple[str, object]] = []
    for node in _walk_mutable(tree, docstrings):
        for operator, apply in _mutations_for(node):
            sites.append((operator, apply))
    return sites


def _walk_mutable(tree: ast.AST, docstrings: set[int]) -> list[ast.AST]:
    return [n for n in ast.walk(tree) if id(n) not in docstrings]


def _nth_site(tree: ast.AST, docstrings: set[int], index: int) -> ast.AST:
    """Finds the node owning site `index` in a freshly copied tree.

    Docstring ids differ across copies, so protection is re-derived here rather
    than reusing the caller's id set.
    """
    fresh_docstrings = _docstring_nodes(tree)
    counter = 0
    for node in _walk_mutable(tree, fresh_docstrings):
        for _operator, _apply in _mutations_for(node):
            if counter == index:
                return node
            counter += 1
    raise IndexError(f"no mutation site at index {index}")


def _mutations_for(node: ast.AST) -> list[tuple[str, object]]:
    """The mutations applicable to a single node, in a stable order."""
    out: list[tuple[str, object]] = []

    if isinstance(node, ast.Compare):
        for position, op in enumerate(node.ops):
            replacement = COMPARISON_SWAPS.get(type(op))
            if replacement is not None:
                out.append(("comparison", _replace_compare_op(position, replacement)))

    if isinstance(node, ast.BinOp):
        replacement = ARITHMETIC_SWAPS.get(type(node.op))
        if replacement is not None:
            out.append(("arithmetic", _replace_binop(replacement)))

    if isinstance(node, ast.BoolOp):
        replacement = BOOLEAN_SWAPS.get(type(node.op))
        if replacement is not None:
            out.append(("boolean", _replace_boolop(replacement)))

    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool):
            out.append(("constant", _replace_constant(not node.value)))
        elif isinstance(node.value, int):
            out.append(("boundary", _replace_constant(node.value + BOUNDARY_SHIFT)))
        elif isinstance(node.value, float):
            out.append(("boundary", _replace_constant(node.value + BOUNDARY_SHIFT)))

    return out


def _replace_compare_op(position: int, replacement: type):
    def apply(node: ast.AST) -> None:
        node.ops[position] = replacement()  # type: ignore[attr-defined]

    return apply


def _replace_binop(replacement: type):
    def apply(node: ast.AST) -> None:
        node.op = replacement()  # type: ignore[attr-defined]

    return apply


def _replace_boolop(replacement: type):
    def apply(node: ast.AST) -> None:
        node.op = replacement()  # type: ignore[attr-defined]

    return apply


def _replace_constant(value: object):
    def apply(node: ast.AST) -> None:
        node.value = value  # type: ignore[attr-defined]

    return apply
