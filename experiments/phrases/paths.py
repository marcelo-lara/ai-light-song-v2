"""Where this experiment reads and writes.

`src/` never imports this package (docs/experiments.md sandbox rule). Reads,
read-only, from `data/analysis/<song>/`:

* top-level: `beats.json` (times + `off_grid_spans`; downbeats / bar numbers are
  never read), `info.json`, `loudness.json` (per-stem), `arrangement_state.json`,
  `song_event_timeline.json` (gestures impacts);
* `artifacts/essentia/`: `fft_bands.json` (mix), `fft_bands.drums.json`,
  `beats.json` (the primitive detectors' own input), `rms_loudness.json`;
  `artifacts/symbolic_transcription/drum_events.json` (snare-roll primitive only);
* other experiments' proposals, as data: `reference/proposals/filter_sweep.json`,
  `reference/proposals/stem_presence_sections.json`;
* scoring only: `artifacts/allin1/raw.json`, `reference/human/{segments,human_hints}.json`,
  `reference/pre-analysis/structure.json` (`genre.family`).

Writes: `cache/<song>.json` and `reference/proposals/phrases.json`.
"""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(os.environ.get("PHRASES_EXP_REPO", Path(__file__).resolve().parents[2]))
ANALYSIS_ROOT = REPO_ROOT / "data" / "analysis"
CACHE_ROOT = Path(__file__).resolve().parent / "cache"
OUT_ROOT = Path(__file__).resolve().parent / "out"


def _song(song: str) -> Path:
    return ANALYSIS_ROOT / song


def beats_path(song: str) -> Path:
    return _song(song) / "beats.json"


def info_path(song: str) -> Path:
    return _song(song) / "info.json"


def loudness_path(song: str) -> Path:
    return _song(song) / "loudness.json"


def arrangement_path(song: str) -> Path:
    return _song(song) / "arrangement_state.json"


def timeline_path(song: str) -> Path:
    return _song(song) / "song_event_timeline.json"


def mix_fft_path(song: str) -> Path:
    return _song(song) / "artifacts" / "essentia" / "fft_bands.json"


def drums_fft_path(song: str) -> Path:
    return _song(song) / "artifacts" / "essentia" / "fft_bands.drums.json"


def essentia_beats_path(song: str) -> Path:
    return _song(song) / "artifacts" / "essentia" / "beats.json"


def rms_path(song: str) -> Path:
    return _song(song) / "artifacts" / "essentia" / "rms_loudness.json"


def drum_events_path(song: str) -> Path:
    return _song(song) / "artifacts" / "symbolic_transcription" / "drum_events.json"


def allin1_raw_path(song: str) -> Path:
    return _song(song) / "artifacts" / "allin1" / "raw.json"


def structure_hint_path(song: str) -> Path:
    return _song(song) / "reference" / "pre-analysis" / "structure.json"


def human_segments_path(song: str) -> Path:
    return _song(song) / "reference" / "human" / "segments.json"


def human_hints_path(song: str) -> Path:
    return _song(song) / "reference" / "human" / "human_hints.json"


def filter_sweep_path(song: str) -> Path:
    return _song(song) / "reference" / "proposals" / "filter_sweep.json"


def stem_presence_path(song: str) -> Path:
    return _song(song) / "reference" / "proposals" / "stem_presence_sections.json"


def proposals_path(song: str) -> Path:
    return _song(song) / "reference" / "proposals" / "phrases.json"


def cache_path(song: str) -> Path:
    return CACHE_ROOT / f"{song.replace('/', '_')}.json"


def required_inputs(song: str) -> list[Path]:
    return [
        beats_path(song), info_path(song), loudness_path(song), arrangement_path(song),
        timeline_path(song), mix_fft_path(song), drums_fft_path(song),
        essentia_beats_path(song), rms_path(song), drum_events_path(song),
    ]


def all_songs() -> list[str]:
    """Every song directory carrying all required inputs."""
    return sorted(
        p.name for p in ANALYSIS_ROOT.iterdir()
        if p.is_dir() and all(q.exists() for q in required_inputs(p.name))
    )
