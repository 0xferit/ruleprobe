"""The cache key format is fixed by compatibility, not taste.

Changing the algorithm or the truncation length orphans every entry already on
disk, and those entries represent real API spend: at the time of writing, some
700 cached responses at roughly $0.45 each.
"""

from ruleprobe.backend import _cache_key
from ruleprobe.cache import RESPONSE_CACHE_DIR, SCORE_CACHE_DIR, cache_key
from ruleprobe.score import score_key


def test_response_key_format_is_frozen():
    """Golden values captured from the implementation that wrote the live cache."""
    assert _cache_key("sys", "user", "sonnet", 0) == "b7801cfb9828e468aa4e03315347ce4e"
    assert _cache_key("a", "b", "c", 3) == "107bed4f569505fe5a877c227cff75db"


def test_key_length_is_frozen():
    assert len(cache_key(["anything"])) == 32


def test_response_and_score_caches_share_a_root():
    """Separate directories, one root: deriving the root per consumer lets the
    two caches drift onto different paths."""
    assert SCORE_CACHE_DIR.parent == RESPONSE_CACHE_DIR


def test_both_key_builders_use_the_same_recipe():
    assert score_key("py", "t", ["m"], "s") == cache_key(["py", "t", ["m"], "s"])


def test_key_is_order_sensitive_across_parts():
    assert cache_key(["a", "b"]) != cache_key(["b", "a"])


def test_process_patterns_match_the_commands_actually_spawned():
    """A monitor grepping for a signature the code no longer produces reports
    zero processes and looks healthy, which is how a dead campaign stayed
    invisible for hours."""
    from ruleprobe.backend import CLI_EXECUTABLE, HEADLESS_FLAG, PROCESS_PATTERN
    from ruleprobe.solidity import (
        FORGE_EXECUTABLE,
        FORGE_TEST_SUBCOMMAND,
        PROCESS_PATTERN as FORGE_PATTERN,
    )

    assert PROCESS_PATTERN == f"{CLI_EXECUTABLE} {HEADLESS_FLAG}"
    assert FORGE_PATTERN == f"{FORGE_EXECUTABLE} {FORGE_TEST_SUBCOMMAND}"
