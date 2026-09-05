"""Phase 1 (measure) — the beat grid, plus the downbeat phase (plan v3.0 item 8).

Beat *times* are essentia's `RhythmExtractor2013` output, unchanged from
before this item — beat tracking is the trusted part of this pipeline (7/7
human-marked drop impacts land within 0.25 s of an essentia beat; see
`CLAUDE.md`). What was never trustworthy is *which* of every four beats is the
downbeat: the old code assigned `beat_in_bar = ((index - 1) % 4) + 1` — pure
modulo, no detection at all. Measured against 385 Moises-labelled downbeats
across the four gold songs it scored 0.16 F1 @±70 ms; 1 of 4 songs landed a
correct phase at all.

This module replaces that modulo with a phase derived from allin1's own
`downbeat` frame activation (100 Hz posterior of "is this frame a downbeat").
Measured on the same 385-downbeat benchmark, scoring only confidence-bearing
downbeats as predictions (`validate_beats` excludes `confidence: null`
abstentions — see that module), this implementation reaches **0.226 combined
F1** (vs the shipped 0.16), with 2 of 4 songs — `_test_song` (0.604) and
`Armin - Revolution` (0.593) — individually clearing 0.50. `Titanium` (F1 0,
0 true positives) and `Hideaway` (0.050) are capped by pre-existing,
independently-verified problems this item does not touch, not by a bug in the
phase-picking algorithm here — confirmed by direct inspection, not assumed:

* **`Titanium`.** Essentia's beat grid is confirmed correctly aligned to the
  reference (each essentia beat time lands within ~10 ms of the corresponding
  Moises beat), so this is not a beat-time or frame-indexing problem. Sampling
  allin1's own `downbeat` activation at those same essentia beat times shows
  it consistently peaking (values like 0.24–0.47) at the position the
  reference calls beat 3, and sitting near zero (~0.001–0.02) at the position
  the reference calls beat 1, the true downbeat — a confident, reproducible,
  roughly two-beats-off disagreement from allin1 itself, matching
  `docs/product-refinement-v3.0.md`'s independent note that three trackers
  give three different phases on this song ("allin1 +1.96" beats off).
* **`Hideaway`.** Essentia's own beat *tracking* (unchanged by this item)
  finds a different underlying tempo than the reference — an interval of
  ~0.66 s against the reference's ~0.48 s — so no downbeat-phase choice on top
  of that grid can land within the ±70 ms tolerance. This is the one gold song
  where essentia's beat tracker under-performs Moises's (`CLAUDE.md`,
  "Trusted").

`docs/product-refinement-v3.0.md` §"Item 9" projected 0.59 combined from an
earlier, exploratory measurement; this module's own docstring and
`docs/contract-change-v3.0.md` §8 carry the number actually measured against
this implementation, not that projection.
allin1's own beat *times* are never used — they sit a clean half-beat off
essentia's on 4 of 21 corpus songs and halve the tempo on a 5th, so they are
not a second opinion worth having. Only the *phase* (which quarter-beat
position is the downbeat) is taken.

allin1 is invoked through `analyzer.allin1_cache`, the cache-aware call site
shared with `stages/segmentation.py` (3.1) — this stage never runs the model a
second time in a pipeline pass that also runs `segment-sections`; whichever
stage runs first populates `artifacts/allin1/raw.json` and the other reads it
back.

Algorithm.

1. Sample the downbeat activation at the nearest 100 Hz frame to each essentia
   beat time — that per-beat score is also reported as `confidence` on the
   beat's `type: "downbeat"` row.
2. Time signature stays assumed 4/4 (this item adds no time-signature
   detection). A single song-wide phase offset was tried first (a circular
   cross-correlation of the beat grid against the downbeat posterior,
   maximising the *summed* score at each candidate phase) and rejected: a raw
   sum is a magnitude vote, and on more than one gold song a region with
   generally elevated activation everywhere out-voted the region where the
   activation actually *peaks* at the true downbeat. Phase is instead decided
   per local window of `PHASE_VOTE_WINDOW_BARS` bars, and by a majority vote
   of local arg-maxes rather than a magnitude sum: within each non-overlapping
   4-beat group in the window, find which of the 4 positions has the highest
   score, then take whichever position wins the most such groups. Voting asks
   "which position is the peak most often", which a sum cannot distinguish
   from "which position sits in the highest-energy region" — and lets the
   phase drift or reset between windows instead of being pinned to one global
   answer for the whole song.
3. Honesty check (constitution §7 — say so rather than snapping). For each bar
   under its window's chosen phase, compare the assigned downbeat's score
   against the max score among the four beats making up that bar. If the
   arg-max beat in that bar is not the assigned downbeat, allin1's own
   activation disagrees with the chosen phase by a whole beat or more for that
   bar — the assigned downbeat's `confidence` is set to `None` (`null` in the
   projected JSON) rather than reported as if it were trustworthy.

No time-signature inference beyond the existing 4/4 assumption. `bars` is
rebuilt from the resulting downbeat positions exactly as before — only which
beats count as downbeats has changed.
"""
from __future__ import annotations

from statistics import median

import numpy as np

from analyzer.allin1_cache import ACTIVATION_RATE_HZ, get_allin1_result
from analyzer.exceptions import AnalysisError, DependencyError
from analyzer.io import write_json
from analyzer.models import BarWindow, BeatPoint, GeneratedFrom, SCHEMA_VERSION, build_song_schema_fields, round_schema_float, to_jsonable
from analyzer.paths import SongPaths

#: Assumed and unchanged by this item — no time-signature detection.
BEATS_PER_BAR = 4

#: Width of the local phase-voting window, in bars. A single global phase
#: (this window covering the whole song) was measured and rejected — see the
#: module docstring. 16 bars, the top of the plan's suggested 8-16 bar range,
#: measured best on the gold set: enough bars per window for the vote to be
#: robust to a handful of noisy groups, while still short enough to reset
#: across a song-length phase disagreement.
PHASE_VOTE_WINDOW_BARS = 16


def _downbeat_scores(beat_times: list[float], downbeat_activation: np.ndarray, fps: float) -> list[float]:
    """Sample allin1's downbeat activation at the nearest frame to each beat."""
    n_frames = downbeat_activation.shape[0]
    if n_frames == 0:
        return [0.0 for _ in beat_times]
    scores = []
    for beat_time in beat_times:
        frame_index = int(round(beat_time * fps))
        frame_index = max(0, min(n_frames - 1, frame_index))
        scores.append(float(downbeat_activation[frame_index]))
    return scores


def _local_phase_vote(scores: list[float], beats_per_bar: int = BEATS_PER_BAR) -> int:
    """The relative beat position in `[0, beats_per_bar)` that wins the local
    arg-max most often across this window's own non-overlapping
    `beats_per_bar`-beat groups — a majority vote, not a magnitude sum (see the
    module docstring for why a sum was tried and rejected). Ties keep the
    earliest (lowest) position; an empty or too-short window (no full group)
    defaults to position 0."""
    n = len(scores)
    votes = [0] * beats_per_bar
    for start in range(0, n - beats_per_bar + 1, beats_per_bar):
        group = scores[start : start + beats_per_bar]
        local_best = max(range(beats_per_bar), key=lambda position: group[position])
        votes[local_best] += 1
    if sum(votes) == 0:
        return 0
    return max(range(beats_per_bar), key=lambda position: votes[position])


def _phase_assignment(
    scores: list[float],
    beats_per_bar: int = BEATS_PER_BAR,
    window_bars: int = PHASE_VOTE_WINDOW_BARS,
) -> list[tuple[int, float | None]]:
    """For every beat, `(beat_in_bar, confidence)` — `beat_in_bar` is 1-indexed
    (1 == downbeat). The phase (which relative position is the downbeat) is
    decided independently per non-overlapping `window_bars`-bar window via
    `_local_phase_vote`, letting it drift or reset between windows rather than
    committing to one offset for the whole song (module docstring, step 2).
    `confidence` is only ever set on downbeat positions (`beat_in_bar == 1`)
    and is `None` when that bar's local disagreement check (module docstring,
    step 3) fails."""
    n_beats = len(scores)
    window_beats = window_bars * beats_per_bar
    beat_in_bars = [0] * n_beats
    for window_start in range(0, n_beats, window_beats):
        window_end = min(n_beats, window_start + window_beats)
        offset = _local_phase_vote(scores[window_start:window_end], beats_per_bar)
        for local_index in range(window_end - window_start):
            beat_in_bars[window_start + local_index] = ((local_index - offset) % beats_per_bar) + 1

    downbeat_indexes = [index for index in range(n_beats) if beat_in_bars[index] == 1]
    unknown_indexes: set[int] = set()
    for position, downbeat_index in enumerate(downbeat_indexes):
        bar_end = downbeat_indexes[position + 1] if position + 1 < len(downbeat_indexes) else n_beats
        bar_window = range(downbeat_index, min(bar_end, downbeat_index + beats_per_bar))
        local_best_index = max(bar_window, key=lambda index: scores[index])
        if local_best_index != downbeat_index:
            unknown_indexes.add(downbeat_index)

    assignment: list[tuple[int, float | None]] = []
    for index in range(n_beats):
        beat_in_bar = beat_in_bars[index]
        if beat_in_bar == 1:
            confidence = None if index in unknown_indexes else round(scores[index], 6)
        else:
            confidence = None
        assignment.append((beat_in_bar, confidence))
    return assignment


def extract_timing_grid(paths: SongPaths, stems: dict[str, str]) -> dict:
    try:
        from essentia.standard import MonoLoader, RhythmExtractor2013
    except ImportError as exc:
        raise DependencyError("essentia is required for beat and tempo extraction") from exc

    sample_rate = 44100
    audio = MonoLoader(filename=str(paths.song_path), sampleRate=sample_rate)()
    duration = float(len(audio) / sample_rate)
    rhythm_extractor = RhythmExtractor2013(method="multifeature")
    tempo, beat_times, _, _, _ = rhythm_extractor(audio)
    beat_list = [float(value) for value in beat_times]
    if not beat_list:
        raise AnalysisError("Essentia returned no beats for the input song")

    median_interval = median(
        max(beat_list[index + 1] - beat_list[index], 1e-6)
        for index in range(len(beat_list) - 1)
    ) if len(beat_list) > 1 else 60.0 / float(tempo)

    allin1_result, _seeded_stems = get_allin1_result(paths, stems)
    downbeat_activation = allin1_result.activations["downbeat"]
    scores = _downbeat_scores(beat_list, downbeat_activation, ACTIVATION_RATE_HZ)
    phase_assignment = _phase_assignment(scores)

    # Bar numbers count actual downbeat positions under the chosen phase(s),
    # not `(index - 1) // 4` — that would silently revert to the old modulo
    # grid. A beat before the first window's first downbeat (a leading
    # pickup, at most `BEATS_PER_BAR - 1` beats) has no enclosing bar yet; it
    # is folded into bar 1 rather than given a bar 0 no downstream consumer
    # expects.
    bar_numbers: list[int] = []
    current_bar = 0
    for beat_in_bar, _confidence in phase_assignment:
        if beat_in_bar == 1:
            current_bar += 1
        bar_numbers.append(max(current_bar, 1))

    beats = []
    for index, (beat_time, (beat_in_bar, confidence), bar_number) in enumerate(
        zip(beat_list, phase_assignment, bar_numbers), start=1
    ):
        beats.append(
            BeatPoint(
                index=index,
                time=round(beat_time, 6),
                bar=bar_number,
                beat_in_bar=beat_in_bar,
                type="downbeat" if beat_in_bar == 1 else "beat",
                confidence=confidence,
            )
        )
    downbeat_indexes = [index for index, beat in enumerate(beats) if beat.beat_in_bar == 1]

    bars = []
    for bar_number, beat_index in enumerate(downbeat_indexes, start=1):
        start_s = beats[beat_index].time
        if bar_number < len(downbeat_indexes):
            end_s = beats[downbeat_indexes[bar_number]].time
        else:
            end_s = min(duration, beats[-1].time + median_interval)
        bars.append(BarWindow(bar=bar_number, start_s=round(start_s, 6), end_s=round(end_s, 6)))

    payload = {
        "schema_version": SCHEMA_VERSION,
        **build_song_schema_fields(paths, bpm=tempo, duration=duration),
        "time_signature": "4/4",
        "generated_from": GeneratedFrom(
            source_song_path=str(paths.song_path),
            engine="essentia.RhythmExtractor2013+allin1.downbeat_phase.v1",
        ),
        "tempo": round_schema_float(tempo),
        "beats": beats,
        "bars": bars,
    }
    payload = to_jsonable(payload)
    write_json(paths.artifact("essentia", "beats.json"), payload)
    return payload
