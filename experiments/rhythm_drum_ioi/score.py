"""Score against `experiments/truth_common.rhythm` — provisional until item
4's `segments.seed.json` / operator review lands (see that module's
docstring for the human/seed distinction; a score against a seed is always
`provisional: true`)."""
from __future__ import annotations

import json

from experiments.truth_common import rhythm as truth_rhythm

from . import paths


def _predicted(song: str) -> list[dict]:
    path = paths.proposals_path(song)
    if not path.exists():
        return []
    payload = json.loads(path.read_text())
    return [
        {"start": b["start_s"], "end": b["end_s"], "subdivisions": b.get("subdivisions", {})}
        for b in payload.get("blocks", [])
    ]


def write_report() -> None:
    per_song = []
    for song in truth_rhythm.SCORING_CORPUS:
        per_song.append(truth_rhythm.score_rhythm(song, _predicted(song)))
    truth_rhythm.write_report(paths.out_file("score.txt"), per_song)
