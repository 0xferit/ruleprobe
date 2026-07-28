from ruleprobe.detect import analyze

ENTRY = "add"


def test_test_without_any_assertion_is_flagged():
    src = "from solution import add\n\ndef test_runs():\n    add(1, 2)\n"
    assert analyze(src, ENTRY).assertion_free == 1


def test_pytest_raises_counts_as_an_assertion():
    """A `raises` block asserts a contract. Counting it as assertion-free would
    penalise the one correct way to test an error path."""
    src = (
        "import pytest\nfrom solution import add\n\n"
        "def test_rejects_none():\n    with pytest.raises(TypeError):\n        add(None, 1)\n"
    )
    assert analyze(src, ENTRY).assertion_free == 0


def test_direct_self_comparison_is_tautological():
    src = "from solution import add\n\ndef test_x():\n    assert add(1, 2) == add(1, 2)\n"
    assert analyze(src, ENTRY).tautological == 1


def test_expected_value_computed_by_the_sut_is_tautological():
    src = (
        "from solution import add\n\n"
        "def test_x():\n    expected = add(1, 2)\n    assert add(1, 2) == expected\n"
    )
    assert analyze(src, ENTRY).tautological == 1


def test_literal_expectation_is_not_tautological():
    src = "from solution import add\n\ndef test_x():\n    assert add(1, 2) == 3\n"
    assert analyze(src, ENTRY).tautological == 0


def test_patching_the_system_under_test_is_flagged():
    src = (
        "from unittest.mock import patch\nfrom solution import add\n\n"
        "@patch('solution.add')\ndef test_x(m):\n    m.return_value = 5\n    assert add(1, 2) == 5\n"
    )
    assert analyze(src, ENTRY).mocks_sut == 1


def test_patching_a_genuine_external_is_not_flagged():
    """Mocking the network is correct practice; only mocking the SUT is the smell."""
    src = (
        "from unittest.mock import patch\nfrom solution import add\n\n"
        "@patch('requests.get')\ndef test_x(m):\n    assert add(1, 2) == 3\n"
    )
    assert analyze(src, ENTRY).mocks_sut == 0


def test_constant_true_assertion_is_trivial():
    src = "def test_x():\n    assert True\n"
    assert analyze(src, ENTRY).trivial_assert == 1


def test_self_equality_assertion_is_trivial():
    src = "from solution import add\n\ndef test_x():\n    x = 1\n    assert x == x\n"
    assert analyze(src, ENTRY).trivial_assert == 1


def test_counts_tests_and_assertions():
    src = (
        "from solution import add\n\n"
        "def test_a():\n    assert add(1, 2) == 3\n    assert add(0, 0) == 0\n\n"
        "def test_b():\n    assert add(-1, 1) == 0\n"
    )
    report = analyze(src, ENTRY)
    assert report.tests == 2
    assert report.assertions == 3


def test_unparseable_suite_reports_zero_tests_rather_than_raising():
    assert analyze("def test_x(:\n", ENTRY).tests == 0
