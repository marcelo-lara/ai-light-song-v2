"""Phase-4 stage — `version-check` (v3.11 item 21).

Is the web-researched pre-analysis hint about the same recording as the audio?
Compares `reference/pre-analysis/structure.json` against the PUBLISHED
`info.json` and writes the `version_check` block of
`reference/pre-analysis/verdict.json`:

- `duration_delta_s` = hint `track.version_duration_s` - info `duration`
  (signed, 3 decimals); mismatch when `abs() > 5 s`.
- `bpm_delta_pct` = relative gap between hint `genre.bpm` and info `bpm` after
  folding half / double time (the hint BPM, x0.5, x1 or x2, whichever is
  nearest), as a percent of info `bpm`, 3 decimals; mismatch when `> 3 %`.
- `version_mismatch` = either mismatch. A `null` on either side of a pair is
  not a mismatch and leaves that delta `null`. Both limits are strict (exactly
  5 s or 3 % is not a mismatch).

Measured on the 27-song corpus (schema 1.1 hints, 2026-10): 7 songs flag, all
on duration (Chimera - Hana 40.4 s, Rapture 23.5, Sash 16.8, Queen of Kings
13.6, Titanium 12.6, Only this moment 7.2, Underworld - Born Slippy 6.05); none
flags on BPM alone. 9 songs have a null duration and are never flagged on it.

Consumers (`docs/reference/downstream-contract.md`) ignore the hint's
`track.version` and `shape` when `version_mismatch` is true. Nothing in the
analysis reads the hint or this block.

No hint file -> nothing written, no error (the hint is optional). A hint file
that exists but is unreadable or lacks the `track`/`genre` objects raises
`AnalysisError`: no silent fallback. `info.json` must already be published.
Other blocks already in `verdict.json` (item 22) are preserved; only
`version_check` is replaced. Deterministic: pure arithmetic on two files, no
timestamps.

`verdict.json` lives under `reference/` (beside the hint it judges), is never
published at top level and never reaches the MCP server's read surface.
"""
from __future__ import annotations

from analyzer.exceptions import AnalysisError
from analyzer.io import read_json, write_json
from analyzer.models import SCHEMA_VERSION
from analyzer.paths import SongPaths

DURATION_TOLERANCE_S = 5.0
BPM_TOLERANCE_PCT = 3.0


def _number(value: object, where: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AnalysisError(f"{where} must be a number or null, got {value!r}.")
    return float(value)


def compute_version_check(hint: dict, info: dict, song_name: str) -> dict:
    track = hint.get("track")
    genre = hint.get("genre")
    if not isinstance(track, dict) or not isinstance(genre, dict):
        raise AnalysisError(f"{song_name}: structure.json must carry 'track' and 'genre' objects.")
    hint_duration = _number(track.get("version_duration_s"), "track.version_duration_s")
    hint_bpm = _number(genre.get("bpm"), "genre.bpm")
    duration = _number(info.get("duration"), "info.json duration")
    bpm = _number(info.get("bpm"), "info.json bpm")
    if duration is None or bpm is None or bpm <= 0:
        raise AnalysisError(f"{song_name}: info.json must carry a numeric duration and a positive bpm.")

    duration_delta = None if hint_duration is None else round(hint_duration - duration, 3)
    bpm_delta = None
    if hint_bpm is not None:
        bpm_delta = round(min(abs(hint_bpm * f - bpm) for f in (0.5, 1.0, 2.0)) / bpm * 100.0, 3)

    mismatch = (duration_delta is not None and abs(duration_delta) > DURATION_TOLERANCE_S) or (
        bpm_delta is not None and bpm_delta > BPM_TOLERANCE_PCT
    )
    return {
        "version_mismatch": bool(mismatch),
        "duration_delta_s": duration_delta,
        "bpm_delta_pct": bpm_delta,
    }


def publish_version_check(paths: SongPaths) -> str | None:
    """Writes `reference/pre-analysis/verdict.json`'s `version_check` block.
    Returns the written path, or `None` when the song has no hint."""
    hint_path = paths.reference("pre-analysis", "structure.json")
    if not hint_path.exists():
        return None
    hint = read_json(hint_path)
    if not isinstance(hint, dict):
        raise AnalysisError(f"{hint_path.name} must contain a JSON object payload.")
    if not paths.info_output_path.exists():
        raise AnalysisError("'version-check' requires the published info.json; run the full pipeline first.")
    info = read_json(paths.info_output_path)
    if not isinstance(info, dict):
        raise AnalysisError("info.json must contain a JSON object payload.")

    verdict_path = paths.reference("pre-analysis", "verdict.json")
    payload = read_json(verdict_path) if verdict_path.exists() else {}
    if not isinstance(payload, dict):
        raise AnalysisError(f"{verdict_path.name} must contain a JSON object payload.")
    payload.update(
        {
            "schema_version": SCHEMA_VERSION,
            "song_name": paths.song_name,
            "generated_from": {
                "hint": "reference/pre-analysis/structure.json",
                "hint_schema_version": hint.get("schema_version"),
                "info": "info.json",
            },
            "version_check": compute_version_check(hint, info, paths.song_name),
        }
    )
    write_json(verdict_path, payload)
    return str(verdict_path)
