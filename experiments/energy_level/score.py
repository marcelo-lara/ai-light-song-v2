"""Score against `experiments/truth_common.energy_tension` — provisional
until item 4's `segments.seed.json` is operator-reviewed (see that module's
docstring for the human/seed distinction)."""
from __future__ import annotations

import json

from experiments.truth_common import energy_tension as truth_et

from . import paths


def _predicted(song: str) -> list[dict]:
    path = paths.proposals_path(song)
    if not path.exists():
        return []
    payload = json.loads(path.read_text())
    return [
        {"start": b["start_s"], "end": b["end_s"], "energy": b.get("energy"), "tension": None}
        for b in payload.get("blocks", [])
    ]


def write_report() -> None:
    per_song = []
    for song in truth_et.SCORING_CORPUS:
        per_song.append(truth_et.score_energy_tension(song, _predicted(song)))
    truth_et.write_report(paths.out_file("score.txt"), per_song)
