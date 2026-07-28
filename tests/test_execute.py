from ruleprobe.execute import Outcome, run_suite

CORRECT = "def add(a, b):\n    return a + b\n"
BROKEN = "def add(a, b):\n    return a - b\n"

GOOD_SUITE = "from solution import add\n\ndef test_add():\n    assert add(2, 3) == 5\n"


def test_passing_suite_on_correct_code_passes():
    assert run_suite(CORRECT, GOOD_SUITE).outcome is Outcome.PASSED


def test_suite_fails_on_broken_code():
    assert run_suite(BROKEN, GOOD_SUITE).outcome is Outcome.FAILED


def test_empty_suite_is_not_a_pass():
    """pytest exits 5 when it collects nothing. Counting that as a pass would
    hand a perfect validity score to a model that wrote no tests at all."""
    result = run_suite(CORRECT, "# no tests here\n")
    assert result.outcome is Outcome.NO_TESTS


def test_suite_with_syntax_error_is_reported_not_raised():
    result = run_suite(CORRECT, "def test_x(:\n")
    assert result.outcome is Outcome.ERROR


def test_import_error_in_suite_is_reported():
    result = run_suite(CORRECT, "from solution import nonexistent\n\ndef test_x():\n    assert True\n")
    assert result.outcome is Outcome.ERROR


def test_infinite_loop_times_out_instead_of_hanging():
    spinner = "from solution import add\n\ndef test_spin():\n    while True:\n        pass\n"
    result = run_suite(CORRECT, spinner, timeout_seconds=5)
    assert result.outcome is Outcome.TIMEOUT


def test_collected_test_count_is_reported():
    two = GOOD_SUITE + "\ndef test_add_zero():\n    assert add(0, 0) == 0\n"
    assert run_suite(CORRECT, two).tests_collected == 2
