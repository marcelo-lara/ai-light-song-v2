"""Fit a 4-bar phrase grid to a boundary set, then classify each block by how
well its edges lock to that grid.

Method (refinement doc item 4):

  * bar length  -> median downbeat spacing from `beats.json` (period only, never
    phase — the downbeat-phase weakness does not touch this; the phase is fit
    here, to the boundary set, not taken from the grid).
  * phrase grid -> lines every `PHRASE_BARS` bars. The phase offset is swept and
    the offset that minimises the median edge-to-line distance over the
    *boundary set* (union of items 6 and 7's proposal edges) is kept.
  * `grid_fit_bars` for an edge -> distance to the nearest phrase-grid line,
    expressed in bars. A block is `structural` when at least one of its edges
    locks to the grid within `STRUCTURAL_MAX_BARS`, else `micro`.

`STRUCTURAL_MAX_BARS = 0.12` is not tuned to a target number: the refinement
doc's own `Queen of Kings` fit puts the structural edges at -0.06..-0.00 bars and
the micro edges at 0.15..3.3 bars, so anything in (0.06, 0.15) separates them.
"""
from __future__ import annotations

import numpy as np

STRUCTURAL_MAX_BARS = 0.12
_PHASE_STEPS = 400


def bar_length(downbeats: np.ndarray) -> float:
    if len(downbeats) < 2:
        return 0.0
    return float(np.median(np.diff(np.sort(downbeats))))


def _line_distance_s(edges: np.ndarray, phase: float, phrase_len_s: float) -> np.ndarray:
    d = np.mod(edges - phase, phrase_len_s)
    return np.minimum(d, phrase_len_s - d)


def fit_phrase_grid(
    boundary_set: np.ndarray, downbeats: np.ndarray, phrase_bars: int
) -> tuple[float, float]:
    """Return (phase_s, phrase_len_s). phase_s is an absolute time a grid line
    passes through; grid lines are then phase_s + k * phrase_len_s."""
    bar_len = bar_length(downbeats)
    if bar_len <= 0:
        return 0.0, 0.0
    phrase_len_s = phrase_bars * bar_len
    if len(boundary_set) == 0:
        anchor = float(downbeats[0]) if len(downbeats) else 0.0
        return anchor % phrase_len_s, phrase_len_s

    candidates = list(np.linspace(0.0, phrase_len_s, _PHASE_STEPS, endpoint=False))
    candidates += [float(db) % phrase_len_s for db in downbeats]
    best_phase, best_err = 0.0, np.inf
    for phase in candidates:
        err = float(np.median(_line_distance_s(boundary_set, phase, phrase_len_s)))
        if err < best_err:
            best_phase, best_err = float(phase), err
    return best_phase, phrase_len_s


def grid_fit_bars(edge: float, phase_s: float, phrase_len_s: float, bar_len: float) -> float:
    if phrase_len_s <= 0 or bar_len <= 0:
        return float("nan")
    d = float(_line_distance_s(np.array([edge]), phase_s, phrase_len_s)[0])
    return d / bar_len


def classify_block(
    start_s: float,
    end_s: float,
    phase_s: float,
    phrase_len_s: float,
    bar_len: float,
) -> tuple[str, float]:
    """(kind, grid_fit_bars) — grid_fit_bars is the better-locking of the two
    edges; kind is `structural` when that value is <= STRUCTURAL_MAX_BARS."""
    fs = grid_fit_bars(start_s, phase_s, phrase_len_s, bar_len)
    fe = grid_fit_bars(end_s, phase_s, phrase_len_s, bar_len)
    fit = min(fs, fe)
    kind = "structural" if fit <= STRUCTURAL_MAX_BARS else "micro"
    return kind, round(fit, 3)


# --- cheap baseline: block duration alone -----------------------------------

def baseline_kind(start_s: float, end_s: float, bar_len: float) -> str:
    """< 1 bar => micro (refinement doc item 4 cheap baseline)."""
    if bar_len <= 0:
        return "micro"
    return "micro" if (end_s - start_s) < bar_len else "structural"
