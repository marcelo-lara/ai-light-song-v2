"""Energy/tension family: 1-5 scale, scored exact-match and +-1 tolerance.

Truth has two sources, same as every field plan item 6 seeds:

    human   `reference/human/segments.json` rows carrying `energy`/`tension`
            — the operator's own ratings. As of 2026-09-14 there are 2:
            `Cinderella - Ella Lee` Intro, `_test_song` Refrain.
    seed    `reference/human/segments.seed.json` — written by plan item 4,
            **does not exist yet**. Every row scored against a seed carries
            `provisional: true` in the output (item 2's seed/incumbent
            circularity rule: seeds share method with candidate producers, so
            a producer cannot be archived on a seed-only loss). A missing
            seed file produces zero seed rows, not a crash and not a silent
            fallback to a guess — this is an explicitly sanctioned "not built
            yet" gap.

Corpus: the 4 segment songs carry `segments.json` (`docs/product-
refinement-v3.6.md` item 2); seeds land on the same 4 first (item 6), then
all 23 (item 7). This module always reads whichever of the two files exist
for a song — it does not hardcode which songs currently have ratings, since
that grows over time; `SCORING_CORPUS` here names the *segmented* songs
eligible to carry either source.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from . import paths
from .report import CORPUS_ROW_LABEL, write_score_txt

# Same 4 songs as structure.SCORING_CORPUS — the ones with a segments.json at all.
SCORING_CORPUS: tuple[str, ...] = (
    "ayuni",
    "Cinderella - Ella Lee",
    "_test_song",
    "What a Feeling - Courtney Storm",
)

FIELDS: tuple[str, ...] = ("energy", "tension")


@dataclass(frozen=True)
class RatedSegment:
    song: str
    start: float
    end: float
    energy: int | None
    tension: int | None
    source: str  # "human" | "seed"
    provisional: bool


def load_truth(song: str) -> list[RatedSegment]:
    """Human rows (only where `energy`/`tension` is actually set — most
    `segments.json` rows carry neither today) plus seed rows if
    `segments.seed.json` exists. Raises if `segments.json` itself is
    missing for a `SCORING_CORPUS` song (that file is required by the
    corpus definition); a missing *seed* file is not an error."""
    human_path = paths.human_segments_path(song)
    if not human_path.exists():
        raise FileNotFoundError(
            f"{song!r} is in energy_tension.SCORING_CORPUS but has no {human_path}."
        )
    rows: list[RatedSegment] = []
    for r in json.loads(human_path.read_text()):
        energy = r.get("energy")
        tension = r.get("tension")
        if energy is None and tension is None:
            continue
        rows.append(
            RatedSegment(
                song=song,
                start=float(r["start"]),
                end=float(r["end"]),
                energy=energy,
                tension=tension,
                source="human",
                provisional=False,
            )
        )

    seed_path = paths.human_segments_seed_path(song)
    if seed_path.exists():
        for r in json.loads(seed_path.read_text()):
            rows.append(
                RatedSegment(
                    song=song,
                    start=float(r["start"]),
                    end=float(r["end"]),
                    energy=r.get("energy"),
                    tension=r.get("tension"),
                    source="seed",
                    provisional=True,
                )
            )
    # else: item 4 has not written this song's seed yet — no seed rows, not
    # a crash and not a guess.
    return rows


def _find_predicted(predicted: list[dict], start: float, end: float) -> dict | None:
    """Predicted row whose span contains the truth segment's start, or
    (falling back) whose start is nearest. No time-grid resampling here —
    both sides are already segment-shaped."""
    for r in predicted:
        if float(r["start"]) <= start < float(r["end"]):
            return r
    if not predicted:
        return None
    return min(predicted, key=lambda r: abs(float(r["start"]) - start))


@dataclass
class FieldScore:
    song: str
    field: str
    source: str
    provisional: bool
    n: int
    exact_match: int
    within_1: int
    exact_accuracy: float | None
    within_1_accuracy: float | None


def score_energy_tension(
    song: str,
    predicted: list[dict],
    *,
    truth: list[RatedSegment] | None = None,
) -> list[FieldScore]:
    """`predicted`: `[{"start": float, "end": float, "energy": int|None,
    "tension": int|None}, ...]`. Returns one `FieldScore` per
    (field, source) combination present in truth — human and seed are never
    pooled, since seed rows are provisional."""
    truth_rows = truth if truth is not None else load_truth(song)
    out: list[FieldScore] = []
    for source in ("human", "seed"):
        source_rows = [r for r in truth_rows if r.source == source]
        for field in FIELDS:
            rated = [r for r in source_rows if getattr(r, field) is not None]
            if not rated:
                continue
            exact = within1 = 0
            for r in rated:
                pred = _find_predicted(predicted, r.start, r.end)
                pred_value = pred.get(field) if pred else None
                truth_value = getattr(r, field)
                if pred_value is None:
                    continue
                if int(pred_value) == int(truth_value):
                    exact += 1
                if abs(int(pred_value) - int(truth_value)) <= 1:
                    within1 += 1
            out.append(
                FieldScore(
                    song=song,
                    field=field,
                    source=source,
                    provisional=(source == "seed"),
                    n=len(rated),
                    exact_match=exact,
                    within_1=within1,
                    exact_accuracy=exact / len(rated) if rated else None,
                    within_1_accuracy=within1 / len(rated) if rated else None,
                )
            )
    return out


COLUMNS = [
    "song",
    "field",
    "source",
    "provisional",
    "n",
    "exact_match",
    "within_1",
    "exact_accuracy",
    "within_1_accuracy",
]


def _row(s: FieldScore) -> dict:
    return {
        "song": s.song,
        "field": s.field,
        "source": s.source,
        "provisional": s.provisional,
        "n": s.n,
        "exact_match": s.exact_match,
        "within_1": s.within_1,
        "exact_accuracy": s.exact_accuracy,
        "within_1_accuracy": s.within_1_accuracy,
    }


def corpus_row(scores: list[FieldScore], *, field: str, source: str) -> dict | None:
    subset = [s for s in scores if s.field == field and s.source == source]
    if not subset:
        return None
    total_n = sum(s.n for s in subset)
    total_exact = sum(s.exact_match for s in subset)
    total_within1 = sum(s.within_1 for s in subset)
    return {
        "song": CORPUS_ROW_LABEL,
        "field": field,
        "source": source,
        "provisional": source == "seed",
        "n": total_n,
        "exact_match": total_exact,
        "within_1": total_within1,
        "exact_accuracy": total_exact / total_n if total_n else None,
        "within_1_accuracy": total_within1 / total_n if total_n else None,
    }


def write_report(path: Path, per_song_scores: list[list[FieldScore]]) -> None:
    flat = [s for song_scores in per_song_scores for s in song_scores]
    rows = [_row(s) for s in flat]
    for field in FIELDS:
        for source in ("human", "seed"):
            row = corpus_row(flat, field=field, source=source)
            if row is not None:
                rows.append(row)
    write_score_txt(path, COLUMNS, rows)
