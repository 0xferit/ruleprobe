import ast
import textwrap

from ruleprobe.repo import slice_function

MODULE = textwrap.dedent('''
    """Module docstring."""
    import math
    from decimal import Decimal

    TICK = 0.01
    UNUSED = "not needed"

    def _round_to_tick(value):
        return round(value / TICK) * TICK

    def unrelated(x):
        return math.sqrt(x)

    def price_bands(center, count):
        """Return `count` price levels around `center`.

        Levels are rounded to the exchange tick size.
        """
        out = []
        for i in range(count):
            out.append(_round_to_tick(center * (1 + i * 0.001)))
        return out
''')


def sliced(name=MODULE, fn="price_bands"):
    return slice_function(ast.parse(name), name, fn)


def test_slice_is_syntactically_valid():
    ast.parse(sliced().full_source)


def test_slice_carries_transitively_needed_definitions():
    src = sliced().full_source
    assert "TICK = 0.01" in src
    assert "def _round_to_tick" in src


def test_slice_drops_unneeded_module_symbols():
    """Carrying the whole module would hand the model context the real caller
    never gives it, and would add mutation sites outside the function."""
    src = sliced().full_source
    assert "UNUSED" not in src
    assert "def unrelated" not in src


def test_slice_keeps_only_imports_that_are_used():
    src = sliced().full_source
    assert "Decimal" not in src


def test_prompt_ends_at_the_docstring_and_body_is_separate():
    """Mirrors the HumanEval layout so mutate/score work unchanged: the model
    sees signature plus docstring, the body is the thing being mutated."""
    s = sliced()
    assert s.prompt.rstrip().endswith('"""')
    assert "Return `count` price levels" in s.prompt
    assert "out = []" not in s.prompt
    assert "out = []" in s.solution


def test_prompt_plus_solution_reconstructs_the_slice():
    s = sliced()
    assert s.prompt + s.solution == s.full_source


RELATIVE = textwrap.dedent('''
    from ..domain import Symbol
    from .helpers import tidy

    def label(raw):
        """Return a display label for a raw symbol string, tidied for output."""
        return tidy(Symbol(raw)) + "!"
''')


def test_relative_imports_are_resolved_to_absolute_ones():
    """A slice runs standalone, outside the package, so `from ..domain import`
    has no parent to resolve against and would fail at import time."""
    s = slice_function(
        ast.parse(RELATIVE), RELATIVE, "label", module_package="pkg.utilities"
    )
    assert "from pkg.domain import Symbol" in s.full_source
    assert "from pkg.utilities.helpers import tidy" in s.full_source
    assert "from .." not in s.full_source


def test_relative_imports_are_left_alone_without_a_package_context():
    s = slice_function(ast.parse(RELATIVE), RELATIVE, "label")
    assert "from ..domain import Symbol" in s.full_source


def test_function_with_an_unresolvable_name_is_rejected():
    src = "def f(x):\n    \"\"\"Docstring long enough to count as a spec here.\"\"\"\n    return helper(x)\n"
    assert slice_function(ast.parse(src), src, "f") is None


def test_missing_function_is_rejected():
    assert slice_function(ast.parse(MODULE), MODULE, "nope") is None
