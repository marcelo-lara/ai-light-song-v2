"""Load the trusted phase-1 artifacts this experiment reads directly, with no
recomputation — `fft_bands.json`'s existing normalisation is fine here (unlike
the reactive-bands entry, this one is not testing normalisation)."""
from __future__ import annotations

import json
from dataclasses import dataclass

import numpy as np

from . import paths

HIGH_BAND_IDX = (4, 5, 6)  # upper_mid, presence, brilliance
SUB_BAND_IDX = 0


@dataclass
class FftBands:
    times: np.ndarray
    levels: np.ndarray  # (F, 7)
    brightness: np.ndarray
    transient: np.ndarray
    dropout: np.ndarray


def load_fft_bands(song: str) -> FftBands:
    data = json.loads(paths.fft_bands_path(song).read_text())
    frames = data["frames"]
    return FftBands(
        times=np.array([f["time"] for f in frames]),
        levels=np.array([f["levels"] for f in frames]),
        brightness=np.array([f["brightness_ratio"] for f in frames]),
        transient=np.array([f["transient_strength"] for f in frames]),
        dropout=np.array([f["dropout_strength"] for f in frames]),
    )


@dataclass
class RmsLoudness:
    times: np.ndarray
    values: dict  # source_id -> (F,)


def load_rms_loudness(song: str) -> RmsLoudness:
    data = json.loads(paths.rms_loudness_path(song).read_text())
    ids = [s["id"] for s in data["sources"]]
    frames = data["frames"]
    times = np.array([f["time"] for f in frames])
    values = {sid: np.array([f["values"][i] for f in frames]) for i, sid in enumerate(ids)}
    return RmsLoudness(times=times, values=values)


def load_drum_events(song: str) -> list[dict]:
    path = paths.drum_events_path(song)
    if not path.exists():
        return []
    return json.loads(path.read_text())["events"]


def load_beats(song: str) -> list[dict]:
    return json.loads(paths.beats_path(song).read_text())


def load_hints(song: str) -> list[dict]:
    path = paths.hints_path(song)
    if not path.exists():
        return []
    return json.loads(path.read_text())["human_hints"]
