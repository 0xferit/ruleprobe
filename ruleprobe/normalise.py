"""Repairs the import line so test quality can be measured separately from it.

Several rules cause the model to ignore the explicit "importable as
`from solution import X`" instruction and invent a placeholder module name.
That is a real instruction-following effect and is reported as its own metric,
but left alone it would also make the suite unimportable, and an unimportable
suite yields no information about test quality at all — one effect would mask
the other.

Rewriting the module name changes no assertion and weakens no test. It only
restores the mechanical precondition for scoring. The rate at which it was
needed is reported alongside the results.
"""

from __future__ import annotations

import ast

from ruleprobe.execute import SOLUTION_MODULE


def normalise_import(test_source: str, entry_point: str) -> tuple[str, bool]:
    """Points any import of `entry_point` at the real solution module.

    Keyed on the entry point, so genuine imports of other modules are never
    touched. Returns the source and whether a rewrite was needed.
    """
    try:
        tree = ast.parse(test_source)
    except SyntaxError:
        return test_source, False

    wrong_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module
        and node.module != SOLUTION_MODULE
        and any(alias.name == entry_point for alias in node.names)
    }
    if not wrong_modules:
        return test_source, False

    lines = test_source.splitlines(keepends=True)
    for index, line in enumerate(lines):
        stripped = line.lstrip()
        for module in wrong_modules:
            if stripped.startswith(f"from {module} import "):
                indent = line[: len(line) - len(stripped)]
                lines[index] = indent + stripped.replace(
                    f"from {module} import ", f"from {SOLUTION_MODULE} import ", 1
                )
    return "".join(lines), True
