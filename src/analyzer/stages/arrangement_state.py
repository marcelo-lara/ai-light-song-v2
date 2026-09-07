"""Phase 3 (relate) — arrangement-state change detection from published RMS.

The question this answers is not "what part is this" but "*who is playing*, and
when does that change". Nothing here reads audio, a spectrogram or a model —
only the top-level `loudness.json` the pipeline already publishes (the 20 ms
per-stem RMS series). Reading the delivery surface rather than the artifact is
deliberate: it is what makes this a phase-3 stage that produces structure
without touching audio.

Ported from `experiments/arrangement_state/` (promoted in the v3.2 plan). The
experiment's `detect_smoothed()` ablation is intentionally NOT carried over —
its finding stays recorded in `docs/archive/experiments_promoted.md`.

Three decisions carry the whole result; each is a measured one.

1.  **Per-stem, per-song thresholds.** A stem is judged against its own 98th
    percentile in this song, never an absolute level. Nothing transfers between
    tracks or between stems.
2.  **Detect at 250 ms, gate on persistence, report the fine edge.** Smoothing
    the presence signal before thresholding buys precision and *moves the
    boundary* — measured at F1 0.59 -> 0.27 on `_test_song`, with the `Spacer`
    hint displaced by 6 s. So a flip counts only if the new value holds, and the
    time reported is always the unsmoothed edge (a cue fired late is a cue
    missed).
3.  **The mix channel never triggers a change.** It is a sum, so it moves
    whenever any stem does and adds no independent evidence.

Measured (`experiments/arrangement_state/README.md`, Measurement 2/4): on
`_test_song`, the one densely texture-labelled gold song, F1 0.59 @0.5 s /
0.75 @1.0 s against the operator's hand-marked hint starts, median hit error
0.07 s, where the shipped `sections.json` scores 0.00. Corpus-wide it sits at
the noise floor of the labels (32 of 47 gold hints are drop stages `gestures.py`
owns), pooled F1 0.20 vs the incumbent's 0.24. `margin_db` is a measured
distance from the decision boundary, not a tuned score, and is a poor precision
filter — it is carried as honest confidence evidence, never gated on.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from analyzer.io import read_json, write_json
from analyzer.models import SCHEMA_VERSION
from analyzer.paths import SongPaths

#: Detection grid. Fine enough for the shortest hand-marked block in the corpus
#: (`_test_song` "Spacer", 0.46 s) to survive as its own edge.
WINDOW_S = 0.25

#: A stem counts as sounding when it is within this many dB of its own loud
#: level in this song. 18 dB is roughly "audible in the mix" rather than
#: "audible in isolation" — below it, stem bleed from the separator dominates.
PRESENT_DB_BELOW_P98 = 18.0

#: Fraction of a window's frames above threshold for the window to read present.
PRESENT_FRACTION = 0.4

#: How long a flipped value must hold before the flip is believed, and how much
#: of that span must agree. Expressed in seconds rather than bars because the
#: downbeat grid measures 0.226 F1 — the bar numbers are not trustworthy enough
#: to gate a boundary on.
HOLD_S = 1.5
HOLD_AGREEMENT = 0.7


@dataclass
class Change:
    time: float
    entered: list[str] = field(default_factory=list)
    left: list[str] = field(default_factory=list)
    state: dict[str, bool] = field(default_factory=dict)
    #: Smallest dB margin among the stems that flipped — the evidence behind
    #: this change, and what a confidence would be derived from.
    margin_db: float = 0.0


@dataclass
class Result:
    song: str
    stems: list[str]
    times: list[float]
    presence: list[list[float]]
    thresholds_db: dict[str, float]
    changes: list[Change]
    duration: float


def _percentile(values: list[float], p: float) -> float:
    s = sorted(values)
    k = (len(s) - 1) * p
    f = int(k)
    return s[f] + (s[min(f + 1, len(s) - 1)] - s[f]) * (k - f)


def _windows(
    paths: SongPaths,
) -> tuple[list[str], float, list[float], list[list[float]], list[list[float]], dict[str, float]]:
    """Everything downstream of the raw per-stem dB series and before the
    persistence gate: (order, duration, win_times, presence, margin,
    thresholds_db).

    Reads the *published* top-level `loudness.json` (20 ms per-stem RMS), never
    `artifacts/essentia/rms_loudness.json` — no silent fallback to the artifact.
    """
    doc = read_json(paths.loudness_output_path)
    order: list[str] = doc["metadata"]["source_order"]
    duration: float = doc["metadata"]["duration"]
    frames = doc["frames"]

    times = [f["time"] for f in frames]
    # dB per source. A silent frame floors at -180 dB rather than being dropped:
    # silence is a fact about the stem, not missing data (no silent fallbacks).
    db = [[20.0 * math.log10(max(f["values"][i], 1e-9)) for f in frames] for i in range(len(order))]
    thresholds = {order[i]: _percentile(db[i], 0.98) - PRESENT_DB_BELOW_P98 for i in range(len(order))}

    n_windows = int(duration / WINDOW_S)
    win_times: list[float] = []
    presence: list[list[float]] = []
    margin: list[list[float]] = []
    cursor = 0
    for w in range(n_windows):
        lo, hi = w * WINDOW_S, (w + 1) * WINDOW_S
        while cursor < len(times) and times[cursor] < lo:
            cursor += 1
        idx = []
        j = cursor
        while j < len(times) and times[j] < hi:
            idx.append(j)
            j += 1
        if not idx:
            continue
        win_times.append(lo)
        presence.append(
            [sum(1 for k in idx if db[i][k] > thresholds[order[i]]) / len(idx) for i in range(len(order))]
        )
        margin.append(
            [max(db[i][k] for k in idx) - thresholds[order[i]] for i in range(len(order))]
        )

    return order, duration, win_times, presence, margin, thresholds


def detect(paths: SongPaths) -> Result:
    order, duration, win_times, presence, margin, thresholds = _windows(paths)

    hold = max(1, int(round(HOLD_S / WINDOW_S)))
    n = len(win_times)
    state = [[False] * len(order) for _ in range(n)]
    for i in range(len(order)):
        cur = presence[0][i] > PRESENT_FRACTION
        state[0][i] = cur
        for w in range(1, n):
            v = presence[w][i] > PRESENT_FRACTION
            if v != cur:
                future = [presence[k][i] > PRESENT_FRACTION for k in range(w, min(n, w + hold))]
                if sum(1 for x in future if x == v) >= HOLD_AGREEMENT * len(future):
                    cur = v
            state[w][i] = cur

    changes: list[Change] = []
    for w in range(1, n):
        entered, left, margins = [], [], []
        for i, stem in enumerate(order):
            if stem == "mix" or state[w][i] == state[w - 1][i]:
                continue
            (entered if state[w][i] else left).append(stem)
            margins.append(abs(margin[w][i]))
        if entered or left:
            changes.append(
                Change(
                    time=round(win_times[w], 3),
                    entered=entered,
                    left=left,
                    state={s: state[w][i] for i, s in enumerate(order) if s != "mix"},
                    margin_db=round(min(margins), 2),
                )
            )

    return Result(
        song=paths.song_name,
        stems=[s for s in order if s != "mix"],
        times=win_times,
        presence=presence,
        thresholds_db={k: round(v, 2) for k, v in thresholds.items()},
        changes=changes,
        duration=duration,
    )


def blocks(result: Result) -> list[dict]:
    """The changes read as spans — what a published character block would be."""
    edges = [0.0] + [c.time for c in result.changes] + [result.duration]
    out = []
    for i, c in enumerate([None] + result.changes):
        start, end = edges[i], edges[i + 1]
        if end - start <= 0:
            continue
        state = c.state if c else {s: True for s in result.stems}
        playing = [s for s in result.stems if state.get(s)]
        out.append(
            {
                "start_s": round(start, 3),
                "end_s": round(end, 3),
                "playing": playing,
                "entered": c.entered if c else [],
                "left": c.left if c else [],
                "margin_db": c.margin_db if c else None,
            }
        )
    return out


def detect_arrangement_state(paths: SongPaths) -> dict:
    """Stage entry point. Reads the published `loudness.json`, writes
    `artifacts/arrangement_state.json` — the intermediate the publish stage
    fuses into the top-level delivery-surface file."""
    result = detect(paths)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_from": {
            "engine": "analyzer.stages.arrangement_state",
            "reads": "loudness.json",
            "window_s": WINDOW_S,
            "present_db_below_p98": PRESENT_DB_BELOW_P98,
            "present_fraction": PRESENT_FRACTION,
            "hold_s": HOLD_S,
            "hold_agreement": HOLD_AGREEMENT,
        },
        "blocks": blocks(result),
    }
    write_json(paths.artifact("arrangement_state.json"), payload)
    return payload
