from ruleprobe.score import score_suite

CORRECT = "def add(a, b):\n    return a + b\n"
MUTANTS = [
    "def add(a, b):\n    return a - b\n",
    "def add(a, b):\n    return a * b\n",
]

STRONG = "from solution import add\n\ndef test_add():\n    assert add(2, 3) == 5\n"
WEAK = "from solution import add\n\ndef test_add():\n    add(2, 3)\n"
BROKEN = "from solution import add\n\ndef test_add():\n    assert add(2, 3) == 99\n"


def test_strong_suite_kills_every_mutant():
    score = score_suite(CORRECT, MUTANTS, STRONG, entry_point="add")
    assert score.valid is True
    assert score.kill_rate == 1.0


def test_assertion_free_suite_kills_nothing():
    score = score_suite(CORRECT, MUTANTS, WEAK, entry_point="add")
    assert score.valid is True
    assert score.kill_rate == 0.0


def test_suite_failing_on_correct_code_is_invalid_and_scores_no_kills():
    """Without this gate a broken suite reds out on every mutant and would be
    scored as the strongest suite in the experiment."""
    score = score_suite(CORRECT, MUTANTS, BROKEN, entry_point="add")
    assert score.valid is False
    assert score.kill_rate is None


def test_empty_suite_is_invalid():
    score = score_suite(CORRECT, MUTANTS, "# nothing\n", entry_point="add")
    assert score.valid is False


def test_detector_report_is_attached():
    score = score_suite(CORRECT, MUTANTS, WEAK, entry_point="add")
    assert score.report.assertion_free == 1
