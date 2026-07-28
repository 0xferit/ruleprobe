from ruleprobe.normalise import normalise_import

ENTRY = "how_many_times"


def test_rewrites_a_wrong_module_name_that_imports_the_entry_point():
    src = "from module import how_many_times\n"
    fixed, changed = normalise_import(src, ENTRY)
    assert fixed == "from solution import how_many_times\n"
    assert changed is True


def test_leaves_a_correct_import_untouched():
    src = "from solution import how_many_times\n"
    fixed, changed = normalise_import(src, ENTRY)
    assert fixed == src
    assert changed is False


def test_does_not_touch_third_party_imports():
    src = "import pytest\nfrom module import how_many_times\n"
    fixed, _ = normalise_import(src, ENTRY)
    assert "import pytest\n" in fixed


def test_does_not_rewrite_a_module_that_lacks_the_entry_point():
    """Keying on the entry point is what makes this safe: a genuine helper
    import must survive untouched."""
    src = "from math import sqrt\nfrom solution import how_many_times\n"
    fixed, changed = normalise_import(src, ENTRY)
    assert "from math import sqrt" in fixed
    assert changed is False


def test_handles_multiple_names_in_one_import():
    src = "from mymod import how_many_times, helper\n"
    fixed, changed = normalise_import(src, ENTRY)
    assert fixed == "from solution import how_many_times, helper\n"
    assert changed is True


def test_unparseable_source_is_returned_unchanged():
    src = "from module import (\n"
    fixed, changed = normalise_import(src, ENTRY)
    assert fixed == src
    assert changed is False
