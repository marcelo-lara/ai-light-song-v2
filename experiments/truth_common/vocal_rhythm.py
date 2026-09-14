"""Vocal-rhythm family: word onset *timing* as a syllable-onset proxy for a
detector's `onsets_per_beat` / rhythm subdivision from the vocal stem. Text
is ignored entirely — a detector with wrong words and right onsets passes;
right words with late onsets fails (`docs/product-refinement-v3.6.md` item 3,
"Vocal phrases exist to give the model a song segment's rhythm, not its
words").

Trusted timing sources only, each `{"id", "line_id", "start", "end", "text",
"confidence"}` rows with `<SOL>`/`<EOL>` line-boundary tag rows mixed in:

    `Queen of Kings - Alessandra`   `reference/human/lyrics.json` — 257 words
                                     / 37 lines, 1.0-142.9s (whole song; this
                                     supersedes any narrower Moises trust
                                     window for this song).
    `_test_song`                    `reference/moises/lyrics.json` — 24 words
                                     / 5 lines, every row `confidence:
                                     "0.99"`.

Only rows with `confidence == "0.99"` count as truth (word rows only — the
`<SOL>`/`<EOL>` tag rows always carry `confidence: null` and are never
onsets, only line-edge markers).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from . import paths
from .report import CORPUS_ROW_LABEL, write_score_txt

ONSET_TOLERANCES_S: tuple[float, ...] = (0.05, 0.10)

_TAGS = {"<SOL>", "<EOL>"}

# song -> which reference/ file its trusted word timings live in
_SOURCE_FILE: dict[str, str] = {
    "Queen of Kings - Alessandra": "human",
    "_test_song": "moises",
}
SCORING_CORPUS: tuple[str, ...] = tuple(_SOURCE_FILE)


@dataclass(frozen=True)
class WordOnset:
    line_id: int
    start: float
    end: float


def _lyrics_path(song: str) -> Path:
    producer = _SOURCE_FILE[song]
    return paths.human_lyrics_path(song) if producer == "human" else paths.moises_lyrics_path(song)


def load_truth(song: str) -> list[WordOnset]:
    """Word onset rows only (`<SOL>`/`<EOL>` tags dropped), filtered to
    `confidence == "0.99"`. Fails loud if the song is in `SCORING_CORPUS`
    but the file is missing or has zero trusted word rows."""
    p = _lyrics_path(song)
    if not p.exists():
        raise FileNotFoundError(f"{song!r} is in vocal_rhythm.SCORING_CORPUS but has no {p}.")
    rows = json.loads(p.read_text())
    onsets = [
        WordOnset(line_id=int(r["line_id"]), start=float(r["start"]), end=float(r["end"]))
        for r in rows
        if r.get("text") not in _TAGS and r.get("confidence") == "0.99"
    ]
    if not onsets:
        raise ValueError(f"{song!r} is in vocal_rhythm.SCORING_CORPUS but {p} has no confidence=='0.99' word rows.")
    return sorted(onsets, key=lambda o: o.start)


def _lines(onsets: list[WordOnset]) -> list[tuple[float, float]]:
    by_line: dict[int, list[WordOnset]] = {}
    for o in onsets:
        by_line.setdefault(o.line_id, []).append(o)
    return sorted(
        (min(w.start for w in ws), max(w.end for w in ws)) for ws in by_line.values()
    )


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
class VocalRhythmScore:
    song: str
    tolerance_s: float
    n_truth_onsets: int
    n_predicted_onsets: int
    matched: int
    precision: float | None
    recall: float | None
    f1: float
    truth_onsets_per_sec: float
    predicted_onsets_per_sec: float
    n_truth_phrase_edges: int
    n_predicted_phrase_edges: int
    phrase_edge_matched: int
    phrase_edge_f1: float


def score_vocal_rhythm(
    song: str,
    predicted_onsets: list[float],
    predicted_phrases: list[dict],
    *,
    truth: list[WordOnset] | None = None,
    tolerances: tuple[float, ...] = ONSET_TOLERANCES_S,
) -> list[VocalRhythmScore]:
    """`predicted_onsets`: flat list of onset times (seconds). `predicted_
    phrases`: `[{"start": float, "end": float}, ...]` — phrase edges, scored
    at the coarser +-1.0s tolerance shared by the other span families."""
    truth_rows = truth if truth is not None else load_truth(song)
    truth_times = [o.start for o in truth_rows]
    truth_lines = _lines(truth_rows)
    truth_edges = sorted(e for s, e in truth_lines for e in (s, e))
    pred_edges = sorted(float(v) for p in predicted_phrases for v in (p["start"], p["end"]))

    duration = (max(o.end for o in truth_rows) - min(o.start for o in truth_rows)) or 1.0
    pred_sorted = sorted(predicted_onsets)

    out: list[VocalRhythmScore] = []
    for tol in tolerances:
        matched = _greedy_match(pred_sorted, truth_times, tol)
        precision = matched / len(pred_sorted) if pred_sorted else None
        recall = matched / len(truth_times) if truth_times else None
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision is not None and recall is not None and (precision + recall) > 0
            else 0.0
        )
        edge_matched = _greedy_match(pred_edges, truth_edges, 1.0)
        edge_precision = edge_matched / len(pred_edges) if pred_edges else None
        edge_recall = edge_matched / len(truth_edges) if truth_edges else None
        edge_f1 = (
            2 * edge_precision * edge_recall / (edge_precision + edge_recall)
            if edge_precision is not None and edge_recall is not None and (edge_precision + edge_recall) > 0
            else 0.0
        )
        out.append(
            VocalRhythmScore(
                song=song,
                tolerance_s=tol,
                n_truth_onsets=len(truth_times),
                n_predicted_onsets=len(pred_sorted),
                matched=matched,
                precision=precision,
                recall=recall,
                f1=round(f1, 4),
                truth_onsets_per_sec=round(len(truth_times) / duration, 4),
                predicted_onsets_per_sec=round(len(pred_sorted) / duration, 4),
                n_truth_phrase_edges=len(truth_edges),
                n_predicted_phrase_edges=len(pred_edges),
                phrase_edge_matched=edge_matched,
                phrase_edge_f1=round(edge_f1, 4),
            )
        )
    return out


COLUMNS = [
    "song",
    "tolerance_s",
    "n_truth_onsets",
    "n_predicted_onsets",
    "matched",
    "precision",
    "recall",
    "f1",
    "truth_onsets_per_sec",
    "predicted_onsets_per_sec",
    "n_truth_phrase_edges",
    "n_predicted_phrase_edges",
    "phrase_edge_matched",
    "phrase_edge_f1",
]


def _row(s: VocalRhythmScore) -> dict:
    return {
        "song": s.song,
        "tolerance_s": s.tolerance_s,
        "n_truth_onsets": s.n_truth_onsets,
        "n_predicted_onsets": s.n_predicted_onsets,
        "matched": s.matched,
        "precision": s.precision,
        "recall": s.recall,
        "f1": s.f1,
        "truth_onsets_per_sec": s.truth_onsets_per_sec,
        "predicted_onsets_per_sec": s.predicted_onsets_per_sec,
        "n_truth_phrase_edges": s.n_truth_phrase_edges,
        "n_predicted_phrase_edges": s.n_predicted_phrase_edges,
        "phrase_edge_matched": s.phrase_edge_matched,
        "phrase_edge_f1": s.phrase_edge_f1,
    }


def corpus_row(scores: list[VocalRhythmScore], *, tolerance_s: float) -> dict | None:
    subset = [s for s in scores if s.tolerance_s == tolerance_s]
    if not subset:
        return None
    total_matched = sum(s.matched for s in subset)
    total_pred = sum(s.n_predicted_onsets for s in subset)
    total_truth = sum(s.n_truth_onsets for s in subset)
    precision = total_matched / total_pred if total_pred else None
    recall = total_matched / total_truth if total_truth else None
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision is not None and recall is not None and (precision + recall) > 0
        else 0.0
    )
    edge_matched = sum(s.phrase_edge_matched for s in subset)
    edge_pred = sum(s.n_predicted_phrase_edges for s in subset)
    edge_truth = sum(s.n_truth_phrase_edges for s in subset)
    edge_p = edge_matched / edge_pred if edge_pred else None
    edge_r = edge_matched / edge_truth if edge_truth else None
    edge_f1 = (
        2 * edge_p * edge_r / (edge_p + edge_r) if edge_p is not None and edge_r is not None and (edge_p + edge_r) > 0 else 0.0
    )
    return {
        "song": CORPUS_ROW_LABEL,
        "tolerance_s": tolerance_s,
        "n_truth_onsets": total_truth,
        "n_predicted_onsets": total_pred,
        "matched": total_matched,
        "precision": precision,
        "recall": recall,
        "f1": round(f1, 4),
        "truth_onsets_per_sec": None,
        "predicted_onsets_per_sec": None,
        "n_truth_phrase_edges": edge_truth,
        "n_predicted_phrase_edges": edge_pred,
        "phrase_edge_matched": edge_matched,
        "phrase_edge_f1": round(edge_f1, 4),
    }


def write_report(path: Path, per_song_scores: list[list[VocalRhythmScore]]) -> None:
    flat = [s for song_scores in per_song_scores for s in song_scores]
    rows = [_row(s) for s in flat]
    for tol in ONSET_TOLERANCES_S:
        row = corpus_row(flat, tolerance_s=tol)
        if row is not None:
            rows.append(row)
    write_score_txt(path, COLUMNS, rows)
