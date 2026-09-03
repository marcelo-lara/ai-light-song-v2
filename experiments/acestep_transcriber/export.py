"""Write the `acestep` source into reference/proposals/vocal_transcription.json.

Shared file (constitution §3.2). Rewrites only the `ACE-Step …` entry and the
`whisper-…` baseline row; any `VocalParse` entry from the sibling experiment is
left untouched.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import align, model, whisper_baseline
from .paths import SOURCE_MODEL, proposal_path

SCHEMA_VERSION = "1.0"

NOTE = (
    "Vocal transcription proposals from experiments/vocalparse and "
    "experiments/acestep_transcriber. Lyric lines with timing, for review — "
    "nothing in src/ reads this file. Timing on the model rows is borrowed from "
    "the whisper baseline row (see each row's `alignment` field); a row marked "
    "`alignment: unavailable` has only approximate line timing."
)


def _merge(song: str, new_sources: list[dict]) -> dict:
    path = proposal_path(song)
    if path.exists():
        payload = json.loads(path.read_text())
    else:
        payload = {"schema_version": SCHEMA_VERSION, "song_name": song,
                   "note": NOTE, "sources": []}
    keep = {s["model"] for s in new_sources}
    payload["note"] = NOTE
    payload["sources"] = [s for s in payload.get("sources", []) if s["model"] not in keep]
    payload["sources"].extend(new_sources)
    payload["sources"].sort(key=lambda s: (s.get("kind") != "baseline", s["model"]))
    return payload


def export_song(song: str) -> Path:
    whisper = whisper_baseline.load(song)
    parsed = model.load(song)
    aligned = align.align(parsed, whisper["lines"])

    ace_source = {
        "model": SOURCE_MODEL,
        "kind": "singing-transcription",
        "alignment": aligned["alignment"],
        "alignment_reason": aligned["reason"],
        "languages": parsed.get("languages", []),
        "structure": aligned["sections"],
        "lines": [{k: v for k, v in l.items() if k != "section_index"}
                  for l in aligned["lines"]],
    }

    payload = _merge(song, [whisper, ace_source])
    path = proposal_path(song)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    return path


def summary_line(song: str, path: Path) -> str:
    payload = json.loads(path.read_text())
    src = next((s for s in payload["sources"] if s["model"] == SOURCE_MODEL), None)
    if src is None:
        return f"  {song:<40} (no acestep source)"
    tags = " ".join(s["tag"] for s in src["structure"])
    return (f"  {song:<40} {len(src['lines']):3d} lines  {len(src['structure'])} sections  "
            f"align={src['alignment']:<11} [{tags}]")
