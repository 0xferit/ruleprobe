"""Calls the model under test through the Claude Code CLI in headless mode.

`--setting-sources ""` is load-bearing, not incidental. Without it the CLI
loads the operator's own CLAUDE.md into every call; on the machine this was
built on, that file contains explicit rules such as "never mock the system
under test", which would have been silently present in all eight conditions
and destroyed the comparison. See SCORING.md, "Prompt isolation".

Responses are cached on disk by prompt hash so a re-run costs nothing and the
scoring can be re-derived offline.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from ruleprobe.cache import RESPONSE_CACHE_DIR, cache_key

CLI_EXECUTABLE = "claude"
HEADLESS_FLAG = "-p"
# Pattern matching a harness-spawned call, for monitoring and for reaping
# orphans. Defined beside the invocation it describes: a monitor that greps for
# a signature the code no longer produces reports zero and looks healthy.
PROCESS_PATTERN = f"{CLI_EXECUTABLE} {HEADLESS_FLAG}"

DEFAULT_MODEL = "sonnet"
CALL_TIMEOUT_SECONDS = 900
CACHE_DIR = RESPONSE_CACHE_DIR
# The CLI occasionally exits non-zero with empty stderr. Retrying costs one
# call; not retrying costs the unit.
CALL_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 5

_FENCED_BLOCK = re.compile(r"```(?:[a-zA-Z0-9_+-]*)\n(.*?)```", re.DOTALL)


@dataclass(frozen=True)
class Response:
    text: str
    cost_usd: float
    cached: bool


def call_model(
    system_prompt: str,
    user_prompt: str,
    model: str = DEFAULT_MODEL,
    cache_dir: Path = CACHE_DIR,
    sample: int = 0,
    timeout: int = CALL_TIMEOUT_SECONDS,
) -> Response:
    key = _cache_key(system_prompt, user_prompt, model, sample)
    cached = _read_cache(cache_dir, key)
    if cached is not None:
        return Response(text=cached["text"], cost_usd=0.0, cached=True)

    last_error: Exception | None = None
    for attempt in range(CALL_ATTEMPTS):
        try:
            return _invoke(system_prompt, user_prompt, model, cache_dir, key, timeout)
        except RuntimeError as exc:
            last_error = exc
            if attempt + 1 < CALL_ATTEMPTS:
                time.sleep(RETRY_BACKOFF_SECONDS * (attempt + 1))
    raise last_error  # type: ignore[misc]


def _invoke(
    system_prompt: str,
    user_prompt: str,
    model: str,
    cache_dir: Path,
    key: str,
    timeout: int,
) -> Response:
    # A scratch cwd keeps any CLAUDE.md near the repo out of the call.
    with tempfile.TemporaryDirectory(prefix="ruleprobe-call-") as workdir:
        completed = subprocess.run(
            [
                CLI_EXECUTABLE,
                HEADLESS_FLAG,
                user_prompt,
                "--system-prompt",
                system_prompt,
                "--exclude-dynamic-system-prompt-sections",
                "--setting-sources",
                "",
                "--model",
                model,
                "--output-format",
                "json",
            ],
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    if completed.returncode != 0:
        raise RuntimeError(f"claude exited {completed.returncode}: {completed.stderr[:500]}")

    payload = json.loads(completed.stdout)
    if payload.get("is_error"):
        raise RuntimeError(f"claude reported an error: {str(payload.get('result'))[:500]}")

    text = payload["result"]
    _write_cache(cache_dir, key, {"text": text, "system": system_prompt, "user": user_prompt})
    return Response(text=text, cost_usd=float(payload.get("total_cost_usd") or 0.0), cached=False)


def extract_code(response_text: str) -> str:
    """Pulls the test file out of a model response.

    Where several fenced blocks are present the longest is taken: the complete
    suite is the substantial one, and shorter blocks are usually illustrative.
    """
    blocks = _FENCED_BLOCK.findall(response_text)
    if blocks:
        return max(blocks, key=len).strip()
    return response_text.strip()


def _cache_key(system_prompt: str, user_prompt: str, model: str, sample: int = 0) -> str:
    """Distinct per sample.

    The CLI exposes no temperature control, so repeated samples are the only way
    to estimate run-to-run variance. Keying the cache on the prompt alone would
    hand back one response N times and report a spread of exactly zero.
    """
    return cache_key([system_prompt, user_prompt, model, sample])


def _read_cache(cache_dir: Path, key: str) -> dict | None:
    path = cache_dir / f"{key}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return None


def _write_cache(cache_dir: Path, key: str, payload: dict) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / f"{key}.json").write_text(json.dumps(payload))
