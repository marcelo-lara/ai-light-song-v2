"""Texture/character family: untyped, non-drop human hints (character blocks
like Armin's hand-marked "Breath - vocal, no intense section" — texture, not
verse/chorus arrangement; `docs/experiments.md`,
`character-blocks-not-just-arrangement` memory).

A hint counts as texture ground truth when it is NOT `type: "vocal"` and its
title is not one of the 5 `drop_stages` stage titles. No further filtering —
checked against the corpus counts in `docs/product-refinement-v3.6.md` item 2
(`Queen of Kings` 16, `ayuni` 11, `Cinderella` 8, `_test_song` 8, verified
2026-09-14 including a placeholder-titled hint such as Cinderella's
"Hint 13", which the count table does include).

Scored as boundary F1 (start/end edges, same tolerance as `structure.py`) —
texture blocks are spans, and what an authoring model needs is "does a
texture change land here", not a label match (titles are free text, not a
controlled vocabulary like section labels).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from . import paths
from .drop_stages import STAGE_TITLES
from .report import CORPUS_ROW_LABEL, write_score_txt

BOUNDARY_TOLERANCE_S = 1.0

# Queen of Kings 16, ayuni 11, Cinderella 8, _test_song 8 (checked 2026-09-14)
SCORING_CORPUS: tuple[str, ...] = (
    "Queen of Kings - Alessandra",
    "ayuni",
    "Cinderella - Ella Lee",
    "_test_song",
)


@dataclass(frozen=True)
class TextureSpan:
    start: float
    end: float
    title: str


def load_truth(song: str) -> list[TextureSpan]:
    p = paths.human_hints_path(song)
    if not p.exists():
        raise FileNotFoundError(f"{song!r} is in texture.SCORING_CORPUS but has no {p}.")
    doc = json.loads(p.read_text())
    spans: list[TextureSpan] = []
    for h in doc.get("human_hints", []):
        if h.get("type") == "vocal":
            continue
        title = str(h.get("title", "")).strip()
        if not title or title.lower() in STAGE_TITLES:
            continue
        spans.append(TextureSpan(start=float(h["start_time"]), end=float(h["end_time"]), title=title))
    if not spans:
        raise ValueError(f"{song!r} is in texture.SCORING_CORPUS but has no texture hints.")
    return sorted(spans, key=lambda s: s.start)


def _edges(spans_or_dicts, start_key="start", end_key="end") -> list[float]:
    edges: list[float] = []
    for s in spans_or_dicts:
        if isinstance(s, dict):
            edges.append(float(s[start_key]))
            edges.append(float(s[end_key]))
        else:
            edges.append(s.start)
            edges.append(s.end)
    return sorted(edges)


def _greedy_match(predicted: list[float], truth: list[float], tolerance: float) -> int:
    candidates = []
    for pi, pt in enumerate(predicted):
        for ti, tt in enumerate(truth):
            d = abs(pt - tt)
            if d <= tolerance:
                candidates.append((d, pi, ti))
    candidates.sort()
    used_p, used_t = set(), set()
    matched = 0
    for _, pi, ti in candidates:
        if pi in used_p or ti in used_t:
            continue
        used_p.add(pi)
        used_t.add(ti)
        matched += 1
    return matched


@dataclass
class TextureScore:
    song: str
    n_truth_edges: int
    n_predicted_edges: int
    matched: int
    precision: float | None
    recall: float | None
    f1: float


def score_texture(
    song: str,
    predicted: list[dict],
    *,
    truth: list[TextureSpan] | None = None,
    tolerance: float = BOUNDARY_TOLERANCE_S,
) -> TextureScore:
    """`predicted`: `[{"start": float, "end": float}, ...]` texture-block
    proposals."""
    truth_rows = truth if truth is not None else load_truth(song)
    truth_edges = _edges(truth_rows)
    pred_edges = _edges(predicted)
    matched = _greedy_match(pred_edges, truth_edges, tolerance)
    precision = matched / len(pred_edges) if pred_edges else None
    recall = matched / len(truth_edges) if truth_edges else None
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision is not None and recall is not None and (precision + recall) > 0
        else 0.0
    )
    return TextureScore(
        song=song,
        n_truth_edges=len(truth_edges),
        n_predicted_edges=len(pred_edges),
        matched=matched,
        precision=precision,
        recall=recall,
        f1=round(f1, 4),
    )


COLUMNS = ["song", "n_truth_edges", "n_predicted_edges", "matched", "precision", "recall", "f1"]


def _row(s: TextureScore) -> dict:
    return {
        "song": s.song,
        "n_truth_edges": s.n_truth_edges,
        "n_predicted_edges": s.n_predicted_edges,
        "matched": s.matched,
        "precision": s.precision,
        "recall": s.recall,
        "f1": s.f1,
    }


def corpus_row(scores: list[TextureScore]) -> dict:
    total_matched = sum(s.matched for s in scores)
    total_pred = sum(s.n_predicted_edges for s in scores)
    total_truth = sum(s.n_truth_edges for s in scores)
    precision = total_matched / total_pred if total_pred else None
    recall = total_matched / total_truth if total_truth else None
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision is not None and recall is not None and (precision + recall) > 0
        else 0.0
    )
    return {
        "song": CORPUS_ROW_LABEL,
        "n_truth_edges": total_truth,
        "n_predicted_edges": total_pred,
        "matched": total_matched,
        "precision": precision,
        "recall": recall,
        "f1": round(f1, 4),
    }


def write_report(path: Path, scores: list[TextureScore]) -> None:
    rows = [_row(s) for s in scores] + [corpus_row(scores)]
    write_score_txt(path, COLUMNS, rows)
