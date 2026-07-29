"""Retry behaviour, after 465 of 756 units were lost to rate limiting.

Twenty-eight concurrent calls exceeded what the API would accept. The retry was
three attempts with 5 and 10 second waits, which is the wrong order of magnitude
for a rate limit: every attempt landed inside the same throttling window and the
unit was recorded as a permanent failure.
"""

import pytest

from ruleprobe.backend import CALL_ATTEMPTS, backoff_seconds


def test_backoff_grows_exponentially():
    waits = [backoff_seconds(i) for i in range(4)]
    assert waits == sorted(waits)
    assert waits[-1] >= 8 * waits[0]


def test_first_wait_is_long_enough_to_clear_a_throttle_window():
    """Five and ten seconds landed inside the same window every time."""
    assert backoff_seconds(0) >= 30


def test_total_patience_exceeds_several_minutes():
    total = sum(backoff_seconds(i) for i in range(CALL_ATTEMPTS - 1))
    assert total >= 300, f"only {total}s of total patience"


def test_enough_attempts_to_ride_out_a_throttle():
    assert CALL_ATTEMPTS >= 5


@pytest.mark.parametrize("attempt", [0, 1, 2, 3, 4])
def test_backoff_is_always_positive(attempt):
    assert backoff_seconds(attempt) > 0
