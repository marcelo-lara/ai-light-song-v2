"""Write the reviewable character layer — one file per song.

`data/analysis/<song>/reference/proposals/character.json`, rendered by the
debugger as the **Character** lane beneath **allin1 Sections**. A proposal,
never a deliverable (constitution §3.2).

The lane answers a question the arrangement cannot: *what is this passage like?*
A verse and a chorus can both be a voice over pads with the drums out, and they
want the same look; two choruses can differ completely. The operator already
works this way — `Armin - Revolution` carries a hand-marked "Breath" block with
its own fixture behaviour, and it is not a section boundary.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from . import character, model, probes
from .paths import ANALYSIS_ROOT, proposals_path

SCHEMA_VERSION = "1.0"

NOTE = (
    "Character blocks from experiments/clap: what a passage is like, not where it sits "
    "in the arrangement. Proposals for review, not deliverables — nothing in src/ reads "
    "this file. `stems` blocks come from per-stem RMS the pipeline already produces, "
    "`stems+clap` blocks additionally need CLAP's calm/intense axis, and `allin1` blocks "
    "are labels with sustained frame-level posterior mass that allin1's own published "
    "segmentation never used."
)


def character_path(song: str) -> Path:
    return proposals_path(song).with_name("character.json")


def build(song: str, text_emb: np.ndarray) -> dict:
    times, stems = character.stem_grid(song)
    clap_cache = model.load(song)
    raw_axes = probes.axes(model.unit(clap_cache["emb"]), text_emb)
    clap_axes = {k: character.resample(clap_cache["times"], v, times)
                 for k, v in raw_axes.items()}
    rows = character.blocks(song, times, stems, clap_axes)

    counts: dict[str, int] = {}
    for row in rows:
        counts[row["kind"]] = counts.get(row["kind"], 0) + 1

    return {
        "schema_version": SCHEMA_VERSION,
        "song_name": song,
        "generated_from": {
            "engine": "experiments.clap.character",
            "clap_model": str(clap_cache["model_id"]),
            "stems": "artifacts/essentia/rms_loudness.json",
            "shadow_labels": "reference/proposals/allin1.json (frame_labels)",
            "grid_hz": character.GRID_HZ,
        },
        "note": NOTE,
        "thresholds": {
            "stem_present_fraction_of_p90": character.PRESENT_FRACTION,
            "stem_out_fraction_of_p90": character.OUT_FRACTION,
            "smooth_s": character.SMOOTH_S,
            "close_gap_s": character.CLOSE_GAP_S,
            "calm_z": character.CALM_Z,
            "intense_z": character.INTENSE_Z,
            "min_block_s": character.MIN_BLOCK_S,
        },
        "counts": counts,
        "blocks": rows,
    }


def export_song(song: str, text_emb: np.ndarray) -> Path:
    payload = build(song, text_emb)
    path = character_path(song)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return path


def summary_line(song: str, path: Path) -> str:
    payload = json.loads(path.read_text())
    counts = payload["counts"]
    order = ("breath", "void", "vocal lead", "full power")
    shown = " ".join(f"{k.split()[-1][:5]}:{counts.get(k, 0)}" for k in order)
    shadow = sum(v for k, v in counts.items() if k.startswith("shadow"))
    return (f"  {song:<40} {len(payload['blocks']):3d} blocks   {shown}   "
            f"shadow:{shadow}")
