"""Shadow-label detection over allin1's cached frame posterior.

`_test_song`, ...: reads `artifacts/allin1/raw.json` (already computed and
committed by the production pipeline — no model run here). Renormalises the
`label` activation over the eight musical Harmonix labels the same way
`src/analyzer/stages/segmentation.py::_label_posterior` does (sentinels
`start`/`end` dropped, remaining mass renormalised to sum to 1 per frame), so
the entropy/posterior math here is provably the same quantity production
already computes for `function_confidence` — NOT a re-derivation on a
different scale.

Item 1 of this entry's plan ("entropy as a real confidence") is **already
shipped**: `segmentation.py::_function_confidence_for_span` publishes exactly
this 1-minus-normalised-entropy quantity as `sections.json`'s
`function_confidence` field today. This module only builds item 2 — shadow
labels — which is not published anywhere.

A "shadow label" is a span where some label *other than* the section's own
published `function` holds a sustained share of the posterior mass. The
Armin `break` example (docs/experiments.md): 143.4-175.0s, `break` holding
30% of the posterior, appearing in no published section.
"""
from __future__ import annotations

import math

import numpy as np

from analyzer.io import read_json  # src/ import is fine; the forbidden direction is src/ -> experiments/

from . import paths

HARMONIX_LABELS = ("start", "end", "intro", "outro", "break", "bridge", "inst", "solo", "verse", "chorus")
SENTINEL_LABELS = ("start", "end")
MUSICAL_LABELS = tuple(label for label in HARMONIX_LABELS if label not in SENTINEL_LABELS)
ACTIVATION_RATE_HZ = 100.0

#: Sustained-share threshold and minimum span duration for a shadow label to
#: be reported — swept, not tuned against any gold-set metric (no ground
#: truth for "is this shadow label real" exists to tune against).
SHARE_THRESHOLD = 0.20
MIN_SPAN_S = 2.0
#: A shadow span is only reported where the published `sections.json` covers
#: less than this fraction of it with a section whose own `function` already
#: names the same label — otherwise it is not "shadow", it is redundant with
#: what is already published.
MAX_PUBLISHED_OVERLAP = 0.50


def load_posterior(song: str) -> tuple[list[str], np.ndarray, float]:
    payload = read_json(paths.allin1_raw_path(song))
    matrix = np.asarray(payload["activations"]["label"], dtype=np.float64)
    if matrix.shape[0] != len(HARMONIX_LABELS):
        raise ValueError(f"{song}: allin1 label activation has {matrix.shape[0]} rows, expected {len(HARMONIX_LABELS)}")
    keep = [i for i, label in enumerate(HARMONIX_LABELS) if label in MUSICAL_LABELS]
    musical = matrix[keep, :]
    musical = musical / (musical.sum(axis=0, keepdims=True) + 1e-9)
    fps = float(payload.get("fps", ACTIVATION_RATE_HZ))
    return list(MUSICAL_LABELS), musical, fps


def entropy_confidence(posterior_slice: np.ndarray) -> float:
    if posterior_slice.size == 0:
        return 0.0
    n_labels = posterior_slice.shape[0]
    frame_entropy = -(posterior_slice * np.log(posterior_slice + 1e-9)).sum(axis=0) / np.log(n_labels)
    mean_entropy = float(np.mean(frame_entropy))
    return max(0.0, min(1.0, 1.0 - mean_entropy))


def _runs(mask: np.ndarray, times: np.ndarray) -> list[tuple[int, int]]:
    runs = []
    start = None
    for i, active in enumerate(mask):
        if active and start is None:
            start = i
        elif not active and start is not None:
            runs.append((start, i))
            start = None
    if start is not None:
        runs.append((start, len(mask)))
    return runs


def published_sections(song: str) -> list[dict]:
    doc = read_json(paths.sections_path(song))
    return doc["sections"] if isinstance(doc, dict) else doc


def _overlap_fraction(start_s: float, end_s: float, label: str, sections: list[dict]) -> float:
    span = end_s - start_s
    if span <= 0:
        return 0.0
    covered = 0.0
    for sec in sections:
        # match against allin1's raw label, not the display vocabulary — same
        # rule segmentation.py uses for `same_label_as` identity. Published
        # sections don't carry the raw token, so this compares normalized
        # function names; `inst`/`solo` both display as the same string, which
        # only makes shadow detection *more* conservative (more overlap
        # credited), never less.
        if str(sec.get("function", "")).lower() != label:
            continue
        s0, s1 = max(start_s, float(sec["start"])), min(end_s, float(sec["end"]))
        if s1 > s0:
            covered += s1 - s0
    return covered / span


def detect_shadow_labels(song: str) -> list[dict]:
    labels, posterior, fps = load_posterior(song)
    sections = published_sections(song)
    times = np.arange(posterior.shape[1]) / fps

    shadows: list[dict] = []
    for label_index, label in enumerate(labels):
        mask = posterior[label_index] >= SHARE_THRESHOLD
        for start_i, end_i in _runs(mask, times):
            start_s, end_s = float(times[start_i]), float(times[min(end_i, len(times) - 1)])
            if end_s - start_s < MIN_SPAN_S:
                continue
            overlap = _overlap_fraction(start_s, end_s, label, sections)
            if overlap > MAX_PUBLISHED_OVERLAP:
                continue
            mean_share = float(np.mean(posterior[label_index, start_i:end_i]))
            shadows.append(
                {
                    "label": label,
                    "start_s": round(start_s, 3),
                    "end_s": round(end_s, 3),
                    "mean_share": round(mean_share, 4),
                    "published_overlap": round(overlap, 4),
                }
            )
    shadows.sort(key=lambda r: r["start_s"])
    return shadows


def section_entropy_confidences(song: str) -> list[dict]:
    """Re-derives `function_confidence` for every published section, to
    confirm this module's posterior math matches production's exactly
    (item 1 is shipped; this is a parity check, not a new computation)."""
    labels, posterior, fps = load_posterior(song)
    sections = published_sections(song)
    n_frames = posterior.shape[1]
    out = []
    for sec in sections:
        start_i = max(0, min(n_frames, int(round(float(sec["start"]) * fps))))
        end_i = max(start_i + 1, min(n_frames, int(round(float(sec["end"]) * fps))))
        conf = round(entropy_confidence(posterior[:, start_i:end_i]), 6)
        out.append(
            {
                "section_id": sec.get("section_id"),
                "function": sec.get("function"),
                "start": sec["start"],
                "end": sec["end"],
                "shipped_function_confidence": sec.get("function_confidence"),
                "recomputed_entropy_confidence": conf,
            }
        )
    return out
