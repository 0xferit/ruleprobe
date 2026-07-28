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


from ruleprobe.backend import _cache_key


def test_samples_get_distinct_cache_keys():
    """Without this, n=5 replication silently returns one cached response five
    times and reports zero variance: n=1 wearing a disguise."""
    keys = {_cache_key("sys", "user", "sonnet", sample) for sample in range(5)}
    assert len(keys) == 5


def test_the_same_sample_is_still_cached():
    assert _cache_key("sys", "user", "sonnet", 2) == _cache_key("sys", "user", "sonnet", 2)


def test_sample_zero_is_stable_across_calls():
    """Sample 0 must stay reproducible so existing runs re-score from cache."""
    assert _cache_key("sys", "user", "sonnet", 0) == _cache_key("sys", "user", "sonnet", 0)
