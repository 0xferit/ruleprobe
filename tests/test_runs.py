import json

from ruleprobe.runs import latest_run, planned_units


def write(directory, records):
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "records.jsonl").write_text("".join(json.dumps(r) + "\n" for r in records))


def record(task_id="src/A.sol", condition="control", sample=0):
    return {"task_id": task_id, "condition": condition, "sample": sample}


def test_latest_run_picks_the_newest(tmp_path):
    write(tmp_path / "20260101T000000Z", [record()])
    write(tmp_path / "20260202T000000Z", [record(task_id="src/B.sol")])
    directory, records = latest_run(tmp_path)
    assert directory.name == "20260202T000000Z"
    assert records[0]["task_id"] == "src/B.sol"


def test_latest_run_skips_empty_records(tmp_path):
    write(tmp_path / "20260101T000000Z", [record()])
    write(tmp_path / "20260202T000000Z", [])
    directory, _ = latest_run(tmp_path)
    assert directory.name == "20260101T000000Z"


def test_solidity_filter_skips_python_runs(tmp_path):
    write(tmp_path / "20260101T000000Z", [record(task_id="src/A.sol")])
    write(tmp_path / "20260202T000000Z", [record(task_id="utils.py::f")])
    directory, _ = latest_run(tmp_path, solidity_only=True)
    assert directory.name == "20260101T000000Z"


def test_missing_runs_dir_is_not_an_error(tmp_path):
    assert latest_run(tmp_path / "nope") == (None, [])


def test_planned_units_multiplies_tasks_conditions_and_samples():
    from ruleprobe.conditions import CONDITION_IDS

    records = [record(task_id=f"src/{i}.sol", sample=s) for i in range(4) for s in range(3)]
    assert planned_units(records) == 4 * len(CONDITION_IDS) * 3


def test_planned_units_never_undercounts_what_is_already_done():
    """Early in a run only some conditions have appeared, so the naive product
    can fall below the number of records already written."""
    records = [record(condition=f"c{i}") for i in range(200)]
    assert planned_units(records) >= 200


def test_planned_units_of_nothing_is_zero():
    assert planned_units([]) == 0


def test_usable_units_excludes_failed_calls():
    """A run whose calls all failed has a full record count and looks complete.
    The watchdog stopped on exactly that, declaring 756/756 when 465 of those
    records were failure placeholders holding no data."""
    from ruleprobe.runs import usable_units

    records = [
        {"validity_outcome": "passed"},
        {"validity_outcome": "failed"},
        {"validity_outcome": "error"},
        {"validity_outcome": "call_failed"},
        {"validity_outcome": "call_failed"},
    ]
    assert usable_units(records) == 3


def test_usable_units_of_nothing_is_zero():
    from ruleprobe.runs import usable_units

    assert usable_units([]) == 0
