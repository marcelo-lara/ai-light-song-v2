"""Drop-stages family: precision/recall/F1 per stage
(`approach`/`build`/`tension`/`impact`/`release`) against human hints titled
exactly `drop approach`, `drop build`, `drop tension`, `drop impact`,
`drop release` (the parse rule already used by
`src/analyzer/stages/validation/drops.py`; this module reuses its
tolerance — `DROP_TOLERANCE_SECONDS = 1.0` — rather than inventing a second
one, though `drops.py` itself only scores an undifferentiated "drop" instant
and does not split into stages).

Ground truth: `Titanium - David Guetta ft Sia` (3 drops, 15 hints), `Armin -
Revolution` (2 drops, 10 hints), `Hideaway - Kiesza` (1 drop, 5 hints),
`_test_song` (1 drop, 5 hints) — checked 2026-09-14. Every stage hint's
`start_time` is the truth instant for that stage (matches `drops.py`, which
also scores drop *onset*, not the span).
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from . import paths
from .report import CORPUS_ROW_LABEL, write_score_txt

# Same tolerance as validation/drops.py::DROP_TOLERANCE_SECONDS.
DROP_STAGE_TOLERANCE_S = 1.0

STAGES: tuple[str, ...] = ("approach", "build", "tension", "impact", "release")
STAGE_TITLES = {f"drop {stage}": stage for stage in STAGES}

# Titanium 3 drops, Armin 2, Hideaway 1, _test_song 1 (checked 2026-09-14)
SCORING_CORPUS: tuple[str, ...] = (
    "Titanium - David Guetta ft Sia",
    "Armin - Revolution",
    "Hideaway - Kiesza",
    "_test_song",
)


@dataclass(frozen=True)
class StageEvent:
    stage: str
    time: float


def load_truth(song: str) -> list[StageEvent]:
    """Human hints exactly titled `drop <stage>` (case-insensitive), one
    event per hint at `start_time`. Fails loud if the song is in
    `SCORING_CORPUS` but the file is missing or names no stage hints — a
    corpus-declaration bug, not a skippable gap."""
    p = paths.human_hints_path(song)
    if not p.exists():
        raise FileNotFoundError(
            f"{song!r} is in drop_stages.SCORING_CORPUS but has no {p}."
        )
    doc = json.loads(p.read_text())
    events: list[StageEvent] = []
    for h in doc.get("human_hints", []):
        stage = STAGE_TITLES.get(str(h.get("title", "")).strip().lower())
        if stage is not None:
            events.append(StageEvent(stage=stage, time=float(h["start_time"])))
    if not events:
        raise ValueError(
            f"{song!r} is in drop_stages.SCORING_CORPUS but its human_hints.json "
            f"names no 'drop <stage>' titled hints."
        )
    return sorted(events, key=lambda e: e.time)


def _greedy_match(predicted: list[float], truth: list[float], tolerance: float) -> int:
    """Greedy nearest-first one-to-one match, same shape as
    `validation/drops.py::_greedy_match`."""
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
class DropStageScore:
    song: str
    stage: str
    n_truth: int
    n_predicted: int
    matched: int
    precision: float | None
    recall: float | None
    f1: float


def score_drop_stages(
    song: str,
    predicted: list[dict],
    *,
    truth: list[StageEvent] | None = None,
    tolerance: float = DROP_STAGE_TOLERANCE_S,
) -> list[DropStageScore]:
    """`predicted`: `[{"stage": "approach"|..., "time": float}, ...]`. One
    `DropStageScore` per stage in `STAGES` (0 predicted/truth is still
    reported, never dropped, so a caller can see a stage the producer never
    emits)."""
    truth_rows = truth if truth is not None else load_truth(song)
    out: list[DropStageScore] = []
    for stage in STAGES:
        t_times = sorted(e.time for e in truth_rows if e.stage == stage)
        p_times = sorted(float(r["time"]) for r in predicted if r.get("stage") == stage)
        matched = _greedy_match(p_times, t_times, tolerance)
        precision = matched / len(p_times) if p_times else None
        recall = matched / len(t_times) if t_times else None
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision is not None and recall is not None and (precision + recall) > 0
            else 0.0
        )
        out.append(
            DropStageScore(
                song=song,
                stage=stage,
                n_truth=len(t_times),
                n_predicted=len(p_times),
                matched=matched,
                precision=precision,
                recall=recall,
                f1=round(f1, 4),
            )
        )
    return out


COLUMNS = ["song", "stage", "n_truth", "n_predicted", "matched", "precision", "recall", "f1"]


def _row(s: DropStageScore) -> dict:
    return {
        "song": s.song,
        "stage": s.stage,
        "n_truth": s.n_truth,
        "n_predicted": s.n_predicted,
        "matched": s.matched,
        "precision": s.precision,
        "recall": s.recall,
        "f1": s.f1,
    }


def corpus_row(scores: list[DropStageScore]) -> dict:
    """One micro-averaged row per stage across every song, plus an
    all-stage row — corpus_row returns the all-stage pooled row; callers
    wanting per-stage corpus rows should pool `scores` themselves by stage
    before calling this (kept simple: this module's `write_report` does
    both)."""
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
    return {
        "song": CORPUS_ROW_LABEL,
        "stage": "all",
        "n_truth": total_truth,
        "n_predicted": total_pred,
        "matched": total_matched,
        "precision": precision,
        "recall": recall,
        "f1": round(f1, 4),
    }


def write_report(path: Path, per_song_scores: list[list[DropStageScore]]) -> None:
    """`per_song_scores`: one `score_drop_stages()` result list per song."""
    flat = [s for song_scores in per_song_scores for s in song_scores]
    rows = [_row(s) for s in flat] + [corpus_row(flat)]
    write_score_txt(path, COLUMNS, rows)
