"""v3.9 item 1 — no lyric token text ever leaves the `mcp/` server, checked
against the real Queen of Kings analysis (`reference/human/lyrics.json` has
real words; `vocal_cadence.json` and everything the server serializes from it
must carry only timing).

Skipped when the real corpus isn't mounted (fixture-only test runs, e.g. a
bare `pytest mcp/tests` outside the `app`/`mcp` containers) or the song
hasn't been analysed with `publish-vocal-cadence` yet — this is a corpus
integration check, not a fixture unit test.
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

MCP_DIR = Path(__file__).resolve().parents[1]
ANALYSIS_ROOT = MCP_DIR.parents[0] / "data" / "analysis"
SONG = "Queen of Kings - Alessandra"

sys.path.insert(0, str(MCP_DIR))


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, MCP_DIR / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


serializers = _load("mcp_serializers_qok", "serializers.py")

pytestmark = pytest.mark.skipif(
    not (ANALYSIS_ROOT / SONG / "vocal_cadence.json").is_file(),
    reason=f"{SONG!r} has no published vocal_cadence.json in this environment",
)


def _distinctive_words() -> set[str]:
    """Real lyric tokens, length >= 4 only — short tokens risk a false-positive
    substring hit against ordinary JSON field names/values (e.g. "on")."""
    human = ANALYSIS_ROOT / SONG / "reference" / "human" / "lyrics.json"
    tokens = json.loads(human.read_text())
    return {
        t["text"] for t in tokens
        if t["text"] not in ("<SOL>", "<EOL>") and not t["text"].startswith("(") and len(t["text"]) >= 4
    }


def _leaf_string_values(obj, *, skip_keys: frozenset[str] = frozenset({"song_name"})) -> list[str]:
    """Recursively collect string LEAF VALUES only — never dict keys, and
    never a value under `skip_keys` (e.g. `song_name`, which legitimately
    contains "Queen of Kings"). This is what a lyric word could plausibly
    "leak into"; JSON key names (`beat`, `calls`, `section_id`, ...) are
    schema, not content, and would otherwise false-positive against common
    English lyric words."""
    out: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in skip_keys:
                continue
            out.extend(_leaf_string_values(v, skip_keys=skip_keys))
    elif isinstance(obj, list):
        for v in obj:
            out.extend(_leaf_string_values(v, skip_keys=skip_keys))
    elif isinstance(obj, str):
        out.append(obj)
    return out


def test_no_lyric_text_in_overview_or_detail():
    """Scoped to the parts of the response actually derived from
    `lyrics.json` — `overview["vocal_cadence"]`/its per-section fields on
    `sections.rows`, and `detail["structural"]["vocal_cadence"]`. A
    whole-response scan false-positives on ordinary English words that
    coincidentally match a short lyric token inside unrelated fields (e.g.
    `hints.json`'s own human-written prose, which legitimately shares common
    words with the song's lyrics)."""
    words = _distinctive_words()
    assert words, "fixture assumption stale: Queen of Kings lyrics.json carries no tokens"

    overview = serializers.build_song_overview(SONG, root=ANALYSIS_ROOT)
    detail = serializers.build_detail(SONG, root=ANALYSIS_ROOT, start_ms=0, end_ms=180000)

    scoped = [overview.get("vocal_cadence")]
    scoped += [
        {k: v for k, v in row.items() if k in ("lead_in_bars", "rest_count", "call_count", "cadence_repeat_best")}
        for row in overview.get("sections", {}).get("rows", [])
    ]
    scoped.append(detail["structural"]["vocal_cadence"])

    values = _leaf_string_values(scoped)
    leaked = set()
    for value in values:
        tokens = set(re.findall(r"[A-Za-z']+", value))
        leaked |= (words & tokens)
    assert not leaked, f"lyric text leaked into vocal_cadence-derived mcp response fields: {leaked}"
