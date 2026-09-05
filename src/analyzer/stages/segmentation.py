"""Phase 2 (interpret) — named functional segmentation from All-In-One.

Replaces `stages/sections/` (`segmenter.py`, `form.py`, `utils.py`): an 8-bar
deterministic-DSP phrase segmenter whose boundaries measured at 0.32 recall /
0.27 precision / 0.29 F1 against `reference/moises/segments.json` — worse than
an evenly spaced grid at the same boundary budget — plus a 13-value invented
`section_character` mood vocabulary with no ground truth behind it.

This stage runs All-In-One (Kim & Nam, ISMIR 2023), a multi-task model that
predicts an 8-bar phrase segmentation labelled from the Harmonix vocabulary
(`intro outro break bridge inst solo verse chorus`, plus the `start`/`end`
sentinels it emits at the very edges). Ported from `experiments/allin1/` after
the experiment's own comparison there:

    | boundaries shipped        | recall @±1.0s | precision | F1   | bounds/min |
    | -------------------------- | ------------- | --------- | ---- | ---------- |
    | allin1 merged sections      | 0.53          | 0.91      | 0.67 | 1.8        |
    | allin1 raw phrase edges     | 0.84          | 0.76      | 0.80 | 3.4        |
    | old sections/ segmenter     | 0.32          | 0.27      | 0.29 | 3.7        |

Merged section runs are shipped, not raw phrase edges — a boundary the cue
author can trust is worth more than one more recalled boundary, and merging
equal-labelled neighbours is what turns an 8-bar phrase grid into song form.

Determinism (constitution §6). allin1 shells out to `demucs` itself unless
handed stems, and that separation is not reproducible run to run — the
experiment's caches disagreed on 14 of 21 songs across two unseeded runs.
Seeded with the pipeline's own htdemucs stems (`_seed_demix` in
`analyzer.allin1_cache`) it produced byte-identical section sequences over
three consecutive runs on every
gold song. Seeding is therefore mandatory, not an optimisation, and this stage
never falls back to letting allin1 separate the mix itself.

Honesty (constitution §2 — no silent fallbacks). Where allin1 gives a song
fewer than `MIN_DISTINCT_LABELS` distinct functional labels, or one label
covers more than `DOMINANT_LABEL_MAX_SHARE` of the track, the *name* is not
trustworthy — allin1 is outside the training distribution it was fit on (short
excerpts, purely instrumental passages). `function_status` is set to
`"unknown"` on every section of that song; the boundaries are left as measured,
because a degenerate label set says nothing about whether the boundary
timing is wrong.

Scope. This stage never reads allin1's own beat or downbeat times — only its
segment/label output. The downbeat *phase* is a separate, later pipeline item
(`stages/timing.py`, item 8); allin1's own beat grid sits a clean half-beat off
essentia's on several corpus songs and is not a second opinion worth having
here.

allin1 itself is invoked through `analyzer.allin1_cache`, not directly — that
module is the single call site shared with `stages/timing.py`, which also
needs allin1's frame activations (its `downbeat` stream) and would otherwise
force the model to run twice in one pipeline pass. See that module's docstring
for the caching contract; this stage's own behaviour and output are unchanged
by that refactor.
"""
from __future__ import annotations

from typing import Any

import numpy as np

from analyzer.allin1_cache import ACTIVATION_RATE_HZ, get_allin1_result
from analyzer.exceptions import AnalysisError
from analyzer.io import write_json
from analyzer.models import SCHEMA_VERSION, SectionSegment, to_jsonable
from analyzer.paths import SongPaths

#: allin1's fixed label order (`allin1.config.HARMONIX_LABELS`). `start` and
#: `end` are edge sentinels the model emits at the very start/end of the
#: track, not musical categories.
SENTINEL_LABELS = ("start", "end")
HARMONIX_LABELS = ("start", "end", "intro", "outro", "break", "bridge", "inst", "solo", "verse", "chorus")
MUSICAL_LABELS = tuple(label for label in HARMONIX_LABELS if label not in SENTINEL_LABELS)

#: A song's functional *names* are untrustworthy (constitution §2 — an honest
#: `unknown` beats a confident wrong label) when allin1 gives it fewer than
#: this many distinct labels, or one label covers more than this share of the
#: track. Boundaries are unaffected — only `function` and `function_confidence`
#: become meaningless when the model has this little to say.
MIN_DISTINCT_LABELS = 3
DOMINANT_LABEL_MAX_SHARE = 0.90


def _round(value: float, digits: int = 6) -> float:
    return round(float(value), digits)


def _run_allin1(paths: SongPaths, stems: dict[str, str]) -> tuple[Any, list[str]]:
    return get_allin1_result(paths, stems)


def _phrase_rows(result: Any) -> list[dict[str, Any]]:
    """allin1's own 8-bar phrase segments, sentinels dropped, time-sorted."""
    rows = [
        {"start": float(segment.start), "end": float(segment.end), "function": str(segment.label)}
        for segment in result.segments
        if str(segment.label) not in SENTINEL_LABELS
    ]
    rows.sort(key=lambda row: row["start"])
    if not rows:
        raise AnalysisError("allin1 returned only sentinel (start/end) segments — no musical labels to merge")
    return rows


def merge_equal_labelled_runs(phrase_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge consecutive equal-labelled phrases into song-form section runs.

    allin1 emits one row per 8-bar phrase, so a 32-bar chorus arrives as four
    consecutive `chorus` rows; the musically real boundary is only where the
    label actually changes. Precision comes from shipping these merged runs
    (measured 0.91) rather than the raw phrase edges (measured 0.76) — this is
    the step that turns an 8-bar phrase grid into song form, and skipping it is
    the most likely cause if precision regresses.
    """
    runs: list[dict[str, Any]] = []
    for row in phrase_rows:
        if runs and runs[-1]["function"] == row["function"] and abs(runs[-1]["end"] - row["start"]) < 0.25:
            runs[-1]["end"] = row["end"]
        else:
            runs.append({"function": row["function"], "start": row["start"], "end": row["end"]})
    return runs


def _label_posterior(activations: dict[str, Any]) -> tuple[list[str], np.ndarray]:
    """Renormalised per-frame posterior over the musical vocabulary only.

    allin1's `label` activation is already a softmax over all ten Harmonix
    labels (sentinels included), so it sums to 1 per frame *before* the
    sentinels are dropped. Once `start`/`end` are removed the remaining eight
    musical labels no longer sum to 1, so they are renormalised — otherwise a
    frame where the model leaned on a sentinel would read as artificially
    low-entropy across the musical labels that are left.
    """
    matrix = np.asarray(activations["label"], dtype=np.float64)
    if matrix.shape[0] != len(HARMONIX_LABELS):
        raise AnalysisError(
            f"allin1 label activations have {matrix.shape[0]} rows, expected {len(HARMONIX_LABELS)} "
            "(HARMONIX_LABELS order); the model version may have changed"
        )
    keep = [index for index, label in enumerate(HARMONIX_LABELS) if label in MUSICAL_LABELS]
    musical = matrix[keep, :]
    musical = musical / (musical.sum(axis=0, keepdims=True) + 1e-9)
    return list(MUSICAL_LABELS), musical


def _entropy_confidence(posterior_slice: np.ndarray) -> float:
    """1 − normalised Shannon entropy of a posterior slice, in [0, 1].

    0 means the model spread its mass evenly over the musical vocabulary across
    this section (no opinion); 1 means it put all its mass on one label the
    whole time. Ported from `experiments/allin1/activations.py::entropy`.
    """
    if posterior_slice.size == 0:
        return 0.0
    n_labels = posterior_slice.shape[0]
    frame_entropy = -(posterior_slice * np.log(posterior_slice + 1e-9)).sum(axis=0) / np.log(n_labels)
    mean_entropy = float(np.mean(frame_entropy))
    return max(0.0, min(1.0, 1.0 - mean_entropy))


def _function_confidence_for_span(
    labels: list[str], posterior: np.ndarray, start: float, end: float
) -> float:
    n_frames = posterior.shape[1]
    start_index = max(0, min(n_frames, int(round(start * ACTIVATION_RATE_HZ))))
    end_index = max(start_index + 1, min(n_frames, int(round(end * ACTIVATION_RATE_HZ))))
    return _entropy_confidence(posterior[:, start_index:end_index])


def _labelling_status(sections: list[dict[str, Any]], duration: float) -> str:
    """`"unknown"` when allin1 is outside the distribution it can reliably name.

    Detectable without ground truth: a song with fewer than `MIN_DISTINCT_LABELS`
    distinct functions, or where one function covers more than
    `DOMINANT_LABEL_MAX_SHARE` of the track, is the model running out of
    opinions — the failure mode measured on short excerpts and purely
    instrumental material. Boundaries stay as measured; only the name is
    untrusted.
    """
    if not sections or duration <= 0:
        return "unknown"
    share: dict[str, float] = {}
    for section in sections:
        share[section["function"]] = share.get(section["function"], 0.0) + (section["end"] - section["start"])
    distinct = len(share)
    dominant_share = max(share.values()) / duration if duration > 0 else 1.0
    if distinct < MIN_DISTINCT_LABELS or dominant_share > DOMINANT_LABEL_MAX_SHARE:
        return "unknown"
    return "known"


def _boundary_confidence(function_confidence: float, index: int) -> float:
    """Boundary confidence for a merged run. The first section's start is fixed
    at 0.0 and trivially correct; every other boundary is where allin1's own
    label posterior actually changed, so its evidence is the label confidence
    itself — there is no independent boundary detector in this stage (that is
    the raw phrase edge, which this stage deliberately does not ship).
    """
    if index == 0:
        return 0.9
    return function_confidence


def segment_sections(paths: SongPaths, stems: dict[str, str], timing: dict) -> dict:
    """Run allin1 seeded with the pipeline's own stems, merge its 8-bar phrase
    segments into song-form section runs, and score each run's label
    confidence from the model's own frame-level posterior. See the module
    docstring for the full rationale."""
    result, seeded_stems = _run_allin1(paths, stems)
    phrase_rows = _phrase_rows(result)
    merged_runs = merge_equal_labelled_runs(phrase_rows)

    song_end = float(timing["bars"][-1]["end_s"]) if timing.get("bars") else merged_runs[-1]["end"]
    if merged_runs:
        merged_runs[0]["start"] = 0.0
        merged_runs[-1]["end"] = song_end
    duration = song_end

    activations = getattr(result, "activations", None)
    if not activations:
        raise AnalysisError(f"allin1 returned no frame activations for {paths.song_name} (include_activations=True)")
    labels, posterior = _label_posterior(activations)

    status = _labelling_status(merged_runs, duration)

    first_section_id_by_function: dict[str, str] = {}
    sections: list[SectionSegment] = []
    for index, run in enumerate(merged_runs):
        section_id = f"section-{index + 1:03d}"
        function = run["function"]
        function_confidence = round(_function_confidence_for_span(labels, posterior, run["start"], run["end"]), 6)
        same_label_as = first_section_id_by_function.get(function)
        if same_label_as is None:
            first_section_id_by_function[function] = section_id
        confidence = round(_boundary_confidence(function_confidence, index), 6)
        sections.append(
            SectionSegment(
                section_id=section_id,
                start=_round(run["start"]),
                end=_round(run["end"]),
                function=function,
                function_confidence=function_confidence,
                function_status=status,
                same_label_as=same_label_as,
                confidence=confidence,
            )
        )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": paths.song_name,
        "generated_from": {
            "source_song_path": str(paths.song_path),
            "engine": "allin1.harmonix-all.section_segmentation.v1",
            "dependencies": {
                "stems": {name: str(path) for name, path in stems.items()},
            },
            "seeded_stems": seeded_stems,
            "seeding_note": (
                "allin1 was seeded with the pipeline's own htdemucs stems rather than "
                "separating the mix itself — mandatory for determinism (constitution §6)."
            ),
            "merge_strategy": "consecutive equal-labelled 8-bar phrases merged into one section run",
            "function_confidence_strategy": "1 - normalised Shannon entropy of allin1's frame-level label posterior within the section span",
            "labelling_status": status,
            "phrase_count": len(phrase_rows),
        },
        "sections": to_jsonable(sections),
    }
    write_json(paths.artifact("section_segmentation", "sections.json"), payload)
    return payload
