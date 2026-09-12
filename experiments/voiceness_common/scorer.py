"""Score any voiceness candidate against three-class human-hint ground truth.

Ground truth has three classes, not two (`docs/experiments.md` "Ground truth
is three classes, not two"; the `docs/issues.md` entry that raised this — still
pending until the items 4-7 rescore runs):

    positive    `type: "vocal"` hint spans — a voice genuinely sings here.
    residual    an inferable-but-not-lead vocal construct (filtered/looped/
                sampled texture) — declared per-song in
                `vocal_ground_truth.json`, since the distinction lives only in
                hint prose and defeats keyword matching. Excluded from both
                the numerator and denominator of every scored metric; its
                firing rate is reported separately as a diagnostic only.
    negative    the operator's explicit "no vocals" (including "vocal stem
                noise" — instrument bleed with no voice at all), declared the
                same way. A hard negative: firing here is a real error.
    unknown     unreviewed time, or a hint that asserts nothing about vocal
                presence (declared "unknown" in the map, e.g. Armin's
                drop-gesture hints). Excluded entirely — neither credit nor
                error.

A hint that is neither `type: "vocal"` nor named in the map fails loud
(`ground_truth()` raises `ValueError`) — no silent fallback. Overlap between
classes (hints do overlap, e.g. on `Armin - Revolution`) resolves per frame by
precedence `positive > residual > negative > unknown`.

`evaluable` is the union of positive + residual + negative spans — the region
the operator has actually reviewed and made *some* claim about. Every scored
denominator below is restated in terms of it:

    frame_accuracy       over evaluable, non-residual frames only (positive +
                          negative). Residual and unknown frames are not
                          scored right or wrong.
    false_vocal_rate     voiced frames inside a NEGATIVE span, over evaluable
                          non-residual frames. This denominator changed from
                          "all frames" (or "all frames outside every vocal
                          span") to "evaluable, non-residual frames" — so this
                          number is NOT directly comparable with the 40.8%
                          figure quoted in `docs/product-refinement-v3.5.md`,
                          which was computed against all frames outside every
                          vocal span, unmarked time included.
    residual_firing_rate  fraction of residual frames called voiced — the
                          diagnostic the three-class rule asks for. Never
                          scored as an error or a credit.
    boundary F1 @ tol     greedy one-to-one match of every phrase start/end
                          edge to every POSITIVE-span start/end edge (target
                          edges), at +-0.25/0.5/1.0s. A predicted edge lying
                          outside `evaluable` is dropped before matching —
                          counted in neither the precision numerator nor its
                          denominator, since the operator has made no claim
                          about that instant.
    bounds/min            firing rate (predicted phrase edges per minute of
                          EVALUABLE duration, not song duration) — reported
                          beside every F1 so two candidates are compared at a
                          matched budget, never on F1 alone (CLAUDE.md
                          "matched firing budget").

Every incumbent in `incumbents.py` and every voiceness candidate (items 4-7)
plugs into this one function so all lanes land in one comparable table.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_TOLERANCES: tuple[float, ...] = (0.25, 0.5, 1.0)

VALID_CLASSES = ("residual", "negative", "unknown")

Frame = tuple[float, float | bool]
Span = tuple[float, float]

_GROUND_TRUTH_MAP_PATH = Path(__file__).resolve().parent / "vocal_ground_truth.json"


def _to_bool(value: float | bool) -> bool:
    if isinstance(value, bool):
        return value
    return float(value) >= 0.5


def _in_any_span(t: float, spans: list[Span]) -> bool:
    return any(s <= t <= e for s, e in spans)


def _merge_spans(spans: list[Span]) -> list[Span]:
    """Sorted union of possibly-overlapping/touching spans."""
    if not spans:
        return []
    ordered = sorted(spans)
    merged: list[Span] = [ordered[0]]
    for s, e in ordered[1:]:
        last_s, last_e = merged[-1]
        if s <= last_e:
            merged[-1] = (last_s, max(last_e, e))
        else:
            merged.append((s, e))
    return merged


def _span_duration(spans: list[Span]) -> float:
    return sum(e - s for s, e in spans)


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
class GroundTruth:
    """Three-class human-hint ground truth for one song, resolved to spans.

    `evaluable` is the merged/sorted union of `positive + residual +
    negative` — the region the operator has made *some* claim about. Time
    outside it is `unknown` and is never stored explicitly; it is simply
    "not in evaluable".
    """

    positive: list[Span] = field(default_factory=list)
    residual: list[Span] = field(default_factory=list)
    negative: list[Span] = field(default_factory=list)
    evaluable: list[Span] = field(default_factory=list)

    def classify(self, t: float) -> str:
        """Per-frame class at time `t`, precedence positive > residual >
        negative > unknown."""
        if _in_any_span(t, self.positive):
            return "positive"
        if _in_any_span(t, self.residual):
            return "residual"
        if _in_any_span(t, self.negative):
            return "negative"
        return "unknown"

    @property
    def evaluable_duration_s(self) -> float:
        return _span_duration(self.evaluable)


def load_class_map(path: Path | None = None) -> dict:
    """Loads the declared per-song, per-hint class map. Never guessed —
    residual/negative/unknown live only as prose in `human_hints.json` and
    defeat keyword matching, so classification is declared data (see the
    file's own `_note`)."""
    p = path or _GROUND_TRUTH_MAP_PATH
    return json.loads(p.read_text())


def ground_truth(human_hints_doc: dict, song: str, class_map: dict) -> GroundTruth:
    """Builds `GroundTruth` for `song` from `human_hints_doc` (the parsed
    `human_hints.json`) and `class_map` (the parsed `vocal_ground_truth.json`,
    or an equivalent dict for tests).

    Fails loud (`ValueError`) rather than guessing when:
    - a hint is neither `type: "vocal"` nor named in `class_map[song]`;
    - `class_map[song]` names a hint id that does not exist in the hints doc.
    No silent fallback — an unclassified hint is a defect in the map, not a
    frame to score either way.
    """
    hints = human_hints_doc.get("human_hints", [])
    song_map: dict = class_map.get(song, {})
    if not isinstance(song_map, dict):
        song_map = {}

    ids_present = {h["id"] for h in hints}
    unknown_ids = sorted(set(song_map) - ids_present)
    if unknown_ids:
        raise ValueError(
            f"vocal_ground_truth.json names hint ids not present in "
            f"{song!r}'s human_hints.json: {unknown_ids}"
        )

    positive: list[Span] = []
    residual: list[Span] = []
    negative: list[Span] = []
    unclassified: list[str] = []

    for h in hints:
        span = (float(h["start_time"]), float(h["end_time"]))
        if h.get("type") == "vocal":
            positive.append(span)
            continue
        cls = song_map.get(h["id"])
        if cls == "residual":
            residual.append(span)
        elif cls == "negative":
            negative.append(span)
        elif cls == "unknown":
            continue
        else:
            unclassified.append(h["id"])

    if unclassified:
        raise ValueError(
            f"{song!r}: hint ids are neither type: \"vocal\" nor classified in "
            f"vocal_ground_truth.json (add each to \"residual\", \"negative\" or "
            f"\"unknown\" — never guess): {sorted(unclassified)}"
        )

    evaluable = _merge_spans(positive + residual + negative)
    return GroundTruth(positive=positive, residual=residual, negative=negative, evaluable=evaluable)


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
    residual_firing_rate: float
    n_frames: int
    n_frames_evaluable: int
    n_frames_residual: int
    n_frames_unknown: int
    n_marked_spans: int  # positive (`type: "vocal"`) span count
    n_residual_spans: int
    n_negative_spans: int
    bounds_per_min: float
    n_phrase_edges: int
    n_phrase_edges_evaluable: int
    boundary: dict[float, ToleranceScore] = field(default_factory=dict)


def score(
    frames: list[Frame],
    phrases: list[dict],
    truth: GroundTruth,
    *,
    duration_s: float | None = None,
    tolerances: tuple[float, ...] = DEFAULT_TOLERANCES,
) -> ScoreResult:
    """Score one candidate's frames + derived phrases against three-class
    ground truth. See the module docstring for what each field measures and
    which denominator changed.

    `frames`   list of `(time_s, voiceness)` — voiceness a bool or a score in
               [0, 1] (thresholded at 0.5).
    `phrases`  list of `{"start", "end", ...}` dicts (the `vocal_phrase`
               blocks) — only `start`/`end` are used, as boundary edges.
    `truth`    a `GroundTruth`, from `ground_truth()`.
    `duration_s` is accepted for API symmetry with callers that already
               compute it, but `bounds_per_min` is normalized against
               `truth.evaluable_duration_s`, not `duration_s` or song
               duration.
    """
    n_frames = len(frames)
    n_frames_scored = 0  # evaluable, non-residual (positive + negative) — the
    # denominator for frame_accuracy / false_vocal_rate.
    n_frames_residual = 0
    n_frames_unknown = 0
    correct = 0
    false_vocal = 0
    residual_voiced = 0

    for t, v in frames:
        voiced = _to_bool(v)
        cls = truth.classify(float(t))
        if cls == "unknown":
            n_frames_unknown += 1
            continue
        if cls == "residual":
            n_frames_residual += 1
            if voiced:
                residual_voiced += 1
            continue
        # positive or negative: evaluable, non-residual — scored.
        n_frames_scored += 1
        truth_voiced = cls == "positive"
        if voiced == truth_voiced:
            correct += 1
        if voiced and cls == "negative":
            false_vocal += 1

    frame_accuracy = correct / n_frames_scored if n_frames_scored else 0.0
    false_vocal_rate = false_vocal / n_frames_scored if n_frames_scored else 0.0
    residual_firing_rate = residual_voiced / n_frames_residual if n_frames_residual else 0.0
    n_frames_evaluable_total = n_frames_scored + n_frames_residual

    pred_edges_raw = _phrase_edges(phrases)
    pred_edges = [e for e in pred_edges_raw if _in_any_span(e, truth.evaluable)]
    target_edges = _span_edges(truth.positive)

    evaluable_duration_s = truth.evaluable_duration_s
    minutes = evaluable_duration_s / 60.0 if evaluable_duration_s else 0.0
    # numerator and denominator must agree: evaluable edges over evaluable
    # minutes. Mixing the raw edge count with an evaluable-only denominator
    # inflates the rate on a sparsely marked song (`Cinderella - Ella Lee` is
    # 117.9 s evaluable of 339.5 s) and breaks the matched-budget comparison
    # the field exists for. The raw count stays visible as `n_phrase_edges`.
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
        residual_firing_rate=residual_firing_rate,
        n_frames=n_frames,
        n_frames_evaluable=n_frames_evaluable_total,
        n_frames_residual=n_frames_residual,
        n_frames_unknown=n_frames_unknown,
        n_marked_spans=len(truth.positive),
        n_residual_spans=len(truth.residual),
        n_negative_spans=len(truth.negative),
        bounds_per_min=bounds_per_min,
        n_phrase_edges=len(pred_edges_raw),
        n_phrase_edges_evaluable=len(pred_edges),
        boundary=boundary,
    )
