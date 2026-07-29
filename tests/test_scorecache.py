"""Scoring is deterministic, so it should be paid for once.

The model-response cache made restarts free in API spend but not in time: every
relaunch re-ran forge over every already-scored unit, and the replay grew with
each restart.
"""

from ruleprobe.score import Score, read_score_cache, score_key, write_score_cache
from ruleprobe.detect import Report


def a_score(killed=(True, False)):
    return Score(
        valid=True, validity_outcome="passed", tests_collected=3,
        mutants_total=len(killed), mutants_killed=sum(killed),
        killed_mutants=list(killed), report=Report(3, 4, 0, 0, 0, 0),
    )


def test_same_inputs_give_the_same_key():
    assert score_key("sol", "t", ["m1"], "suite") == score_key("sol", "t", ["m1"], "suite")


def test_a_different_suite_gives_a_different_key():
    assert score_key("sol", "t", ["m1"], "suite") != score_key("sol", "t", ["m1"], "other")


def test_a_different_mutant_set_gives_a_different_key():
    """A stale score against a changed mutant set would silently misreport the
    kill rate, which is the headline number."""
    assert score_key("sol", "t", ["m1"], "s") != score_key("sol", "t", ["m1", "m2"], "s")


def test_a_different_task_gives_a_different_key():
    assert score_key("sol", "t1", ["m"], "s") != score_key("sol", "t2", ["m"], "s")


def test_language_is_part_of_the_key():
    assert score_key("sol", "t", ["m"], "s") != score_key("py", "t", ["m"], "s")


def test_round_trip_through_the_cache(tmp_path):
    key = score_key("sol", "t", ["m1"], "suite")
    assert read_score_cache(tmp_path, key) is None
    write_score_cache(tmp_path, key, a_score())
    restored = read_score_cache(tmp_path, key)
    assert restored.kill_rate == a_score().kill_rate
    assert restored.killed_mutants == [True, False]
    assert restored.validity_outcome == "passed"


def test_a_corrupt_cache_entry_is_ignored_rather_than_raising(tmp_path):
    key = score_key("sol", "t", ["m"], "s")
    (tmp_path / f"{key}.json").write_text("{not json")
    assert read_score_cache(tmp_path, key) is None


def test_every_score_field_survives_the_round_trip(tmp_path):
    """Guards the generic reconstruction: a field added to Score must flow
    through automatically rather than becoming a silent cache miss."""
    from dataclasses import fields

    from ruleprobe.score import read_score_cache, write_score_cache

    key = score_key("py", "t", ["m"], "s")
    original = a_score()
    write_score_cache(tmp_path, key, original)
    restored = read_score_cache(tmp_path, key)
    for field in fields(Score):
        assert getattr(restored, field.name) == getattr(original, field.name), field.name
