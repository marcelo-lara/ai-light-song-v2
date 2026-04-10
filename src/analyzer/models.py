from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from analyzer.paths import SongPaths


SCHEMA_VERSION = "1.0"


def round_schema_float(value: float, digits: int = 2) -> float:
    return round(float(value), digits)


def build_song_schema_fields(
    paths: SongPaths,
    *,
    bpm: float | None = None,
    duration: float | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"song_name": paths.song_name}
    if bpm is not None:
        payload["bpm"] = round_schema_float(bpm)
    if duration is not None:
        payload["duration"] = round_schema_float(duration)
    return payload


def to_jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return to_jsonable(asdict(value))
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {key: to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    return value


@dataclass(slots=True)
class GeneratedFrom:
    source_song_path: str
    engine: str | None = None
    beats_file: str | None = None
    harmonic_stem: str | None = None
    dependencies: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class BeatPoint:
    index: int
    time: float
    bar: int
    beat_in_bar: int
    type: str


@dataclass(slots=True)
class BarWindow:
    bar: int
    start_s: float
    end_s: float


@dataclass(slots=True)
class ChordEvent:
    time: float
    end_s: float
    bar: int
    beat: int
    chord: str
    confidence: float


@dataclass(slots=True)
class EnergyFrame:
    time: float
    frame_index: int
    loudness: float
    spectral_centroid: float
    spectral_flux: float
    onset_strength: float


@dataclass(slots=True)
class EnergyBeat:
    beat: int
    time: float
    loudness_avg: float
    centroid_avg: float
    flux_avg: float
    onset_density: float


@dataclass(slots=True)
class SectionWindow:
    section_id: str
    start: float
    end: float
    label: str | None
    confidence: float
    section_character: str | None = None
