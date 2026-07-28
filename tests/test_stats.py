from ruleprobe.stats import paired_deltas, summarise


def record(condition, task_id, kill_rate, valid=True, outcome=None, **detections):
    base = {
        "tests": 2, "assertions": 4, "assertion_free": 0,
        "tautological": 0, "mocks_sut": 0, "trivial_assert": 0,
    }
    base.update(detections)
    return {
        "condition": condition,
        "task_id": task_id,
        "kill_rate": kill_rate,
        "valid": valid,
        "validity_outcome": outcome or ("passed" if valid else "failed"),
        "tests_collected": base["tests"],
        "detections": base,
    }


def test_mechanical_and_assertion_failures_are_reported_separately():
    """An ImportError means the model broke the import contract; a failed
    assertion means it disagreed about behaviour. Merging them would let a
    rename look like a test-quality collapse."""
    records = [
        record("bad", "t1", None, valid=False, outcome="error"),
        record("bad", "t2", None, valid=False, outcome="failed"),
        record("bad", "t3", 1.0),
    ]
    row = summarise(records)[0]
    assert row["invalid_error"] == 1
    assert row["invalid_failed"] == 1


def test_kill_rate_averages_only_valid_suites():
    records = [
        record("control", "t1", 1.0),
        record("control", "t2", None, valid=False),
    ]
    assert summarise(records)[0]["kill_rate"] == 1.0


def test_valid_rate_counts_invalid_suites():
    records = [
        record("control", "t1", 1.0),
        record("control", "t2", None, valid=False),
    ]
    assert summarise(records)[0]["valid_rate"] == 0.5


def test_pairing_drops_tasks_invalid_in_either_arm():
    """A task scored in one arm but not the other cannot contribute a paired
    delta; including it would compare different task sets."""
    records = [
        record("control", "t1", 1.0),
        record("control", "t2", 1.0),
        record("bad", "t1", 0.0),
        record("bad", "t2", None, valid=False),
    ]
    delta = paired_deltas(records, baseline="control")["bad"]
    assert delta["n"] == 1
    assert delta["mean"] == -1.0


def test_baseline_has_no_delta_against_itself():
    records = [record("control", "t1", 1.0)]
    assert "control" not in paired_deltas(records, baseline="control")


def test_bootstrap_is_deterministic():
    records = [record("control", f"t{i}", 1.0) for i in range(10)]
    records += [record("bad", f"t{i}", 0.5) for i in range(10)]
    a = paired_deltas(records, baseline="control", seed=3)["bad"]
    b = paired_deltas(records, baseline="control", seed=3)["bad"]
    assert (a["low"], a["high"]) == (b["low"], b["high"])


def test_condition_with_no_paired_tasks_is_reported_as_none():
    records = [
        record("control", "t1", 1.0),
        record("bad", "t2", None, valid=False),
    ]
    assert paired_deltas(records, baseline="control").get("bad") is None
