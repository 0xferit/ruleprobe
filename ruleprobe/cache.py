"""One cache root and one key recipe, shared by everything that caches.

Model responses and scores are separate caches with the same identity scheme.
Deriving the root or re-implementing the hash per consumer means a change to
either convention silently splits them onto different roots or key formats.

The recipe is fixed by compatibility, not taste: changing the algorithm or the
truncation length orphans every entry already on disk, and those entries
represent real API spend.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

CACHE_ROOT = Path(__file__).resolve().parent.parent / ".cache"
RESPONSE_CACHE_DIR = CACHE_ROOT
SCORE_CACHE_DIR = CACHE_ROOT / "scores"
KEY_LENGTH = 32


def cache_key(parts: list) -> str:
    """Stable identity for a cacheable job, from its JSON-serialisable parts."""
    payload = json.dumps(parts, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:KEY_LENGTH]
