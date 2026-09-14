"""Rhythm family: per-source (`drums`/`bass`/`harmonic`/`vocals`) dominant
subdivision relative to the beat grid, exact match only.

Vocabulary: `half`, `quarter`, `eighth`, `sixteenth`, `eighth_triplet`,
`none` (`docs/product-refinement-v3.6.md` item 6's `rhythm` field shape —
this scorer measures against the same vocabulary the publish stage will use).

Truth sources and the seed/provisional rule are identical to
`energy_tension.py` — see that module's docstring for the full explanation.
`segments.json` does not carry `rhythm` today (only `energy`/`tension`), so
until item 6 seeds land, `SCORING_CORPUS` songs contribute zero human rows
and zero seed rows here — this module still runs, produces an empty (but not
crashing) report, honestly reflecting "no rhythm truth exists yet".
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from . import paths
from .report import CORPUS_ROW_LABEL, write_score_txt

SOURCES: tuple[str, ...] = ("drums", "bass", "harmonic", "vocals")
SUBDIVISIONS: frozenset[str] = frozenset(
    {"half", "quarter", "eighth", "sixteenth", "eighth_triplet", "none"}
)

# Same 4 songs as structure.SCORING_CORPUS / energy_tension.SCORING_CORPUS.
SCORING_CORPUS: tuple[str, ...] = (
    "ayuni",
    "Cinderella - Ella Lee",
    "_test_song",
    "What a Feeling - Courtney Storm",
)


@dataclass(frozen=True)
class RhythmSegment:
    song: str
    start: float
    end: float
    subdivisions: dict  # {source: subdivision_str}
    source: str  # "human" | "seed" — which truth file this row came from
    provisional: bool


def _validate_subdivisions(subdivisions: dict, where: str) -> dict:
    for src, value in subdivisions.items():
        if src not in SOURCES:
            raise ValueError(f"{where}: unknown rhythm source {src!r} (expected one of {SOURCES})")
        if value not in SUBDIVISIONS:
            raise ValueError(f"{where}: unknown subdivision {value!r} (expected one of {sorted(SUBDIVISIONS)})")
    return subdivisions


def load_truth(song: str) -> list[RhythmSegment]:
    """Human rows: `segments.json` rows carrying a `rhythm` object (none do
    today — see module docstring). Seed rows: `segments.seed.json` if it
    exists, else none (not a crash, not a guess)."""
    human_path = paths.human_segments_path(song)
    if not human_path.exists():
        raise FileNotFoundError(f"{song!r} is in rhythm.SCORING_CORPUS but has no {human_path}.")
    rows: list[RhythmSegment] = []
    for r in json.loads(human_path.read_text()):
        rhythm = r.get("rhythm")
        if not rhythm:
            continue
        rows.append(
            RhythmSegment(
                song=song,
                start=float(r["start"]),
                end=float(r["end"]),
                subdivisions=_validate_subdivisions(rhythm, f"{song} human segments.json"),
                source="human",
                provisional=False,
            )
        )

    seed_path = paths.human_segments_seed_path(song)
    if seed_path.exists():
        for r in json.loads(seed_path.read_text()):
            rhythm = r.get("rhythm")
            if not rhythm:
                continue
            rows.append(
                RhythmSegment(
                    song=song,
                    start=float(r["start"]),
                    end=float(r["end"]),
                    subdivisions=_validate_subdivisions(rhythm, f"{song} segments.seed.json"),
                    source="seed",
                    provisional=True,
                )
            )
    return rows


def _find_predicted(predicted: list[dict], start: float) -> dict | None:
    for r in predicted:
        if float(r["start"]) <= start < float(r["end"]):
            return r
    if not predicted:
        return None
    return min(predicted, key=lambda r: abs(float(r["start"]) - start))


@dataclass
class SourceScore:
    song: str
    source: str  # drums/bass/harmonic/vocals
    truth_origin: str  # "human" | "seed"
    provisional: bool
    n: int
    exact_match: int
    accuracy: float | None


def score_rhythm(
    song: str,
    predicted: list[dict],
    *,
    truth: list[RhythmSegment] | None = None,
) -> list[SourceScore]:
    """`predicted`: `[{"start": float, "end": float, "subdivisions": {source:
    value}}, ...]`."""
    truth_rows = truth if truth is not None else load_truth(song)
    out: list[SourceScore] = []
    for truth_origin in ("human", "seed"):
        origin_rows = [r for r in truth_rows if r.source == truth_origin]
        for source in SOURCES:
            rated = [r for r in origin_rows if source in r.subdivisions]
            if not rated:
                continue
            exact = 0
            for r in rated:
                pred = _find_predicted(predicted, r.start)
                pred_subdivisions = (pred or {}).get("subdivisions", {})
                pred_value = pred_subdivisions.get(source)
                if pred_value == r.subdivisions[source]:
                    exact += 1
            out.append(
                SourceScore(
                    song=song,
                    source=source,
                    truth_origin=truth_origin,
                    provisional=(truth_origin == "seed"),
                    n=len(rated),
                    exact_match=exact,
                    accuracy=exact / len(rated) if rated else None,
                )
            )
    return out


COLUMNS = ["song", "source", "truth_origin", "provisional", "n", "exact_match", "accuracy"]


def _row(s: SourceScore) -> dict:
    return {
        "song": s.song,
        "source": s.source,
        "truth_origin": s.truth_origin,
        "provisional": s.provisional,
        "n": s.n,
        "exact_match": s.exact_match,
        "accuracy": s.accuracy,
    }


def corpus_row(scores: list[SourceScore], *, source: str, truth_origin: str) -> dict | None:
    subset = [s for s in scores if s.source == source and s.truth_origin == truth_origin]
    if not subset:
        return None
    total_n = sum(s.n for s in subset)
    total_exact = sum(s.exact_match for s in subset)
    return {
        "song": CORPUS_ROW_LABEL,
        "source": source,
        "truth_origin": truth_origin,
        "provisional": truth_origin == "seed",
        "n": total_n,
        "exact_match": total_exact,
        "accuracy": total_exact / total_n if total_n else None,
    }


def write_report(path: Path, per_song_scores: list[list[SourceScore]]) -> None:
    flat = [s for song_scores in per_song_scores for s in song_scores]
    rows = [_row(s) for s in flat]
    for source in SOURCES:
        for truth_origin in ("human", "seed"):
            row = corpus_row(flat, source=source, truth_origin=truth_origin)
            if row is not None:
                rows.append(row)
    write_score_txt(path, COLUMNS, rows)
