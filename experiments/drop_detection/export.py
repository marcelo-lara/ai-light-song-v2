"""Bootstrap labelling: turn stage-1 proposals into draft hints for review.

Only four of the twenty-one corpus tracks are labelled, giving seven positive
examples. That is far too few to train or even honestly validate a re-ranker, so
the proposer is used to make labelling cheap: it emits its top candidates per
song as draft `drop impact` hints, a human keeps or deletes each one in the hint
editor, and the kept set becomes ground truth.

Files are written to `data/analysis/<song>/reference/proposals/drop_impacts.json`
-- inside the tree the UI dev server mounts at `/data`, so the "Drop Proposals"
timeline lane can read them and you can audition each candidate against the
Human Hints lane while the song plays. They are deliberately NOT written into
`reference/human/human_hints.json`: that file is the ground truth and is only
ever edited by a person.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import candidates, features, groundtruth
from .paths import ANALYSIS_ROOT

PROPOSALS_FILE = "drop_impacts.json"


def proposals_path(song: str) -> Path:
    return ANALYSIS_ROOT / song / "reference" / "proposals" / PROPOSALS_FILE


def _rank_key(row: dict) -> float:
    """Order candidates for review. More channels agreeing on a beat is the
    strongest available prior: every gold impact fires at least one channel, and
    the two-and-three-channel agreements are much rarer than single hits."""
    ch = row["channels"]
    strength = max(row["features"][f"ch_{name}"] for name in ch)
    return len(ch) * 1000.0 + strength


def export_song(song: str, *, top: int = 8, per_channel: int = 3) -> Path:
    feat = features.load(song)
    props = candidates.propose(feat, per_channel=per_channel)
    props.sort(key=_rank_key, reverse=True)
    props = props[:top]
    props.sort(key=lambda row: row["time"])

    known = groundtruth.impacts(song)
    hints = []
    for index, row in enumerate(props, 1):
        t = row["time"]
        matched = next((g for g in known if abs(g - t) <= 0.5), None)
        hints.append({
            "id": f"proposal-{index:03d}",
            "title": "drop impact",
            # A human `drop impact` hint runs about half a second; the proposal is
            # given the same span so the two lanes are visually comparable.
            "start_time": round(t, 3),
            "end_time": round(t + 0.542, 3),
            "channels": row["channels"],
            "matches_human_label": matched,
            "evidence": {
                "bass_reentry_db": round(row["features"]["bass_reentry"], 1),
                "vocals_delta_db": round(row["features"]["d_vocals_s"], 1),
                "drums_delta_db": round(row["features"]["d_drums_s"], 1),
                "mix_delta_db": round(row["features"]["d_mix_s"], 1),
            },
        })

    path = proposals_path(song)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "schema_version": "1.0",
        "song_name": song,
        "generated_from": {"engine": "experiments.drop_detection.stage1"},
        "note": "Draft `drop impact` candidates from the stage-1 proposer. Audition "
                "each against the Human Hints lane, then copy the survivors into "
                "reference/human/human_hints.json by hand.",
        "existing_labels": known,
        "proposals": hints,
    }, indent=2) + "\n")
    return path


def summary_line(song: str, path: Path) -> str:
    payload = json.loads(path.read_text())
    known = payload["existing_labels"]
    hints = payload["proposals"]
    covered = sum(1 for h in hints if h["matches_human_label"] is not None)
    tag = f"{covered}/{len(known)} known" if known else "unlabelled"
    return f"  {song:<38} {len(hints):2d} drafts  ({tag})"
