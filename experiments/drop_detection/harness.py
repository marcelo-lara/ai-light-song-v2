"""Scoring. Impact instants only — see README for why the phase labels are not
scoreable as authored."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

TOLERANCE = 0.5


@dataclass
class SongScore:
    song: str
    n_true: int
    n_pred: int
    matches: list[tuple[float, float]] = field(default_factory=list)   # (gt, pred)
    missed: list[float] = field(default_factory=list)
    spurious: list[float] = field(default_factory=list)

    @property
    def errors(self) -> list[float]:
        return [pred - gt for gt, pred in self.matches]

    @property
    def recall(self) -> float:
        return len(self.matches) / self.n_true if self.n_true else float("nan")

    @property
    def precision(self) -> float:
        return len(self.matches) / self.n_pred if self.n_pred else float("nan")


def match(gt: list[float], pred: list[float], tol: float = TOLERANCE) -> tuple[list, list, list]:
    """Greedy globally-closest pairing, so a cluster of predictions near one
    label cannot claim more than one label."""
    pairs = sorted(
        ((abs(g - p), g, p) for g in gt for p in pred if abs(g - p) <= tol),
        key=lambda row: row[0],
    )
    used_gt: set[float] = set()
    used_pred: set[float] = set()
    matches = []
    for _, g, p in pairs:
        if g in used_gt or p in used_pred:
            continue
        used_gt.add(g)
        used_pred.add(p)
        matches.append((g, p))
    matches.sort()
    return matches, [g for g in gt if g not in used_gt], [p for p in pred if p not in used_pred]


def score_song(song: str, gt: list[float], pred: list[float], tol: float = TOLERANCE) -> SongScore:
    matches, missed, spurious = match(gt, pred, tol)
    return SongScore(song, len(gt), len(pred), matches, missed, spurious)


def report(scores: list[SongScore], *, title: str, tol: float = TOLERANCE) -> None:
    print(f"\n== {title}  (tolerance +-{tol:.2f}s) ==")
    tp = sum(len(s.matches) for s in scores)
    n_true = sum(s.n_true for s in scores)
    n_pred = sum(s.n_pred for s in scores)
    all_err = [e for s in scores for e in s.errors]
    for s in scores:
        errs = ", ".join(f"{e:+.2f}" for e in s.errors) or "-"
        print(f"  {s.song:<34} gt={s.n_true} pred={s.n_pred:<3} hit={len(s.matches)} "
              f"miss={len(s.missed)} fp={len(s.spurious)}  err[{errs}]")
        if s.missed:
            print(f"      missed: {', '.join(f'{m:.2f}' for m in s.missed)}")
    rec = tp / n_true if n_true else float("nan")
    prec = tp / n_pred if n_pred else float("nan")
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else float("nan")
    med = float(np.median(np.abs(all_err))) if all_err else float("nan")
    mx = float(np.max(np.abs(all_err))) if all_err else float("nan")
    print(f"  TOTAL recall={rec:.3f} ({tp}/{n_true})  precision={prec:.3f} ({tp}/{n_pred})  "
          f"f1={f1:.3f}  |err| median={med:.3f}s max={mx:.3f}s")
