"""compute — item 5/6c candidate producer: `rhythm.vocals` +
`onsets_per_beat` from word-onset times, not autocorrelation of a continuous
curve.

Reuses `experiments.acestep_transcriber.whisper_baseline` — whisper-large-v3
word timestamps over the vocal stem (`artifacts/stems/vocals.wav`), already
built and cached by that experiment (item 3). Word `t` timestamps are used
directly as syllable-onset proxies: dominant inter-onset interval of the
words inside a span / local beat period -> nearest subdivision, same
vocabulary and confidence rule as `rhythm_drum_ioi`
(`rhythm_energy_common.subdivision_from_ratio`). `onsets_per_beat` = word
count in the span / (span duration / beat period).

**Must run in the ACE-Step sandbox image**
(`experiments/acestep_transcriber/run_in_container.sh`) — `faster_whisper`
is not installed in the `app` image this repo's normal `./experiment` queue
runner uses. `queue.toml` marks this experiment's `image` as something the
runner never honors (matching `svd_tagger`'s precedent), so the queue always
records it `skipped`; that is expected, not a bug.

No silent fallbacks: a span with no usable beat grid, or fewer than 2 word
onsets in it, is omitted.
"""
from __future__ import annotations

import json

from experiments.acestep_transcriber import whisper_baseline
from experiments.rhythm_energy_common import dominant_ioi_ratio, subdivision_from_ratio
from experiments.segment_seeds import features as seed_features

from . import paths


def _word_onsets(song: str) -> list[float]:
    data = whisper_baseline.load(song)
    onsets = [
        float(w["t"])
        for line in data.get("lines", [])
        for w in line.get("words", [])
    ]
    return sorted(onsets)


def compute(song: str) -> list[dict]:
    beats = seed_features.load_json(paths.beats_path(song))
    onsets = _word_onsets(song)

    rows: list[dict] = []
    for span in paths.spans(song):
        start, end = span["start"], span["end"]
        beat_period = seed_features.beat_period_near(beats, start, end)
        if not beat_period or beat_period <= 0:
            continue
        span_onsets = [t for t in onsets if start <= t < end]
        n_beats = (end - start) / beat_period
        onsets_per_beat = round(len(span_onsets) / n_beats, 3) if n_beats > 0 else None
        if len(span_onsets) < 2:
            continue
        ratio = dominant_ioi_ratio(span_onsets, beat_period)
        if ratio is None:
            continue
        name, conf = subdivision_from_ratio(ratio)
        rows.append({
            "start_s": round(start, 3),
            "end_s": round(end, 3),
            "subdivisions": {"vocals": name},
            "confidence": {"vocals": conf},
            "onsets_per_beat": onsets_per_beat,
        })
    return rows


def compute_and_cache(song: str) -> list[dict]:
    rows = compute(song)
    path = paths.cache_path(song)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2) + "\n")
    return rows


def load_cache(song: str) -> list[dict]:
    path = paths.cache_path(song)
    if not path.exists():
        return compute_and_cache(song)
    return json.loads(path.read_text())
