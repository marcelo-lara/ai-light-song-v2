"""Shared, cache-aware allin1 invocation for phase-1/2 stages.

allin1 (Kim & Nam, ISMIR 2023) is the one model this pipeline runs that both
`stages/segmentation.py` (3.1, the functional-label stage — item 7) and
`stages/timing.py` (1.2, the downbeat-phase derivation — item 8) need: the
former reads its `label` frame activation, the latter its `downbeat` frame
activation. Running the model twice in one pipeline pass would double allin1's
runtime for input that is byte-identical between the two callers (same seeded
stems, same song). This module is the single call site.

The first stage to run in a given pipeline pass invokes allin1, seeded with the
pipeline's own htdemucs stems (`_seed_demix`, ported unchanged from
`segmentation.py`'s original implementation — determinism is mandatory, not an
optimisation; see that module's docstring), and persists everything either
caller needs to `artifacts/allin1/raw.json`. Every later call in the same or a
subsequent pass reads that file back instead of invoking the model again. The
two callers see the same duck-typed `Allin1Result` (`.segments`, `.activations`)
whether the model just ran or the cache was read, which is what keeps their own
behaviour byte-identical to before this module existed.

Not a pipeline stage itself — no `STAGE_PIPELINE_IDS` entry, no stage-scoped
`generated_from` provenance block of its own (each caller still records its own
provenance, e.g. `seeded_stems`, in its own artifact). It is runtime
infrastructure shared across stages, which is why it lives at
`analyzer.allin1_cache` rather than under `analyzer.stages`.

Only `downbeat` and `label` activations are cached. allin1's own `beat`
activation and its `segment` boundary-novelty curve are not read by either
caller — allin1's own beat *times* sit a clean half-beat off essentia's on
several corpus songs and are never used in this pipeline — so they are dropped
rather than carried for no consumer.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from analyzer.exceptions import AnalysisError, DependencyError
from analyzer.io import read_json, write_json
from analyzer.paths import SongPaths

#: allin1's frame-level activations are emitted at a fixed 100 Hz
#: (`allin1.config` `fps: int = 100`), independent of song content.
ACTIVATION_RATE_HZ = 100.0

#: allin1 checks this directory for existing htdemucs separations before
#: running demucs itself — the seeding hook.
DEMIX_DIR = Path("/tmp/allin1_demix")
SPEC_DIR = "/tmp/allin1_spec"

#: Decimal digits kept when persisting activation floats. allin1's own
#: activations are float32 (~7 significant decimal digits); 9 digits after the
#: point at the [0, 1] scale these live on carries that precision through the
#: JSON round trip with margin to spare, so a cached read reproduces the exact
#: same downstream rounding a fresh run would.
ACTIVATION_PRECISION_DIGITS = 9


def _round(value: float, digits: int = 6) -> float:
    return round(float(value), digits)


@dataclass(slots=True)
class Allin1Segment:
    """Duck-types allin1's own segment objects (`.start`, `.end`, `.label`)."""
    start: float
    end: float
    label: str


@dataclass(slots=True)
class Allin1Result:
    """Duck-types the subset of allin1's `AnalysisResult` this pipeline reads:
    `.segments` (list of objects with `.start`/`.end`/`.label`) and
    `.activations` (dict of `"downbeat"` and `"label"` numpy arrays)."""
    segments: list[Allin1Segment]
    activations: dict[str, np.ndarray]


def _seed_demix(paths: SongPaths, stems: dict[str, str]) -> list[str]:
    """Point allin1 at the stems the pipeline already produced.

    Left to itself allin1 shells out to `demucs.separate`, and that separation
    is not reproducible run to run. The pipeline's stems are htdemucs output
    already (44.1 kHz stereo), the same thing allin1 would compute — so they
    are symlinked into the cache layout allin1's own demix step checks before
    separating, `harmonic` standing in for htdemucs's `other`. Ported unchanged
    from `experiments/allin1/model.py::_seed_demix`.

    Returns the stem names that were linked, recorded in `generated_from` so a
    run can be told apart from one that (incorrectly) let allin1 separate.
    """
    out = DEMIX_DIR / "htdemucs" / paths.song_path.stem
    out.mkdir(parents=True, exist_ok=True)
    linked: list[str] = []
    for target, source in (("bass", "bass"), ("drums", "drums"), ("other", "harmonic"), ("vocals", "vocals")):
        link = out / f"{target}.wav"
        source_path = Path(stems[source])
        if not source_path.exists():
            raise AnalysisError(
                f"{paths.song_name}: missing stem {source_path} for allin1 seeding — run ensure-stems first"
            )
        if link.exists() or link.is_symlink():
            link.unlink()
        link.symlink_to(source_path)
        linked.append(target)
    return linked


def _invoke_allin1(paths: SongPaths, stems: dict[str, str]) -> tuple[Any, list[str], dict[str, Any]]:
    try:
        import allin1
    except ImportError as exc:
        raise DependencyError("allin1 is required for section segmentation and downbeat phase") from exc

    seeded = _seed_demix(paths, stems)
    try:
        result = allin1.analyze(
            str(paths.song_path),
            demix_dir=str(DEMIX_DIR),
            spec_dir=SPEC_DIR,
            include_activations=True,
            keep_byproducts=True,
        )
    except Exception as exc:  # pragma: no cover - depends on the external model runtime
        raise AnalysisError(f"allin1 analysis failed for {paths.song_name}: {exc}") from exc

    if result is None or not getattr(result, "segments", None):
        raise AnalysisError(f"allin1 returned no segments for {paths.song_name}")
    activations = getattr(result, "activations", None)
    if not activations:
        raise AnalysisError(f"allin1 returned no frame activations for {paths.song_name} (include_activations=True)")
    if "downbeat" not in activations:
        raise AnalysisError(f"allin1 activations for {paths.song_name} are missing 'downbeat' — model version may have changed")
    if "label" not in activations:
        raise AnalysisError(f"allin1 activations for {paths.song_name} are missing 'label' — model version may have changed")
    return result, seeded, activations


def _build_payload(paths: SongPaths, stems: dict[str, str], result: Any, seeded_stems: list[str], activations: dict[str, Any]) -> dict:
    downbeat = np.asarray(activations["downbeat"], dtype=np.float64)
    label = np.asarray(activations["label"], dtype=np.float64)
    segments = [
        {"start": _round(segment.start), "end": _round(segment.end), "label": str(segment.label)}
        for segment in result.segments
    ]
    return {
        "song_name": paths.song_name,
        "generated_from": {
            "source_song_path": str(paths.song_path),
            "engine": "allin1.harmonix-all.v1",
            "dependencies": {
                "stems": {name: str(path) for name, path in stems.items()},
            },
            "seeded_stems": seeded_stems,
            "seeding_note": (
                "allin1 was seeded with the pipeline's own htdemucs stems rather than "
                "separating the mix itself — mandatory for determinism (determinism: same input + engine version must give byte-identical artifacts)."
            ),
        },
        "fps": ACTIVATION_RATE_HZ,
        "segments": segments,
        "activations": {
            "downbeat": [_round(value, ACTIVATION_PRECISION_DIGITS) for value in downbeat.tolist()],
            "label": [[_round(value, ACTIVATION_PRECISION_DIGITS) for value in row] for row in label.tolist()],
        },
    }


def _result_from_payload(payload: dict) -> Allin1Result:
    segments = [
        Allin1Segment(start=float(row["start"]), end=float(row["end"]), label=str(row["label"]))
        for row in payload["segments"]
    ]
    activations = {
        "downbeat": np.asarray(payload["activations"]["downbeat"], dtype=np.float64),
        "label": np.asarray(payload["activations"]["label"], dtype=np.float64),
    }
    return Allin1Result(segments=segments, activations=activations)


def get_allin1_result(paths: SongPaths, stems: dict[str, str]) -> tuple[Allin1Result, list[str]]:
    """Return allin1's segments + `downbeat`/`label` activations for this song,
    running the model only if `artifacts/allin1/raw.json` does not already
    exist. Both the fresh-run path and the cached-read path build the returned
    `Allin1Result` from the same JSON-serialised payload, so a caller's output
    is identical whether it triggered the run or read a cache another stage
    already populated in this pass.
    """
    cache_path = paths.artifact("allin1", "raw.json")
    if cache_path.exists():
        payload = read_json(cache_path)
        return _result_from_payload(payload), list(payload["generated_from"]["seeded_stems"])

    result, seeded_stems, activations = _invoke_allin1(paths, stems)
    payload = _build_payload(paths, stems, result, seeded_stems, activations)
    write_json(cache_path, payload)
    return _result_from_payload(payload), seeded_stems
