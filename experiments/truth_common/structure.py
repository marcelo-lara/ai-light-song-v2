"""Structure family: boundary F1 (+-1.0s) and label agreement against
`reference/human/segments.json`, using `docs/segments-vocabulary.md` as the
label vocabulary.

**Circularity rule (`docs/product-refinement-v3.6.md` item 2).** On these 4
songs, `src/analyzer/stages/ui_data.py` rebuilds the published `sections.json`
*from* `reference/human/segments.json` at confidence 0.8 — scoring a
producer's boundaries against `sections.json` on these songs would grade the
truth against itself. Score a producer's own raw output (an allin1 artifact,
an experiment's proposal file) instead. This module never reads
`sections.json` and callers must not pass it in either.

Boundary matching reuses the same sequential greedy nearest-boundary walk
`src/analyzer/stages/validation/sections.py::_validate_human_segments`
already uses against this same file (both boundary lists pre-sorted
ascending; matched greedily by scanning both in order) — not re-derived here.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from . import paths
from .report import CORPUS_ROW_LABEL, write_score_txt

BOUNDARY_TOLERANCE_S = 1.0

# ayuni 16, Cinderella 20, _test_song 8, What a Feeling 9 (checked 2026-09-14)
SCORING_CORPUS: tuple[str, ...] = (
    "ayuni",
    "Cinderella - Ella Lee",
    "_test_song",
    "What a Feeling - Courtney Storm",
)

_VOCAB_PATH = Path(__file__).resolve().parents[2] / "docs" / "segments-vocabulary.md"
_VOCAB_TERM_RE = re.compile(r"\*\*([A-Za-z][A-Za-z /()\-]*?)\*\*\s*(?:/[^—]*?)?\s*—")


def load_label_vocabulary(path: Path | None = None) -> set[str]:
    """Canonical section-label terms from `docs/segments-vocabulary.md`,
    lower-cased. Used only to flag a predicted label that is outside the
    vocabulary — it never gates matching, since a producer may spell a label
    slightly differently and that is a labeling defect to report, not a
    reason to silently drop the boundary."""
    text = (path or _VOCAB_PATH).read_text()
    terms: set[str] = set()
    for match in _VOCAB_TERM_RE.finditer(text):
        for term in match.group(1).split("/"):
            terms.add(term.strip().lower())
    return terms


@dataclass(frozen=True)
class TruthBoundary:
    time: float
    label: str


def load_truth(song: str) -> list[TruthBoundary]:
    """`reference/human/segments.json` rows, boundaries only (row 0's start
    is the song start, not a boundary — matches
    `validation/sections.py::_validate_human_segments`'s own `[1:]` slice).
    Fails loud if the song is in `SCORING_CORPUS` but the file is absent —
    that is a corpus-declaration bug, not a skippable gap."""
    p = paths.human_segments_path(song)
    if not p.exists():
        raise FileNotFoundError(
            f"{song!r} is in structure.SCORING_CORPUS but has no {p} — "
            f"fix the corpus list or add the file, never skip silently."
        )
    rows = json.loads(p.read_text())
    return [TruthBoundary(time=float(r["start"]), label=str(r.get("label", ""))) for r in rows[1:]]


@dataclass
class StructureScore:
    song: str
    n_truth: int
    n_predicted: int
    matched: int
    precision: float | None
    recall: float | None
    f1: float
    label_matches: int
    label_accuracy: float | None
    out_of_vocab_predicted: int


def _greedy_sequential_match(
    predicted: list[float], truth: list[float], tolerance: float
) -> list[tuple[int, int]]:
    """Ported unchanged (algorithm, not code) from
    `validation/sections.py::_validate_human_segments`: walk both
    ascending-sorted sequences in lockstep, consuming whichever side is
    earlier when neither matches."""
    matches: list[tuple[int, int]] = []
    pi = ti = 0
    while pi < len(predicted) and ti < len(truth):
        delta = predicted[pi] - truth[ti]
        if abs(delta) <= tolerance:
            matches.append((pi, ti))
            pi += 1
            ti += 1
            continue
        if predicted[pi] < truth[ti]:
            pi += 1
        else:
            ti += 1
    return matches


def score_structure(
    song: str,
    predicted: list[dict],
    *,
    truth: list[TruthBoundary] | None = None,
    tolerance: float = BOUNDARY_TOLERANCE_S,
    vocabulary: set[str] | None = None,
) -> StructureScore:
    """`predicted`: `[{"time": float, "label": str | None}, ...]`, any
    producer's raw boundary output — never the published `sections.json` on
    a `SCORING_CORPUS` song (circularity rule, module docstring)."""
    truth_rows = truth if truth is not None else load_truth(song)
    vocab = vocabulary if vocabulary is not None else load_label_vocabulary()

    pred_sorted = sorted(predicted, key=lambda r: float(r["time"]))
    pred_times = [float(r["time"]) for r in pred_sorted]
    truth_times = [t.time for t in truth_rows]

    matches = _greedy_sequential_match(pred_times, truth_times, tolerance)
    matched = len(matches)
    precision = matched / len(pred_sorted) if pred_sorted else None
    recall = matched / len(truth_rows) if truth_rows else None
    if precision is not None and recall is not None and (precision + recall) > 0:
        f1 = 2 * precision * recall / (precision + recall)
    else:
        f1 = 0.0

    label_matches = 0
    for pi, ti in matches:
        pred_label = str(pred_sorted[pi].get("label") or "").strip().lower()
        truth_label = truth_rows[ti].label.strip().lower()
        if pred_label and pred_label == truth_label:
            label_matches += 1
    label_accuracy = label_matches / matched if matched else None

    out_of_vocab = sum(
        1
        for r in pred_sorted
        if str(r.get("label") or "").strip().lower() not in vocab and r.get("label")
    )

    return StructureScore(
        song=song,
        n_truth=len(truth_rows),
        n_predicted=len(pred_sorted),
        matched=matched,
        precision=precision,
        recall=recall,
        f1=round(f1, 4),
        label_matches=label_matches,
        label_accuracy=label_accuracy,
        out_of_vocab_predicted=out_of_vocab,
    )


COLUMNS = [
    "song",
    "n_truth",
    "n_predicted",
    "matched",
    "precision",
    "recall",
    "f1",
    "label_matches",
    "label_accuracy",
    "out_of_vocab_predicted",
]


def _row(s: StructureScore) -> dict:
    return {
        "song": s.song,
        "n_truth": s.n_truth,
        "n_predicted": s.n_predicted,
        "matched": s.matched,
        "precision": s.precision,
        "recall": s.recall,
        "f1": s.f1,
        "label_matches": s.label_matches,
        "label_accuracy": s.label_accuracy,
        "out_of_vocab_predicted": s.out_of_vocab_predicted,
    }


def corpus_row(scores: list[StructureScore]) -> dict:
    """Micro-averaged corpus row: precision/recall/F1 over pooled counts
    (never a mean of per-song F1s, which double-counts short songs)."""
    total_matched = sum(s.matched for s in scores)
    total_pred = sum(s.n_predicted for s in scores)
    total_truth = sum(s.n_truth for s in scores)
    precision = total_matched / total_pred if total_pred else None
    recall = total_matched / total_truth if total_truth else None
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision is not None and recall is not None and (precision + recall) > 0
        else 0.0
    )
    total_label_matches = sum(s.label_matches for s in scores)
    label_accuracy = total_label_matches / total_matched if total_matched else None
    return {
        "song": CORPUS_ROW_LABEL,
        "n_truth": total_truth,
        "n_predicted": total_pred,
        "matched": total_matched,
        "precision": precision,
        "recall": recall,
        "f1": round(f1, 4),
        "label_matches": total_label_matches,
        "label_accuracy": label_accuracy,
        "out_of_vocab_predicted": sum(s.out_of_vocab_predicted for s in scores),
    }


def write_report(path: Path, scores: list[StructureScore]) -> None:
    rows = [_row(s) for s in scores] + [corpus_row(scores)]
    write_score_txt(path, COLUMNS, rows)
