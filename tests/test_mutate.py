import ast

import pytest

from ruleprobe.mutate import generate_mutants

SORTED_CHECK = '''
def is_sorted(xs):
    """Return True if xs is non-decreasing."""
    for i in range(len(xs) - 1):
        if xs[i] > xs[i + 1]:
            return False
    return True
'''

NOTHING_TO_MUTATE = '''
def identity(x):
    """Return x."""
    return x
'''


def test_every_mutant_is_syntactically_valid():
    for m in generate_mutants(SORTED_CHECK, max_mutants=20, seed=1):
        ast.parse(m.source)


def test_every_mutant_differs_from_the_original():
    for m in generate_mutants(SORTED_CHECK, max_mutants=20, seed=1):
        assert m.source.strip() != SORTED_CHECK.strip()


def test_mutants_are_unique():
    sources = [m.source for m in generate_mutants(SORTED_CHECK, max_mutants=20, seed=1)]
    assert len(sources) == len(set(sources))


def test_function_with_no_mutable_site_yields_no_mutants():
    assert generate_mutants(NOTHING_TO_MUTATE, max_mutants=20, seed=1) == []


def test_comparison_operator_is_actually_replaced():
    mutants = generate_mutants(SORTED_CHECK, max_mutants=50, seed=1)
    comparison = [m for m in mutants if m.operator == "comparison"]
    assert comparison, "expected at least one comparison mutant"
    assert any(">=" in m.source or "<" in m.source for m in comparison)


def test_generation_is_deterministic_for_a_fixed_seed():
    a = generate_mutants(SORTED_CHECK, max_mutants=10, seed=7)
    b = generate_mutants(SORTED_CHECK, max_mutants=10, seed=7)
    assert [m.source for m in a] == [m.source for m in b]


def test_docstrings_are_never_mutated():
    """The docstring is the spec the model is scored against; corrupting it
    would silently invalidate the whole comparison."""
    for m in generate_mutants(SORTED_CHECK, max_mutants=50, seed=1):
        tree = ast.parse(m.source)
        fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
        assert ast.get_docstring(fn) == "Return True if xs is non-decreasing."


def test_max_mutants_is_respected():
    assert len(generate_mutants(SORTED_CHECK, max_mutants=3, seed=1)) == 3


def test_each_mutant_changes_exactly_one_site():
    """Single-site mutation is what makes a kill attributable to one operator.
    A mutant differing at two sites would confound which change the suite caught."""
    original = ast.dump(ast.parse(SORTED_CHECK))
    for m in generate_mutants(SORTED_CHECK, max_mutants=20, seed=1):
        assert _dump_distance(original, ast.dump(ast.parse(m.source))) == 1


def _dump_distance(a: str, b: str) -> int:
    """Counts differing tokens between two AST dumps; 1 means a single edit."""
    ta, tb = a.replace("(", " ").replace(")", " ").split(), b.replace("(", " ").replace(")", " ").split()
    if len(ta) != len(tb):
        return abs(len(ta) - len(tb)) or 1
    return sum(1 for x, y in zip(ta, tb) if x != y)
