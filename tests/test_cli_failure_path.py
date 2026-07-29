"""The call-failure path, which took down an entire overnight campaign.

`_failed_record` referenced names that were locals of its caller, so it raised
NameError the moment a model call failed. Because the orchestrator let any
exception escape, one transient CLI failure aborted all 756 units, and the
supervisor's retries restarted from the beginning and hit the same wall eight
times.
"""

from types import SimpleNamespace

from ruleprobe.cli import _failed_record, _run_unit


def condition():
    return SimpleNamespace(
        id="control",
        predicted_failure="baseline",
        system_prompt=lambda base: base,
    )


def python_task():
    return SimpleNamespace(
        task_id="t.py::f",
        entry_point="f",
        prompt="def f():\n    '''doc'''\n",
        canonical_solution="    return 1\n",
        full_solution="def f():\n    '''doc'''\n    return 1\n",
    )


def solidity_task():
    return SimpleNamespace(
        task_id="src/C.sol",
        contract="C",
        entry_file="src/C.sol",
        closure=["src/C.sol"],
        source="contract C {}",
    )


def test_failed_record_builds_for_a_python_task():
    record = _failed_record(condition(), python_task(), "sys", "user", "boom", 0, "f")
    assert record["validity_outcome"] == "call_failed"
    assert record["kill_rate"] is None
    assert record["sample"] == 0


def test_failed_record_builds_for_a_solidity_task():
    """Solidity tasks have no `entry_point` attribute, so a handler that reaches
    for one turns a recoverable failure into a fatal crash."""
    record = _failed_record(condition(), solidity_task(), "sys", "user", "boom", 2, "C")
    assert record["entry_point"] == "C"
    assert record["sample"] == 2


def test_a_failing_model_call_yields_a_record_rather_than_raising(monkeypatch):
    """One transient failure must cost one unit, not the whole run."""
    def explode(*args, **kwargs):
        raise RuntimeError("claude exited 1: ")

    monkeypatch.setattr("ruleprobe.cli.call_model", explode)
    record = _run_unit(condition(), python_task(), "base", {}, "sonnet", 0, "py", None)
    assert record["validity_outcome"] == "call_failed"


def test_an_unexpected_error_also_yields_a_record(monkeypatch):
    """Catching only RuntimeError and OSError is too narrow: the handler itself
    raised NameError, which escaped and killed the orchestrator."""
    def explode(*args, **kwargs):
        raise ValueError("something nobody predicted")

    monkeypatch.setattr("ruleprobe.cli.call_model", explode)
    record = _run_unit(condition(), python_task(), "base", {}, "sonnet", 0, "py", None)
    assert record["validity_outcome"] == "call_failed"


def test_a_solidity_scoring_failure_does_not_escape(monkeypatch):
    monkeypatch.setattr(
        "ruleprobe.cli.call_model",
        lambda *a, **k: SimpleNamespace(text="```solidity\ncontract T {}\n```", cost_usd=0.0),
    )
    def explode(*args, **kwargs):
        raise RuntimeError("forge blew up")

    monkeypatch.setattr("ruleprobe.cli.score_solidity_suite", explode)
    record = _run_unit(condition(), solidity_task(), "base", {}, "sonnet", 1, "sol", None)
    assert record["validity_outcome"] == "call_failed"
    assert record["sample"] == 1
