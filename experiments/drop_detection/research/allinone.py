"""All-In-One (`allin1`, Kim & Nam 2023) — the one model in this survey that
outputs *named* functional structure.

It predicts beats, downbeats, tempo and a segmentation labelled from the
Harmonix vocabulary (`start intro verse chorus bridge inst solo outro end`) in
a single multi-task model, trained on Harmonix Set, which is pop/EDM-heavy —
the same repertoire this project targets.

This is the piece the current pipeline has no equivalent of. Its section labels
are mood adjectives invented per-section ("Momentum Lift", "Vocal Spotlight"),
so a returning chorus gets a different name each time and nothing in the
artifact says *which part of the song* a section is.

Runs in the `ai-light-song-v2-allin1:dev` sandbox only (natten 0.15 / torch 2.1).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .common import CACHE_ROOT, audio_path, stem_path

CACHE_DIR = CACHE_ROOT / "allin1"


def cache_path(song: str) -> Path:
    return CACHE_DIR / f"{song.replace('/', '_')}.json"


DEMIX_DIR = Path("/tmp/allin1_demix")


def _seed_demix(song: str) -> None:
    """Point allin1 at the stems the pipeline already produced.

    Left to itself allin1 shells out to `demucs.separate` on the GPU while
    holding its own model resident, which OOMs a 4 GB card partway through a
    corpus run (it failed on 7 of 21 songs that way). The repo's stems are
    htdemucs output at 44.1 kHz stereo already — the same thing allin1 would
    compute — so they are linked into the layout its cache check expects,
    `harmonic` standing in for htdemucs's `other`.
    """
    out = DEMIX_DIR / "htdemucs" / audio_path(song).stem
    out.mkdir(parents=True, exist_ok=True)
    for target, source in (("bass", "bass"), ("drums", "drums"),
                           ("other", "harmonic"), ("vocals", "vocals")):
        link = out / f"{target}.wav"
        src = stem_path(song, source)
        if not link.exists() and src.exists():
            link.symlink_to(src)


def compute(song: str, *, device: str = "cuda") -> dict:
    import allin1

    _seed_demix(song)
    result = allin1.analyze(
        str(audio_path(song)),
        device=device,
        demix_dir=str(DEMIX_DIR),
        spec_dir="/tmp/allin1_spec",
        keep_byproducts=True,
    )
    return {
        "bpm": result.bpm,
        "beats": [float(b) for b in result.beats],
        "downbeats": [float(b) for b in result.downbeats],
        "beat_positions": [int(p) for p in result.beat_positions],
        "segments": [{"start": float(s.start), "end": float(s.end), "label": s.label}
                     for s in result.segments],
    }


def load(song: str, *, rebuild: bool = False) -> dict:
    path = cache_path(song)
    if rebuild or not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        data = compute(song)
        path.write_text(json.dumps(data, indent=1))
        return data
    return json.loads(path.read_text())


def boundaries(data: dict) -> np.ndarray:
    """Segment starts, minus the zero-length `start` marker."""
    return np.array([s["start"] for s in data["segments"] if s["start"] > 0.05])


def transitions(data: dict) -> list[tuple[float, str, str]]:
    """(time, label_before, label_after) for every change of label.

    Merging equal-labelled neighbours matters: allin1 emits one segment per
    8-bar phrase, so a 32-bar chorus arrives as four `chorus` rows and the
    musically real boundary is only where the label actually changes.
    """
    segments = data["segments"]
    out = []
    for prev, cur in zip(segments, segments[1:]):
        if prev["label"] != cur["label"]:
            out.append((float(cur["start"]), prev["label"], cur["label"]))
    return out
