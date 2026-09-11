"""Score any voiceness candidate against `type: "vocal"` human-hint spans.

    frame voiceness accuracy   fraction of 50ms frames whose voiced/unvoiced
                                call matches the marked spans.
    false-vocal rate           fraction of ALL frames called voiced OUTSIDE
                                every marked span (not a fraction of the voiced
                                subset — this is the quantity measured as
                                40.8% on `ayuni` in the refinement doc).
    boundary F1 @ tol          greedy one-to-one match of every phrase
                                start/end edge to every marked-span start/end
                                edge, at +-0.25/0.5/1.0 s.
    bounds/min                 firing rate (predicted phrase edges per minute
                                of song) — reported beside every F1 so two
                                candidates are compared at a matched budget,
                                never on F1 alone (CLAUDE.md "matched firing
                                budget").

Every incumbent in `incumbents.py` and every future candidate (items 4-7)
plugs into this one function so the four lanes land in one comparable table.
"""
from __future__ import annotations

from dataclasses import dataclass, field

DEFAULT_TOLERANCES: tuple[float, ...] = (0.25, 0.5, 1.0)

Frame = tuple[float, float | bool]
Span = tuple[float, float]


def _to_bool(value: float | bool) -> bool:
    if isinstance(value, bool):
        return value
    return float(value) >= 0.5


def _in_any_span(t: float, spans: list[Span]) -> bool:
    return any(s <= t <= e for s, e in spans)


def _phrase_edges(phrases: list[dict]) -> list[float]:
    edges: list[float] = []
    for p in phrases:
        edges.append(float(p["start"]))
        edges.append(float(p["end"]))
    return sorted(edges)


def _span_edges(spans: list[Span]) -> list[float]:
    edges: list[float] = []
    for s, e in spans:
        edges.append(float(s))
        edges.append(float(e))
    return sorted(edges)


def _greedy_match_count(pred_edges: list[float], target_edges: list[float], tol: float) -> int:
    """Greedy one-to-one match: each target claims its closest still-free
    predicted edge within `tol`, closest target processed... order doesn't
    change the count for edge lists that don't share ties across targets in
    practice, so a simple nearest-available pass is enough here."""
    used = [False] * len(pred_edges)
    matched = 0
    for t in sorted(target_edges):
        best_i, best_d = None, tol
        for i, p in enumerate(pred_edges):
            if used[i]:
                continue
            d = abs(p - t)
            if d <= best_d:
                best_i, best_d = i, d
        if best_i is not None:
            used[best_i] = True
            matched += 1
    return matched


@dataclass
class ToleranceScore:
    tolerance_s: float
    precision: float
    recall: float
    f1: float


@dataclass
class ScoreResult:
    frame_accuracy: float
    false_vocal_rate: float
    n_frames: int
    n_marked_spans: int
    bounds_per_min: float
    n_phrase_edges: int
    boundary: dict[float, ToleranceScore] = field(default_factory=dict)


def score(
    frames: list[Frame],
    phrases: list[dict],
    marked_spans: list[Span],
    *,
    duration_s: float | None = None,
    tolerances: tuple[float, ...] = DEFAULT_TOLERANCES,
) -> ScoreResult:
    """Score one candidate's frames + derived phrases against ground truth.

    `frames`   list of `(time_s, voiceness)` — voiceness a bool or a score in
               [0, 1] (thresholded at 0.5).
    `phrases`  list of `{"start", "end", ...}` dicts (the `vocal_phrase`
               blocks) — only `start`/`end` are used, as boundary edges.
    `marked_spans` list of `(start, end)` — `type: "vocal"` hint spans.
    """
    spans = [(float(s), float(e)) for s, e in marked_spans]

    n_frames = len(frames)
    if n_frames == 0:
        frame_accuracy = 0.0
        false_vocal_rate = 0.0
    else:
        correct = 0
        false_vocal = 0
        for t, v in frames:
            voiced = _to_bool(v)
            truth = _in_any_span(float(t), spans)
            if voiced == truth:
                correct += 1
            if voiced and not truth:
                false_vocal += 1
        frame_accuracy = correct / n_frames
        false_vocal_rate = false_vocal / n_frames

    pred_edges = _phrase_edges(phrases)
    target_edges = _span_edges(spans)

    if duration_s is None:
        duration_s = max((t for t, _ in frames), default=0.0)
    minutes = duration_s / 60.0 if duration_s else 0.0
    bounds_per_min = len(pred_edges) / minutes if minutes > 0 else 0.0

    boundary: dict[float, ToleranceScore] = {}
    for tol in tolerances:
        matched = _greedy_match_count(pred_edges, target_edges, tol)
        precision = matched / len(pred_edges) if pred_edges else 0.0
        recall = matched / len(target_edges) if target_edges else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
        boundary[tol] = ToleranceScore(tolerance_s=tol, precision=precision, recall=recall, f1=f1)

    return ScoreResult(
        frame_accuracy=frame_accuracy,
        false_vocal_rate=false_vocal_rate,
        n_frames=n_frames,
        n_marked_spans=len(spans),
        bounds_per_min=bounds_per_min,
        n_phrase_edges=len(pred_edges),
        boundary=boundary,
    )


def marked_vocal_spans(human_hints_doc: dict) -> list[Span]:
    """Filter `human_hints.json`'s rows to `type == "vocal"` only — never
    `"hint"` or `"review"`."""
    out: list[Span] = []
    for h in human_hints_doc.get("human_hints", []):
        if h.get("type") != "vocal":
            continue
        out.append((float(h["start_time"]), float(h["end_time"])))
    return out
