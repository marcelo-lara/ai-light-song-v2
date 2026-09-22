"""Block-review scorer family — a precision instrument on ANY song, not just
the gold four (`docs/product-refinement-v3.7.md` item 1).

Reads `block_reviews.json` — the ONLY `reference/human/` tier this module
reads. For staleness it also reads the CURRENT run's block starts per lane,
from `reference/proposals/*.json` or the gestures artifact (never another
`reference/human/` file, and never a published top-level file) — the same
lane -> producer-file mapping `ui/src/timeline/laneContent.ts` uses, kept in
sync by hand.

Emits a per-lane, per-song table: block count, reviewed count, and the
correct/wrong/misplaced split — `wrong` reported separately from `misplaced`
because a phantom and a late boundary are different defects with different
fixes. Precision = correct / reviewed. A stale review (no current block
within +-0.25s of its `start`) is excluded from the scored count — it does
not describe any block the current run emitted — but is never dropped from
the raw file and never counted as a verdict on some other block.

Recall is explicitly out of scope: a producer that emits nothing scores a
perfect precision. Recall stays measured against hand-marked truth on the
gold songs (`structure.py`, `energy_tension.py`, ...).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from . import paths
from .report import CORPUS_ROW_LABEL, write_score_txt

# The repo's own beat-alignment tolerance — same convention `matchBlockReviews`
# (ui/src/data/blockReviewMatch.ts) uses.
STALE_TOLERANCE_S = 0.25

# Every lane carrying an `experiment` field in ui/src/timeline/laneState.ts,
# plus `gestures` — the lane set docs/product-refinement-v3.7.md item 1 names.
REVIEWABLE_LANE_IDS: tuple[str, ...] = (
    "segmentSeeds",
    "vocalPhrases",
    "allin1Posterior",
    "rhythmDrumIoi",
    "rhythmStemAutocorr",
    "rhythmVocalOnsets",
    "energyLevel",
    "tensionShape",
    "character",
    "vocalTranscription",
    "gestures",
)


@dataclass(frozen=True)
class BlockReview:
    lane_id: str
    start: float  # rounded to 3 decimals — the join-key convention
    verdict: str  # "correct" | "wrong" | "misplaced"
    reason: str | None


def load_reviews(song: str) -> list[BlockReview]:
    """Every well-formed row in `block_reviews.json`. A row missing
    `lane_id`/`start`, or carrying an out-of-vocabulary `verdict`, is dropped
    rather than failing the whole file — mirrors the UI's own tolerant parse
    (`ui/src/data/parsers.ts` `parseBlockReviews`); the writer already
    validates on save. Absent file -> no reviews, not an error (most songs
    have not been reviewed at all)."""
    review_path = paths.block_reviews_path(song)
    if not review_path.exists():
        return []
    raw = json.loads(review_path.read_text())
    out: list[BlockReview] = []
    for row in raw.get("reviews", []):
        lane_id = row.get("lane_id")
        start = row.get("start")
        verdict = row.get("verdict")
        if not lane_id or start is None or verdict not in ("correct", "wrong", "misplaced"):
            continue
        out.append(
            BlockReview(
                lane_id=str(lane_id),
                start=round(float(start), 3),
                verdict=str(verdict),
                reason=row.get("reason"),
            )
        )
    return out


def _floats(rows: list[dict], key: str) -> list[float]:
    return [float(r[key]) for r in rows if isinstance(r, dict) and r.get(key) is not None]


def _vocal_phrases_starts(doc: dict) -> list[float]:
    starts: list[float] = []
    for key in ("vocal_phrases", "instrumental_gaps", "sustained_notes"):
        starts.extend(_floats(doc.get(key, []), "start"))
    return starts


def _blocks_start_s(doc: dict) -> list[float]:
    return _floats(doc.get("blocks", []), "start_s")


def _vocal_transcription_starts(doc: dict) -> list[float]:
    starts: list[float] = []
    for source in doc.get("sources", []):
        starts.extend(_floats(source.get("lines", []), "start_s"))
    return starts


def _gestures_starts(doc: dict) -> list[float]:
    return _floats(doc.get("events", []), "start_time")


def _segment_seeds_starts(doc) -> list[float]:
    return _floats(doc if isinstance(doc, list) else [], "start")


def _shadow_labels_starts(doc: dict) -> list[float]:
    return _floats(doc.get("shadow_labels", []), "start_s")


# lane_id -> (song -> Path, parsed-doc -> block starts). Kept in sync by hand
# with the corresponding adapter in ui/src/timeline/laneContent.ts /
# ui/src/data/sparseArtifacts.ts.
_LANE_SOURCES: dict[str, tuple] = {
    "segmentSeeds": (
        lambda song: paths.reference_path(song, "human", "segments.seed.json"),
        _segment_seeds_starts,
    ),
    "vocalPhrases": (
        lambda song: paths.proposals_path(song, "vocal_phrases.json"),
        _vocal_phrases_starts,
    ),
    "allin1Posterior": (
        lambda song: paths.proposals_path(song, "allin1_posterior.json"),
        _shadow_labels_starts,
    ),
    "rhythmDrumIoi": (
        lambda song: paths.proposals_path(song, "rhythm_drum_ioi.json"),
        _blocks_start_s,
    ),
    "rhythmStemAutocorr": (
        lambda song: paths.proposals_path(song, "rhythm_stem_autocorr.json"),
        _blocks_start_s,
    ),
    "rhythmVocalOnsets": (
        lambda song: paths.proposals_path(song, "rhythm_vocal_onsets.json"),
        _blocks_start_s,
    ),
    "energyLevel": (
        lambda song: paths.proposals_path(song, "energy_level.json"),
        _blocks_start_s,
    ),
    "tensionShape": (
        lambda song: paths.proposals_path(song, "tension_shape.json"),
        _blocks_start_s,
    ),
    "character": (
        lambda song: paths.proposals_path(song, "character.json"),
        _blocks_start_s,
    ),
    "vocalTranscription": (
        lambda song: paths.proposals_path(song, "vocal_transcription.json"),
        _vocal_transcription_starts,
    ),
    "gestures": (
        lambda song: paths.gestures_timeline_path(song),
        _gestures_starts,
    ),
}


def current_block_starts(song: str, lane_id: str) -> list[float]:
    """The CURRENT run's block starts for `lane_id`. An absent producer file
    means the lane emitted zero blocks this run — every review against it is
    therefore stale, not a crash and not a skip."""
    source = _LANE_SOURCES.get(lane_id)
    if source is None:
        raise ValueError(
            f"block_reviews: unknown lane_id {lane_id!r} — not in REVIEWABLE_LANE_IDS"
        )
    path_fn, extract = source
    doc_path: Path = path_fn(song)
    if not doc_path.exists():
        return []
    return extract(json.loads(doc_path.read_text()))


@dataclass
class LaneScore:
    song: str
    lane_id: str
    block_count: int
    reviewed: int
    stale: int
    correct: int
    wrong: int
    misplaced: int
    precision: float | None


def score_song(
    song: str,
    *,
    reviews: list[BlockReview] | None = None,
    block_starts: dict[str, list[float]] | None = None,
) -> list[LaneScore]:
    """One `LaneScore` per lane that has either a review or an emitted block
    this run — a lane a song was never reviewed on and never emitted a block
    for gets no row. `block_starts`, when supplied, overrides
    `current_block_starts` per lane (test hook — avoids touching disk)."""
    rows = reviews if reviews is not None else load_reviews(song)
    by_lane: dict[str, list[BlockReview]] = {}
    for r in rows:
        by_lane.setdefault(r.lane_id, []).append(r)

    def starts_for(lane_id: str) -> list[float]:
        if block_starts is not None:
            return block_starts.get(lane_id, [])
        return current_block_starts(song, lane_id)

    lane_ids = {lid for lid in REVIEWABLE_LANE_IDS if by_lane.get(lid) or starts_for(lid)}

    out: list[LaneScore] = []
    for lane_id in sorted(lane_ids):
        starts = starts_for(lane_id)
        lane_reviews = by_lane.get(lane_id, [])
        reviewed = correct = wrong = misplaced = stale_n = 0
        for review in lane_reviews:
            is_stale = not any(abs(s - review.start) <= STALE_TOLERANCE_S for s in starts)
            if is_stale:
                stale_n += 1
                continue
            reviewed += 1
            if review.verdict == "correct":
                correct += 1
            elif review.verdict == "wrong":
                wrong += 1
            else:
                misplaced += 1
        out.append(
            LaneScore(
                song=song,
                lane_id=lane_id,
                block_count=len(starts),
                reviewed=reviewed,
                stale=stale_n,
                correct=correct,
                wrong=wrong,
                misplaced=misplaced,
                precision=correct / reviewed if reviewed else None,
            )
        )
    return out


COLUMNS = [
    "song",
    "lane_id",
    "block_count",
    "reviewed",
    "stale",
    "correct",
    "wrong",
    "misplaced",
    "precision",
]


def _row(s: LaneScore) -> dict:
    return {
        "song": s.song,
        "lane_id": s.lane_id,
        "block_count": s.block_count,
        "reviewed": s.reviewed,
        "stale": s.stale,
        "correct": s.correct,
        "wrong": s.wrong,
        "misplaced": s.misplaced,
        "precision": s.precision,
    }


def corpus_row(scores: list[LaneScore], *, lane_id: str) -> dict | None:
    subset = [s for s in scores if s.lane_id == lane_id]
    if not subset:
        return None
    reviewed = sum(s.reviewed for s in subset)
    correct = sum(s.correct for s in subset)
    return {
        "song": CORPUS_ROW_LABEL,
        "lane_id": lane_id,
        "block_count": sum(s.block_count for s in subset),
        "reviewed": reviewed,
        "stale": sum(s.stale for s in subset),
        "correct": correct,
        "wrong": sum(s.wrong for s in subset),
        "misplaced": sum(s.misplaced for s in subset),
        "precision": correct / reviewed if reviewed else None,
    }


def write_report(path: Path, songs: list[str]) -> None:
    """One row per (song, lane) that has a review or a current block, plus a
    `CORPUS` row per lane aggregating across `songs`."""
    per_song = [score_song(song) for song in songs]
    flat = [s for song_scores in per_song for s in song_scores]
    rows = [_row(s) for s in flat]
    for lane_id in REVIEWABLE_LANE_IDS:
        row = corpus_row(flat, lane_id=lane_id)
        if row is not None:
            rows.append(row)
    write_score_txt(path, COLUMNS, rows)
