"""Static detectors for tests that cannot buy information.

Every detector is a pure AST rule with no model in the loop. That is
deliberate: an LLM judge would be one more thing capable of being gamed by the
prompt under test, and would make results impossible to re-derive offline from
the committed transcripts.

These are secondary evidence. Mutation kill rate is the primary metric, because
a suite can be free of every smell here and still catch nothing.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass

from ruleprobe.execute import SOLUTION_MODULE

MOCK_FUNCTIONS = {"patch", "patch.object", "MagicMock", "Mock", "AsyncMock"}
ASSERTING_CONTEXT_MANAGERS = {"raises", "warns", "deprecated_call"}


@dataclass(frozen=True)
class Report:
    tests: int
    assertions: int
    assertion_free: int
    tautological: int
    mocks_sut: int
    trivial_assert: int

    @property
    def assertion_density(self) -> float:
        return self.assertions / self.tests if self.tests else 0.0


def analyze(test_source: str, entry_point: str) -> Report:
    """Counts information-free patterns in a generated suite.

    An unparseable suite reports zeros rather than raising: a syntactically
    broken suite is already captured as an execution error, and crashing here
    would lose the rest of the run.
    """
    try:
        tree = ast.parse(test_source)
    except SyntaxError:
        return Report(0, 0, 0, 0, 0, 0)

    test_functions = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test")
    ]

    assertions = 0
    assertion_free = 0
    tautological = 0
    mocks_sut = 0
    trivial = 0

    for function in test_functions:
        asserts = [n for n in ast.walk(function) if isinstance(n, ast.Assert)]
        assertions += len(asserts)

        if not asserts and not _has_asserting_context(function):
            assertion_free += 1

        sut_derived = _variables_assigned_from(function, entry_point)
        if any(_is_tautological(a, entry_point, sut_derived) for a in asserts):
            tautological += 1
        if any(_is_trivial(a) for a in asserts):
            trivial += 1
        if _mocks_system_under_test(function, entry_point):
            mocks_sut += 1

    return Report(
        tests=len(test_functions),
        assertions=assertions,
        assertion_free=assertion_free,
        tautological=tautological,
        mocks_sut=mocks_sut,
        trivial_assert=trivial,
    )


def _has_asserting_context(function: ast.AST) -> bool:
    """True when the test asserts via `pytest.raises`/`warns` rather than `assert`."""
    for node in ast.walk(function):
        if isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                if isinstance(item.context_expr, ast.Call):
                    if _called_name(item.context_expr) in ASSERTING_CONTEXT_MANAGERS:
                        return True
    return False


def _called_name(call: ast.Call) -> str:
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    if isinstance(call.func, ast.Name):
        return call.func.id
    return ""


def _calls_entry_point(node: ast.AST, entry_point: str) -> bool:
    return any(
        isinstance(n, ast.Call) and _called_name(n) == entry_point
        for n in ast.walk(node)
    )


def _variables_assigned_from(function: ast.AST, entry_point: str) -> set[str]:
    """Names bound to the result of calling the function under test.

    Comparing a fresh call against one of these is the indirect form of
    asserting that the implementation equals itself.
    """
    derived: set[str] = set()
    for node in ast.walk(function):
        if isinstance(node, ast.Assign) and _calls_entry_point(node.value, entry_point):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    derived.add(target.id)
    return derived


def _is_tautological(node: ast.Assert, entry_point: str, sut_derived: set[str]) -> bool:
    if not isinstance(node.test, ast.Compare):
        return False
    left, right = node.test.left, node.test.comparators[0]

    if _calls_entry_point(left, entry_point) and _calls_entry_point(right, entry_point):
        return True

    for call_side, other_side in ((left, right), (right, left)):
        if _calls_entry_point(call_side, entry_point):
            if isinstance(other_side, ast.Name) and other_side.id in sut_derived:
                return True
    return False


def _is_trivial(node: ast.Assert) -> bool:
    if isinstance(node.test, ast.Constant):
        return True
    if isinstance(node.test, ast.Compare) and isinstance(node.test.ops[0], ast.Eq):
        left, right = node.test.left, node.test.comparators[0]
        return ast.dump(left) == ast.dump(right)
    return False


def _mocks_system_under_test(function: ast.AST, entry_point: str) -> bool:
    """True when a patch target names the solution module or the entry point.

    Patching a genuine external dependency is correct practice and must not be
    flagged, so only these two targets count.
    """
    targets: list[str] = []

    for decorator in getattr(function, "decorator_list", []):
        if isinstance(decorator, ast.Call) and _called_name(decorator) == "patch":
            targets.extend(_string_arguments(decorator))

    for node in ast.walk(function):
        if isinstance(node, ast.Call) and _called_name(node) in MOCK_FUNCTIONS:
            targets.extend(_string_arguments(node))

    return any(
        target == entry_point
        or target.startswith(f"{SOLUTION_MODULE}.")
        or target == SOLUTION_MODULE
        for target in targets
    )


def _string_arguments(call: ast.Call) -> list[str]:
    return [a.value for a in call.args if isinstance(a, ast.Constant) and isinstance(a.value, str)]
