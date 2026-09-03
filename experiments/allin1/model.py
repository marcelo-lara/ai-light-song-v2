"""Run `allin1` and cache its raw output, one JSON per song.

All-In-One (Kim & Nam, ISMIR 2023) is a single multi-task model that predicts
beats, downbeats, tempo and a functional segmentation labelled from the Harmonix
vocabulary. It is the only model in the survey that outputs *named* structure,
which is the thing the shipped segmentation has no equivalent of.

This module owns exactly one job: get the model's own numbers onto disk,
unmodified. Everything derived from them lives in `features.py`, so the
expensive GPU step never has to be repeated when the derivation changes.

Runs in the `ai-light-song-v2-allin1:dev` sandbox only (natten 0.15 / torch 2.1);
see `run_in_container.sh`.
"""
from __future__ import annotations

import json
from pathlib import Path

from .paths import audio_path, raw_cache_path, stem_path

SCHEMA = "allin1-raw/1.0"

#: allin1 writes its own demucs output here and checks the directory before
#: separating, which is the hook used to hand it the stems we already have.
DEMIX_DIR = Path("/tmp/allin1_demix")
SPEC_DIR = "/tmp/allin1_spec"


def _seed_demix(song: str) -> list[str]:
    """Point allin1 at the stems the pipeline already produced.

    Left to itself allin1 shells out to `demucs.separate` on the GPU while
    holding its own model resident, which OOMs a 4 GB card partway through a
    corpus run. The repo's stems are htdemucs output at 44.1 kHz stereo already
    — the same thing allin1 would compute — so they are linked into the layout
    its cache check expects, `harmonic` standing in for htdemucs's `other`.

    Returns the stems that were linked, so a caller can record that the run was
    seeded rather than separated.
    """
    out = DEMIX_DIR / "htdemucs" / audio_path(song).stem
    out.mkdir(parents=True, exist_ok=True)
    linked = []
    for target, source in (("bass", "bass"), ("drums", "drums"),
                           ("other", "harmonic"), ("vocals", "vocals")):
        link = out / f"{target}.wav"
        src = stem_path(song, source)
        if not src.exists():
            raise FileNotFoundError(f"{song}: missing stem {src} — run the pipeline first")
        if not link.exists():
            link.symlink_to(src)
        linked.append(target)
    return linked


def compute(song: str, *, device: str = "cuda") -> dict:
    """Every field allin1 returns, converted to plain JSON types and nothing else."""
    import allin1

    seeded = _seed_demix(song)
    result = allin1.analyze(
        str(audio_path(song)),
        device=device,
        demix_dir=str(DEMIX_DIR),
        spec_dir=SPEC_DIR,
        keep_byproducts=True,
    )
    return {
        "schema": SCHEMA,
        "song_name": song,
        "source": {
            "model": "allin1 (Kim & Nam 2023), harmonix-all checkpoint",
            "device": device,
            "stems": f"pipeline htdemucs stems, seeded ({', '.join(seeded)})",
        },
        "bpm": result.bpm,
        "beats": [float(b) for b in result.beats],
        "downbeats": [float(b) for b in result.downbeats],
        "beat_positions": [int(p) for p in result.beat_positions],
        "segments": [
            {"start": float(s.start), "end": float(s.end), "label": s.label}
            for s in result.segments
        ],
    }


def load(song: str, *, rebuild: bool = False) -> dict:
    """Cached `compute`. Reading a cache never needs the allin1 environment."""
    path = raw_cache_path(song)
    if rebuild or not path.exists():
        data = compute(song)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=1) + "\n")
        return data
    return json.loads(path.read_text())


def cached_songs(songs: list[str]) -> list[str]:
    return [song for song in songs if raw_cache_path(song).exists()]
