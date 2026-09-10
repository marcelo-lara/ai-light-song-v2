from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass, field, is_dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from analyzer.paths import SongPaths


SCHEMA_VERSION = "3.0"


class Producer(str, Enum):
    """Closed vocabulary for the `field_sources` attribution header on every
    top-level (delivery-surface) file. A published value's `source` — file-level
    default or per-row override — must be one of these. An unrecognised producer
    string is an error, never a passthrough: see `validate_field_sources`."""

    ESSENTIA = "essentia"
    ALLIN1 = "allin1"
    HARMONIC = "harmonic"
    OMNIZART = "omnizart"
    DEMUCS = "demucs"
    GESTURES = "gestures"
    ARRANGEMENT_STATE = "arrangement_state"
    SECTION_FUNCTION = "section_function"
    GENRE = "genre"
    HUMAN = "human"
    INFERENCE = "inference"
    UNKNOWN = "unknown"


PRODUCERS: frozenset[str] = frozenset(p.value for p in Producer)

# Keys that a top-level payload may carry without a `field_sources` entry: they
# are identity/provenance metadata, not fused musical values.
_FIELD_SOURCES_RESERVED: frozenset[str] = frozenset(
    {"schema_version", "generated_from", "field_sources", "song_name"}
)


def validate_field_sources(
    field_sources: dict[str, str],
    emitted_keys: Iterable[str],
    *,
    file: str,
    exempt: Iterable[str] = (),
) -> dict[str, str]:
    """Enforce the attribution convention for one top-level file:

    - every `field_sources` value is a known `Producer` (unknown => error);
    - the header covers every emitted key except reserved metadata and the
      caller-supplied `exempt` set.

    Returns `field_sources` unchanged so it can be used inline when building a
    payload.
    """
    bad = sorted(v for v in field_sources.values() if v not in PRODUCERS)
    if bad:
        raise ValueError(
            f"{file}: field_sources has producer(s) outside the closed vocabulary: "
            f"{bad}. Allowed: {sorted(PRODUCERS)}"
        )
    covered = set(field_sources) | _FIELD_SOURCES_RESERVED | set(exempt)
    missing = sorted(k for k in emitted_keys if k not in covered)
    if missing:
        raise ValueError(
            f"{file}: field_sources header does not cover emitted field(s): {missing}"
        )
    return field_sources


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
    """`confidence` is populated only on `type == "downbeat"` rows, from
    allin1's downbeat-activation strength at that beat time
    (`analyzer.stages.timing`, plan v3.0 item 8). It is `None` on `"beat"`
    rows, and `None` on a `"downbeat"` row where essentia's and allin1's
    phases disagree by a whole beat or more — the smallest honest encoding of
    "the bar grid is unresolved here" (the bar grid is honestly unresolved rather than snapped)."""
    index: int
    time: float
    bar: int
    beat_in_bar: int
    type: str
    confidence: float | None = None


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
class SectionSegment:
    """One merged, equal-labelled run from the allin1 segmentation stage
    (`analyzer.stages.segmentation`). See that module's docstring for how each
    field is computed. `function` is the Harmonix functional label; `same_label_as`
    is label repetition ("the third thing allin1 called a chorus"), not acoustic
    identity — never read it as "the same music as"."""
    section_id: str
    start: float
    end: float
    function: str | None
    function_confidence: float | None
    function_status: str
    same_label_as: str | None
    confidence: float
