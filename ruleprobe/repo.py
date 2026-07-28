"""Turns functions in a real Python package into ruleprobe tasks.

HumanEval saturates the kill-rate metric: its functions are short enough that
any competent suite catches every planted bug, so a bad rule has no room to do
damage. Real repository code has that headroom. This module supplies it.

The unit is a *slice*: one function plus the transitive closure of the
module-level names it needs, and nothing else. Carrying the whole module would
hand the model context its real callers never provide, and would add mutation
sites outside the function under test.

The output matches the HumanEval layout exactly — a `prompt` ending at the
docstring and a separate body — so mutation, execution and scoring work
unchanged.
"""

from __future__ import annotations

import ast
import builtins
from dataclasses import dataclass
from pathlib import Path

BUILTIN_NAMES = frozenset(dir(builtins))
MIN_DOCSTRING_CHARS = 40
MIN_MUTATION_SITES = 2
INSTANCE_PARAMETERS = frozenset({"self", "cls"})


@dataclass(frozen=True)
class Slice:
    entry_point: str
    prompt: str
    solution: str

    @property
    def full_source(self) -> str:
        return self.prompt + self.solution


def slice_function(
    tree: ast.Module,
    source: str,
    entry_point: str,
    module_package: str | None = None,
) -> Slice | None:
    """Extracts `entry_point` plus everything at module level it depends on.

    Returns None when the function is absent or references a name that is not
    defined in this module, since the slice would not run standalone.

    `module_package` is the dotted package containing the module, e.g.
    `pkg.utilities`. Given it, relative imports are rewritten to absolute ones;
    a slice executes outside the package, so `from ..domain import X` has no
    parent to resolve against and would fail at import time.
    """
    target = next(
        (
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == entry_point
        ),
        None,
    )
    if target is None:
        return None

    provided = _module_symbols(tree)
    needed = _transitive_dependencies(target, provided)
    if needed is None:
        return None

    preamble = _render_preamble(tree, needed, source, module_package)
    prompt_tail, body = _split_at_docstring(target, source)
    prompt = f"{preamble}{prompt_tail}" if preamble else prompt_tail
    return Slice(entry_point=entry_point, prompt=prompt, solution=body)


def find_candidates(
    package_root: Path,
    min_sites: int = MIN_MUTATION_SITES,
) -> list[tuple[Path, str, int]]:
    """Finds sliceable, documented, mutable functions, richest in sites first."""
    found: list[tuple[Path, str, int]] = []
    for path in sorted(package_root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        source = path.read_text()
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        for node in tree.body:
            if not isinstance(node, ast.FunctionDef):
                continue
            docstring = ast.get_docstring(node)
            if not docstring or len(docstring) < MIN_DOCSTRING_CHARS:
                continue
            if _parameters(node)[:1] and _parameters(node)[0] in INSTANCE_PARAMETERS:
                continue
            if not _returns_a_value(node):
                continue
            if not is_safe_to_execute(node):
                continue
            sites = _mutation_sites(node)
            if sites < min_sites:
                continue
            if slice_function(tree, source, node.name) is None:
                continue
            found.append((path, node.name, sites))
    return sorted(found, key=lambda row: (-row[2], str(row[0]), row[1]))


def _returns_a_value(function: ast.FunctionDef) -> bool:
    """Excludes procedures that only print or mutate state.

    A mutation in such a function is invisible through the return value, so a
    generated suite cannot be scored fairly on catching it.
    """
    return any(
        isinstance(node, ast.Return) and node.value is not None
        for node in ast.walk(function)
    )


def _mutation_sites(function: ast.FunctionDef) -> int:
    operators = sum(
        1
        for node in ast.walk(function)
        if isinstance(node, (ast.Compare, ast.BinOp, ast.BoolOp))
    )
    constants = sum(
        1
        for node in ast.walk(function)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float, bool))
    )
    return operators + constants


def _parameters(function: ast.FunctionDef) -> list[str]:
    args = function.args
    names = [a.arg for a in args.posonlyargs + args.args + args.kwonlyargs]
    if args.vararg:
        names.append(args.vararg.arg)
    if args.kwarg:
        names.append(args.kwarg.arg)
    return names


def _module_symbols(tree: ast.Module) -> dict[str, ast.stmt]:
    symbols: dict[str, ast.stmt] = {}
    for statement in tree.body:
        if isinstance(statement, (ast.Import, ast.ImportFrom)):
            for alias in statement.names:
                symbols[(alias.asname or alias.name).split(".")[0]] = statement
        elif isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            symbols[statement.name] = statement
        elif isinstance(statement, ast.Assign):
            for target in statement.targets:
                if isinstance(target, ast.Name):
                    symbols[target.id] = statement
        elif isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
            symbols[statement.target.id] = statement
    return symbols


def _bound_names(node: ast.AST, parameters: list[str]) -> set[str]:
    bound = set(parameters)
    for child in ast.walk(node):
        if isinstance(child, ast.Assign):
            for target in child.targets:
                bound |= {n.id for n in ast.walk(target) if isinstance(n, ast.Name)}
        elif isinstance(child, (ast.For, ast.AsyncFor, ast.comprehension)):
            bound |= {n.id for n in ast.walk(child.target) if isinstance(n, ast.Name)}
        elif isinstance(child, ast.withitem) and child.optional_vars:
            bound |= {n.id for n in ast.walk(child.optional_vars) if isinstance(n, ast.Name)}
        elif isinstance(child, ast.AnnAssign) and isinstance(child.target, ast.Name):
            bound.add(child.target.id)
        elif isinstance(child, ast.ExceptHandler) and child.name:
            bound.add(child.name)
        elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child is not node:
            bound.add(child.name)
    return bound


def _free_names(node: ast.AST, parameters: list[str]) -> set[str]:
    bound = _bound_names(node, parameters)
    return {
        child.id
        for child in ast.walk(node)
        if isinstance(child, ast.Name)
        and isinstance(child.ctx, ast.Load)
        and child.id not in bound
        and child.id not in BUILTIN_NAMES
    }


def _transitive_dependencies(
    target: ast.FunctionDef,
    provided: dict[str, ast.stmt],
) -> set[str] | None:
    """Closure of module-level names the function needs, or None if any is absent."""
    needed: set[str] = set()
    seen: set[str] = set()
    pending = list(_free_names(target, _parameters(target)))

    while pending:
        name = pending.pop()
        if name in seen:
            continue
        seen.add(name)
        definition = provided.get(name)
        if definition is None:
            return None
        needed.add(name)
        if isinstance(definition, (ast.FunctionDef, ast.AsyncFunctionDef)):
            pending += list(_free_names(definition, _parameters(definition)))
        elif isinstance(definition, (ast.ClassDef, ast.Assign, ast.AnnAssign)):
            pending += list(_free_names(definition, []))

    return needed


def _render_preamble(
    tree: ast.Module,
    needed: set[str],
    source: str,
    module_package: str | None = None,
) -> str:
    """Emits the needed module-level statements in their original order."""
    lines = source.splitlines(keepends=True)
    chunks: list[str] = []

    for statement in tree.body:
        names = _names_defined_by(statement)
        if not names & needed:
            continue
        if isinstance(statement, (ast.Import, ast.ImportFrom)):
            chunks.append(_render_import(statement, needed, module_package))
        else:
            chunks.append("".join(lines[statement.lineno - 1 : statement.end_lineno]))

    return "".join(chunk if chunk.endswith("\n") else chunk + "\n" for chunk in chunks) + (
        "\n" if chunks else ""
    )


def _names_defined_by(statement: ast.stmt) -> set[str]:
    if isinstance(statement, (ast.Import, ast.ImportFrom)):
        return {(a.asname or a.name).split(".")[0] for a in statement.names}
    if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return {statement.name}
    if isinstance(statement, ast.Assign):
        return {n.id for t in statement.targets for n in ast.walk(t) if isinstance(n, ast.Name)}
    if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
        return {statement.target.id}
    return set()


def _render_import(
    statement: ast.Import | ast.ImportFrom,
    needed: set[str],
    module_package: str | None = None,
) -> str:
    """Rebuilds an import with only the aliases actually used."""
    kept = [a for a in statement.names if (a.asname or a.name).split(".")[0] in needed]
    if isinstance(statement, ast.Import):
        return "import " + ", ".join(_alias_text(a) for a in kept)
    module = _absolute_module(statement, module_package)
    return f"from {module} import " + ", ".join(_alias_text(a) for a in kept)


def _absolute_module(statement: ast.ImportFrom, module_package: str | None) -> str:
    """Resolves a relative import against the package that contains the module."""
    if not statement.level or module_package is None:
        return "." * statement.level + (statement.module or "")
    parts = module_package.split(".")
    trimmed = parts[: len(parts) - (statement.level - 1)] or parts[:1]
    return ".".join(trimmed + ([statement.module] if statement.module else []))


def _alias_text(alias: ast.alias) -> str:
    return f"{alias.name} as {alias.asname}" if alias.asname else alias.name


def _split_at_docstring(function: ast.FunctionDef, source: str) -> tuple[str, str]:
    """Splits the function into (signature + docstring, body).

    Keeps the HumanEval contract: everything the model is shown lives in the
    prompt, and the part that gets mutated lives in the solution.
    """
    lines = source.splitlines(keepends=True)
    start = min(
        [d.lineno for d in function.decorator_list] + [function.lineno]
    ) - 1
    docstring_node = function.body[0]
    head_end = docstring_node.end_lineno
    body_start = function.body[1].lineno - 1

    head = "".join(lines[start:head_end])
    body = "".join(lines[body_start : function.end_lineno])
    return head, body


# --- Execution safety ---------------------------------------------------
#
# Tasks are handed to a model that writes test code, and that code is then
# executed locally. Against a trading library the obvious hazard is a generated
# test that constructs a client and places an order. Absence of credentials is
# not a control; excluding these functions from the task set is.

SIDE_EFFECT_PARAMETERS = frozenset(
    {"client", "api", "connection", "conn", "session", "ws", "websocket", "socket", "db"}
)
FORBIDDEN_CALLS = frozenset({"input", "eval", "exec", "compile", "__import__"})
FORBIDDEN_MODULES = frozenset(
    {"requests", "httpx", "urllib", "socket", "subprocess", "shutil", "os", "sys", "pickle"}
)
WRITE_MODE_CHARACTERS = frozenset({"w", "a", "x", "+"})


def is_safe_to_execute(function: ast.FunctionDef) -> bool:
    """True when a generated test for this function cannot reach the outside world.

    Matching on parameter names is exact, never substring: `recipient` and
    `sessions_count` are ordinary parameters, and rejecting them would shrink
    the task set for no reason.
    """
    if set(_parameters(function)) & SIDE_EFFECT_PARAMETERS:
        return False

    for node in ast.walk(function):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            if node.func.id in FORBIDDEN_CALLS:
                return False
            if node.func.id == "open" and _opens_for_writing(node):
                return False
        if isinstance(node.func, ast.Attribute):
            root = node.func
            while isinstance(root, ast.Attribute):
                root = root.value
            if isinstance(root, ast.Name) and root.id in FORBIDDEN_MODULES:
                return False

    return True


def _opens_for_writing(call: ast.Call) -> bool:
    mode = call.args[1] if len(call.args) > 1 else None
    for keyword in call.keywords:
        if keyword.arg == "mode":
            mode = keyword.value
    if isinstance(mode, ast.Constant) and isinstance(mode.value, str):
        return bool(set(mode.value) & WRITE_MODE_CHARACTERS)
    return False


RISKY_MODULE_SEGMENTS = frozenset(
    {"client", "clients", "websocket", "websockets", "api", "services", "network"}
)
CLIENT_FACTORY_NAMES = frozenset(
    {"get_client", "create_client", "make_client", "build_client", "connect"}
)


def slice_is_safe(slice_source: str) -> bool:
    """True when nothing in the whole slice can reach a live trading connection.

    Checking the slice rather than the function signature is the point.
    `cancel_order(order_id)` declares no client parameter; it calls `get_client()`
    in its body, so signature inspection alone would let live order cancellation
    into an automated sandbox.

    An unparseable slice is rejected rather than assumed safe.
    """
    try:
        tree = ast.parse(slice_source)
    except SyntaxError:
        return False

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if _names_a_risky_module(node.module):
                return False
        if isinstance(node, ast.Import):
            if any(_names_a_risky_module(alias.name) for alias in node.names):
                return False
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in CLIENT_FACTORY_NAMES:
                return False

    functions = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
    return all(is_safe_to_execute(f) for f in functions)


def _names_a_risky_module(dotted_path: str) -> bool:
    """Substring match on each path segment, unlike the parameter-name check.

    `bitfinex_client` and `client_factory` are both client surfaces but neither
    equals `client`. The costs are asymmetric here: a false positive drops one
    task from the set, a false negative hands live order placement to generated
    test code. Err toward dropping the task.
    """
    return any(
        risky in segment
        for segment in dotted_path.split(".")
        for risky in RISKY_MODULE_SEGMENTS
    )


def freeze_repo_tasks(
    repo_root: Path,
    package_name: str,
    tasks_path: Path,
    mutants_path: Path,
    max_mutants_per_task: int | None = None,
    seed: int | None = None,
) -> tuple[int, int]:
    """Writes a frozen task and mutant set sliced from a real package.

    Mutants are NOT validated against a reference oracle here: unlike HumanEval+,
    a repository has no independent 80x test suite to prove a mutant killable.
    Equivalent mutants are instead filtered post hoc at report time, by dropping
    any mutant that no suite in the run killed. See SCORING.md.
    """
    import json
    from dataclasses import asdict

    from ruleprobe.dataset import Task
    from ruleprobe.validate import ValidatedMutant
    from ruleprobe.mutate import (
        DEFAULT_MAX_MUTANTS_PER_TASK,
        DEFAULT_MUTANT_SEED,
        generate_mutants,
    )

    if max_mutants_per_task is None:
        max_mutants_per_task = DEFAULT_MAX_MUTANTS_PER_TASK
    if seed is None:
        seed = DEFAULT_MUTANT_SEED

    package_root = repo_root / package_name
    tasks: list[Task] = []
    mutants_out: list[ValidatedMutant] = []

    for path, name, _sites in find_candidates(package_root):
        source = path.read_text()
        module_package = ".".join(path.relative_to(repo_root).with_suffix("").parts[:-1])
        sliced = slice_function(ast.parse(source), source, name, module_package)
        if sliced is None or not slice_is_safe(sliced.full_source):
            continue
        if not imports_only_stdlib(sliced.full_source, package_name):
            continue

        task_id = f"{path.relative_to(package_root).as_posix()}::{name}"
        mutants = generate_mutants(sliced.full_source, max_mutants_per_task, seed)
        if not mutants:
            continue

        tasks.append(
            Task(
                task_id=task_id,
                entry_point=name,
                prompt=sliced.prompt,
                canonical_solution=sliced.solution,
            )
        )
        mutants_out += [
            ValidatedMutant(task_id=task_id, operator=m.operator, source=m.source)
            for m in mutants
        ]

    tasks_path.parent.mkdir(parents=True, exist_ok=True)
    # Serialised via the owning dataclasses so these files stay byte-compatible
    # with dataset.load() and validate.load_mutants() if either shape changes.
    with tasks_path.open("w") as f:
        for task in tasks:
            f.write(json.dumps(asdict(task)) + "\n")
    with mutants_path.open("w") as f:
        for mutant in mutants_out:
            f.write(json.dumps(asdict(mutant)) + "\n")

    return len(tasks), len(mutants_out)


def imports_only_stdlib(slice_source: str, package_name: str) -> bool:
    """True when the slice needs nothing from the host package to run.

    Tasks that import the host package would require it on the sandbox path,
    and a generated test could then import the trading modules directly and
    call them, whatever the slice itself contains. Excluding them makes the
    sandbox structurally incapable of reaching a live client, which is a
    stronger guarantee than auditing generated test code after the fact.
    """
    try:
        tree = ast.parse(slice_source)
    except SyntaxError:
        return False

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module.split(".")[0] == package_name:
                return False
        if isinstance(node, ast.Import):
            if any(a.name.split(".")[0] == package_name for a in node.names):
                return False
    return True
