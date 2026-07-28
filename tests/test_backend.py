from ruleprobe.backend import extract_code


def test_extracts_a_python_fenced_block():
    assert extract_code("here you go\n```python\nx = 1\n```\n") == "x = 1"


def test_extracts_a_fenced_block_with_no_language_tag():
    assert extract_code("```\nx = 1\n```") == "x = 1"


def test_picks_the_longest_block_when_several_are_present():
    """Models sometimes precede the suite with a one-line illustrative snippet.
    The complete test file is the substantial one."""
    response = "```python\nimport pytest\n```\nand the file:\n```python\ndef test_a():\n    assert 1 == 1\n```"
    assert extract_code(response) == "def test_a():\n    assert 1 == 1"


def test_unfenced_response_is_treated_as_code():
    assert extract_code("def test_a():\n    pass") == "def test_a():\n    pass"


def test_empty_response_yields_empty_string():
    assert extract_code("") == ""
