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
from dataclasses import dataclass
from pathlib import Path

DEFAULT_MODEL = "sonnet"
CALL_TIMEOUT_SECONDS = 300
CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache"

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
) -> Response:
    key = _cache_key(system_prompt, user_prompt, model)
    cached = _read_cache(cache_dir, key)
    if cached is not None:
        return Response(text=cached["text"], cost_usd=0.0, cached=True)

    # A scratch cwd keeps any CLAUDE.md near the repo out of the call.
    with tempfile.TemporaryDirectory(prefix="ruleprobe-call-") as workdir:
        completed = subprocess.run(
            [
                "claude",
                "-p",
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
            timeout=CALL_TIMEOUT_SECONDS,
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


def _cache_key(system_prompt: str, user_prompt: str, model: str) -> str:
    payload = json.dumps([system_prompt, user_prompt, model], sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:32]


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
