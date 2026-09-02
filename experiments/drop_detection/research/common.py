"""Shared plumbing for the song-dynamics model survey.

Deliberately independent of `src/analyzer` — this is a research sandbox that
reads the same artifacts the pipeline writes and never writes into them.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[3]
ANALYSIS_ROOT = REPO_ROOT / "data" / "analysis"
SONGS_ROOT = REPO_ROOT / "data" / "songs"
CACHE_ROOT = Path(__file__).resolve().parent / "cache"
OUT_ROOT = Path(__file__).resolve().parent / "out"

# The four songs that carry hand-placed `drop impact` marks.
GOLD_SONGS = [
    "_test_song",
    "Hideaway - Kiesza",
    "Armin - Revolution",
    "Titanium - David Guetta ft Sia",
]


def all_songs() -> list[str]:
    return sorted(p.name for p in ANALYSIS_ROOT.iterdir() if p.is_dir())


def audio_path(song: str) -> Path:
    return SONGS_ROOT / f"{song}.mp3"


def stem_path(song: str, stem: str) -> Path:
    return ANALYSIS_ROOT / song / "artifacts" / "stems" / f"{stem}.wav"


def load_audio(song: str, sr: int) -> np.ndarray:
    import librosa

    wave, _ = librosa.load(str(audio_path(song)), sr=sr, mono=True)
    return wave.astype(np.float32)


@dataclass
class BeatGrid:
    beats: np.ndarray
    downbeats: np.ndarray

    @property
    def median_period(self) -> float:
        return float(np.median(np.diff(self.beats))) if len(self.beats) > 2 else float("nan")


def essentia_grid(song: str) -> BeatGrid:
    payload = json.loads((ANALYSIS_ROOT / song / "artifacts" / "essentia" / "beats.json").read_text())
    beats = np.array([float(b["time"]) for b in payload["beats"]])
    downs = np.array([float(b["time"]) for b in payload["beats"] if b.get("type") == "downbeat"])
    return BeatGrid(beats, downs)


def human_impacts(song: str) -> list[float]:
    """The hand-placed `drop impact` start instants — the only hard labels."""
    path = ANALYSIS_ROOT / song / "reference" / "human" / "human_hints.json"
    if not path.exists():
        return []
    payload = json.loads(path.read_text())
    out = [
        float(h["start_time"])
        for h in payload.get("human_hints", [])
        if str(h.get("title", "")).strip().casefold() == "drop impact"
    ]
    return sorted(out)


def gold_impacts() -> dict[str, list[float]]:
    return {song: human_impacts(song) for song in GOLD_SONGS}


def cache_file(kind: str, song: str) -> Path:
    path = CACHE_ROOT / kind / f"{song.replace('/', '_')}.npz"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def out_file(name: str) -> Path:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    return OUT_ROOT / name


# ---------------------------------------------------------------- scoring ---


def nearest_error(targets: np.ndarray, marks: list[float]) -> list[float]:
    """Signed distance from each mark to the nearest target (target - mark)."""
    if len(targets) == 0:
        return [float("nan")] * len(marks)
    return [float(targets[int(np.argmin(np.abs(targets - m)))] - m) for m in marks]


def hit_rate(targets: np.ndarray, marks: list[float], tol: float) -> tuple[int, int]:
    errs = nearest_error(targets, marks)
    return sum(1 for e in errs if abs(e) <= tol), len(marks)


def peak_pick(curve: np.ndarray, times: np.ndarray, *, min_gap: float, top_k: int | None = None,
              threshold: float | None = None) -> list[int]:
    """Greedy peak picking with a hard minimum spacing (NMS in time)."""
    order = np.argsort(curve)[::-1]
    chosen: list[int] = []
    for idx in order:
        if threshold is not None and curve[idx] < threshold:
            break
        if any(abs(times[idx] - times[c]) < min_gap for c in chosen):
            continue
        chosen.append(int(idx))
        if top_k is not None and len(chosen) >= top_k:
            break
    return sorted(chosen)


def snap(values: np.ndarray, grid: np.ndarray) -> np.ndarray:
    if len(grid) == 0:
        return values
    idx = np.argmin(np.abs(values[:, None] - grid[None, :]), axis=1)
    return grid[idx]
