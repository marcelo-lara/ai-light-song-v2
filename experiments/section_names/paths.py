"""Where this experiment reads and writes.

`src/` never imports this package (docs/experiments.md sandbox rule). Reads,
read-only, from `data/analysis/<song>/`:

* top-level: `beats.json` (times + `off_grid_spans`; downbeats / bar numbers are
  never read), `info.json`, `loudness.json`, `arrangement_state.json`
  (`vocals_phrase` spans), `song_event_timeline.json` (`impact` rows only),
  `sections.json` (`start`/`end`/`function`/`function_confidence` of the CURRENT
  rows, only to keep them when a song has no build->drop unit; `energy`,
  `tension` and every other field are never read);
* `artifacts/essentia/`: `fft_bands.json`, `fft_bands.drums.json`,
  `beats.json`, `rms_loudness.json`; `artifacts/symbolic_transcription/drum_events.json`
  (snare-roll primitive only);
* other experiments' proposals, as data: `reference/proposals/phrases.json`
  (required);
* the structure hint `reference/pre-analysis/structure.json` (a prior only);
* scoring only: `artifacts/allin1/raw.json`, `reference/human/segments.json`.

Writes: `cache/<song>.json` and `reference/proposals/section_names.json`.
"""
from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(os.environ.get("SECTION_NAMES_EXP_REPO", Path(__file__).resolve().parents[2]))
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


def sections_path(song: str) -> Path:
    return _song(song) / "sections.json"


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


def phrases_path(song: str) -> Path:
    return _song(song) / "reference" / "proposals" / "phrases.json"


def proposals_path(song: str) -> Path:
    return _song(song) / "reference" / "proposals" / "section_names.json"


def cache_path(song: str) -> Path:
    return CACHE_ROOT / f"{song.replace('/', '_')}.json"


def required_inputs(song: str) -> list[Path]:
    return [
        beats_path(song), info_path(song), loudness_path(song), arrangement_path(song),
        timeline_path(song), sections_path(song), mix_fft_path(song), drums_fft_path(song),
        essentia_beats_path(song), rms_path(song), drum_events_path(song), phrases_path(song),
    ]


def all_songs() -> list[str]:
    """Every song directory carrying all required inputs."""
    return sorted(
        p.name for p in ANALYSIS_ROOT.iterdir()
        if p.is_dir() and all(q.exists() for q in required_inputs(p.name))
    )
