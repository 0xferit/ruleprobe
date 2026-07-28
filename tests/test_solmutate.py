from ruleprobe.solmutate import generate_solidity_mutants, mask_strings_and_comments

SRC = '''// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

/// @notice Compares a > b and returns "greater" when true.
library Cmp {
    uint256 internal constant LIMIT = 100;

    function pick(uint256 a, uint256 b) internal pure returns (uint256) {
        // returns the larger, a >= b wins ties
        require(a <= LIMIT && b <= LIMIT, "a > LIMIT");
        if (a > b) {
            return a + 1;
        }
        return b * 2;
    }
}
'''


def test_comments_are_masked():
    masked = mask_strings_and_comments(SRC)
    assert "greater" not in masked
    assert "wins ties" not in masked


def test_string_literals_are_masked():
    masked = mask_strings_and_comments(SRC)
    assert "a > LIMIT" not in masked


def test_masking_preserves_length_so_offsets_stay_valid():
    assert len(mask_strings_and_comments(SRC)) == len(SRC)


def test_code_outside_strings_and_comments_survives_masking():
    masked = mask_strings_and_comments(SRC)
    assert "require(" in masked
    assert "LIMIT" in masked


def test_mutants_are_generated():
    assert generate_solidity_mutants(SRC, 20, 1)


def test_every_mutant_differs_from_the_original():
    for m in generate_solidity_mutants(SRC, 20, 1):
        assert m.source != SRC


def test_no_mutant_alters_a_comment_or_string():
    """A mutation inside the docstring changes the spec the model is scored
    against; one inside a revert string changes nothing but looks like a kill."""
    for m in generate_solidity_mutants(SRC, 30, 1):
        assert 'Compares a > b and returns "greater" when true.' in m.source
        assert '"a > LIMIT"' in m.source


def test_each_mutant_changes_exactly_one_contiguous_site():
    """Compared by common prefix and suffix rather than position-by-position:
    `<` becoming `<=` lengthens the source, so a zip comparison misaligns every
    character after the edit and reports the whole file as changed."""
    for m in generate_solidity_mutants(SRC, 30, 1):
        prefix = 0
        while prefix < min(len(SRC), len(m.source)) and SRC[prefix] == m.source[prefix]:
            prefix += 1
        suffix = 0
        while (
            suffix < min(len(SRC), len(m.source)) - prefix
            and SRC[-1 - suffix] == m.source[-1 - suffix]
        ):
            suffix += 1
        changed_from = SRC[prefix : len(SRC) - suffix]
        changed_to = m.source[prefix : len(m.source) - suffix]
        assert len(changed_from) <= 3 and len(changed_to) <= 3, (
            f"{m.operator}: {changed_from!r} -> {changed_to!r} is not a single site"
        )


def test_compound_assignment_is_not_split():
    """`a += 1` must not become `a =+ 1`, which still compiles and means
    something else entirely."""
    for m in generate_solidity_mutants("contract C { function f(uint a) public pure returns (uint) { a += 1; return a; } }", 20, 1):
        assert "=+" not in m.source and "=-" not in m.source


def test_mapping_arrow_is_never_mutated():
    src = "contract C { mapping(address => uint256) public balances; }"
    assert all("=>" in m.source for m in generate_solidity_mutants(src, 20, 1))


def test_generation_is_deterministic():
    a = generate_solidity_mutants(SRC, 8, 3)
    b = generate_solidity_mutants(SRC, 8, 3)
    assert [m.source for m in a] == [m.source for m in b]


ASSEMBLY = '''contract C {
    function f(uint256 a) public pure returns (uint256 r) {
        if (a > 3) { r = a + 7; }
        assembly {
            if lt(a, 5) { revert(0, 0) }
            r := add(a, 9)
        }
    }
}
'''


def test_assembly_blocks_are_masked():
    """Yul literals are offsets and selectors, not domain values. Shifting
    `revert(0, 0)` to `revert(1, 0)` is a diff that changes no behaviour a test
    could observe, so it inflates the mutant pool with unkillable noise."""
    for m in generate_solidity_mutants(ASSEMBLY, 40, 1):
        assert "revert(0, 0)" in m.source
        assert "add(a, 9)" in m.source


def test_code_outside_assembly_is_still_mutated():
    sources = {m.source for m in generate_solidity_mutants(ASSEMBLY, 40, 1)}
    assert any("a >= 3" in s or "a + 8" in s or "a - 7" in s for s in sources)


def test_sampling_is_stratified_across_operators():
    """Boundary literals vastly outnumber comparisons in real contracts.
    Uniform sampling returns twelve boundary mutants and never exercises a
    comparison flip, which is the operator most tests are supposed to catch."""
    rich = "contract C { function f(uint a, uint b) public pure returns (uint) {" + \
           " if (a > b && a < 100) { return a + 1; } return b * 2 + 3 + 4 + 5 + 6 + 7 + 8; } }"
    operators = {m.operator for m in generate_solidity_mutants(rich, 6, 1)}
    assert len(operators) >= 3, f"only {operators}"
