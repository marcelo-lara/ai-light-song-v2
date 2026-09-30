"""The low-cardinality state machine.

This is deliberately NOT `experiments/texture_novelty` (self-similarity
novelty over spectral bands, F1 0.29, archived — see
`docs/archive/experiments.discarded.texture-novelty.md`; it fired on texture
change everywhere, including inside a stable section). This module instead
classifies each bar into one of a handful of discrete stem-presence states
and only cuts a boundary where the state **changes and persists** —
hysteresis is the whole point, not an afterthought.

Pure functions, no I/O — `features.py` supplies the per-bar levels,
`export.py` supplies the physical-onset refinement. Unit-tested in
`tests/test_state_machine.py`.
"""
from __future__ import annotations

from dataclasses import dataclass

#: Minimum section length in bars. A run of bars shorter than this is not a
#: section — it is merged into whichever section it interrupted. This is the
#: constant that stops a short dip (e.g. `Rapture - Nadia Ali`'s drums
#: dropping out for ~1 bar at 60.25-62.25 s, inside a 15 s drop) from
#: splitting a section in two.
MIN_SECTION_BARS = 4

#: On/off and full/sparse/off thresholds, each a FRACTION OF THE SONG'S OWN
#: per-stem bar-level p95 (`features.py::compute_bars`) — never an absolute
#: level. Stem levels are song-relative (mix loudness, mastering, stem
#: separation quality all vary per song), so a fixed absolute threshold would
#: not transfer.
BASS_ON_FRAC = 0.35
DRUMS_FULL_FRAC = 0.50
DRUMS_SPARSE_FRAC = 0.15
VOCALS_ON_FRAC = 0.40

CoarseLabel = str  # "full" | "bass_only" | "drums_only" | "stripped"


@dataclass(frozen=True)
class BarClassification:
    bass_state: str  # "on" | "off"
    drums_state: str  # "full" | "sparse" | "off"
    vocals_present: bool
    confidence: float  # 0..1, margin between the bar's level and the nearer threshold


def classify_bar(
    level_bass: float,
    level_drums: float,
    level_vocals: float,
    p95_bass: float,
    p95_drums: float,
    p95_vocals: float,
) -> BarClassification:
    """One bar's discrete state. `confidence` is the mean, over bass and
    drums, of |level - nearest threshold| / p95 (capped at 1.0) — a bar
    sitting exactly on a threshold reads `confidence: 0`, never inflated."""
    bass_thr = BASS_ON_FRAC * p95_bass
    bass_state = "on" if level_bass >= bass_thr else "off"
    bass_margin = abs(level_bass - bass_thr) / p95_bass if p95_bass > 0 else 0.0

    full_thr = DRUMS_FULL_FRAC * p95_drums
    sparse_thr = DRUMS_SPARSE_FRAC * p95_drums
    if level_drums >= full_thr:
        drums_state = "full"
        drums_margin = abs(level_drums - full_thr) / p95_drums if p95_drums > 0 else 0.0
    elif level_drums >= sparse_thr:
        drums_state = "sparse"
        drums_margin = (
            min(abs(level_drums - full_thr), abs(level_drums - sparse_thr)) / p95_drums
            if p95_drums > 0 else 0.0
        )
    else:
        drums_state = "off"
        drums_margin = abs(level_drums - sparse_thr) / p95_drums if p95_drums > 0 else 0.0

    vocals_thr = VOCALS_ON_FRAC * p95_vocals
    vocals_present = level_vocals >= vocals_thr

    confidence = round(min(1.0, (bass_margin + drums_margin) / 2.0), 4)
    return BarClassification(bass_state, drums_state, vocals_present, confidence)


def coarse_label(bass_state: str, drums_state: str) -> CoarseLabel:
    """Vocals never enter this mapping — the task's hard requirement.
    `drums_state in {"full", "sparse"}` both count as drums "present"; the
    full/sparse distinction is kept on the row but does not, by itself, cut
    a boundary (that would just reintroduce the dip problem one level up)."""
    drums_present = drums_state in ("full", "sparse")
    if bass_state == "on" and drums_present:
        return "full"
    if bass_state == "on" and not drums_present:
        return "bass_only"
    if bass_state == "off" and drums_present:
        return "drums_only"
    return "stripped"


def _rle_bounds(labels: list[str]) -> list[list]:
    """`[label, start, end)]` runs of consecutive equal labels."""
    runs: list[list] = []
    i = 0
    n = len(labels)
    while i < n:
        j = i
        while j + 1 < n and labels[j + 1] == labels[i]:
            j += 1
        runs.append([labels[i], i, j + 1])
        i = j + 1
    return runs


def _collapse_equal_bounds(runs: list[list]) -> list[list]:
    out: list[list] = []
    for label, start, end in runs:
        if out and out[-1][0] == label and out[-1][2] == start:
            out[-1][2] = end
        else:
            out.append([label, start, end])
    return out


def _dominant_bass(run_bass: list[str]) -> str:
    """Majority `bass_state` over a run; a tie (only possible on an
    even-length run) breaks to the run's LAST bar — the most recent
    evidence, not an arbitrary constant."""
    on = run_bass.count("on")
    off = len(run_bass) - on
    if on > off:
        return "on"
    if off > on:
        return "off"
    return run_bass[-1]


def apply_hysteresis(
    states: list[tuple[str, str]], min_bars: int = MIN_SECTION_BARS
) -> list[str]:
    """`states[i] = (bass_state, drums_state)`, one bar's raw classification
    (`BarClassification.bass_state`/`.drums_state`). Returns the smoothed
    COARSE label per bar.

    A literal run-length merge (collapse a short run into whichever run is
    literally adjacent, always the same direction) is not enough: a single
    decay-tail or bleed-through bar right at a real transition edge often
    reads a different DRUMS tier than either neighbour (`full`/`sparse`/
    `off` sit close together and a lingering hi-hat or reverb tail crosses a
    tier boundary for exactly one bar), which fragments both a genuine
    boundary (splitting it into two too-short runs that both get swallowed
    the wrong way) and a genuine short section (an EDM break's own edge bar
    misreads, cutting a real `MIN_SECTION_BARS`-long event down to one bar
    short of the threshold).

    So a short run merges into whichever NEIGHBOUR shares its majority
    `bass_state` — bass is the more reliable dimension for this decision:
    a bassline entering or leaving is normally a hard mixer cut, where the
    drums full/sparse tiers can flicker near a decay tail or a continuing
    hi-hat/percussion layer. If both neighbours match (or neither does),
    merge whichever direction produces the LONGER combined run — a real
    multi-bar event should end up as one run, not stay split. A remaining
    tie merges backward (arbitrary but deterministic)."""
    labels = [coarse_label(b, d) for b, d in states]
    n = len(labels)
    if n == 0:
        return []
    bass_states = [b for b, _d in states]

    runs = _rle_bounds(labels)
    while True:
        idx = next((i for i, r in enumerate(runs) if r[2] - r[1] < min_bars), None)
        if idx is None:
            break
        _label, lo, hi = runs[idx]
        dominant = _dominant_bass(bass_states[lo:hi])

        can_back = idx > 0
        can_fwd = idx < len(runs) - 1
        prev_bass = bass_states[runs[idx - 1][2] - 1] if can_back else None
        next_bass = bass_states[runs[idx + 1][1]] if can_fwd else None
        back_matches = can_back and prev_bass == dominant
        fwd_matches = can_fwd and next_bass == dominant

        if back_matches and not fwd_matches:
            direction = "backward"
        elif fwd_matches and not back_matches:
            direction = "forward"
        elif can_back and can_fwd:
            back_len = (runs[idx - 1][2] - runs[idx - 1][1]) + (hi - lo)
            fwd_len = (hi - lo) + (runs[idx + 1][2] - runs[idx + 1][1])
            direction = "forward" if fwd_len > back_len else "backward"
        elif can_fwd:
            direction = "forward"
        else:
            direction = "backward"

        if direction == "backward":
            runs[idx - 1][2] = hi
        else:
            runs[idx + 1][1] = lo
        runs.pop(idx)
        runs = _collapse_equal_bounds(runs)

    out = [""] * n
    for label, lo, hi in runs:
        for k in range(lo, hi):
            out[k] = label
    return out


@dataclass(frozen=True)
class Section:
    label: CoarseLabel
    bar_start: int
    bar_end: int
    start_s: float
    end_s: float
    bar_indices: tuple[int, ...]


def group_into_sections(smoothed_labels: list[str], bar_rows: list[dict]) -> list[Section]:
    """`bar_rows[i]` must carry `bar`/`start`/`end` (features.py's cache
    shape). Groups consecutive equal labels — `smoothed_labels` is expected
    to already be hysteresis-applied; this function does no merging of its
    own."""
    if len(smoothed_labels) != len(bar_rows):
        raise ValueError("smoothed_labels and bar_rows must be the same length")
    sections: list[Section] = []
    i = 0
    n = len(smoothed_labels)
    while i < n:
        j = i
        while j + 1 < n and smoothed_labels[j + 1] == smoothed_labels[i]:
            j += 1
        sections.append(
            Section(
                label=smoothed_labels[i],
                bar_start=bar_rows[i]["bar"],
                bar_end=bar_rows[j]["bar"],
                start_s=bar_rows[i]["start"],
                end_s=bar_rows[j]["end"],
                bar_indices=tuple(range(i, j + 1)),
            )
        )
        i = j + 1
    return sections
