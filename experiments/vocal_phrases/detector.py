"""Vocal-activity envelope, phrase segmentation, breath splits, sustained notes.

No model. Reads only `artifacts/stems/vocals.wav`, trusted phase-1 output.
Normalisation is **local** — a running mean of the stem's own recent level —
not a whole-song percentile, for the same reason the reactive-bands entry
gives: a quiet breakdown must not read as silence relative to a loud chorus
elsewhere in the same song.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass

import librosa
import numpy as np

from . import paths

HOP_LENGTH = 512  # ~11.6 ms at 44100 Hz
FRAME_LENGTH = 2048
EPS = 1e-9

# Hysteresis thresholds on (instantaneous RMS) / (running mean RMS).
ON_RATIO = 1.4
OFF_RATIO = 0.9
RUNNING_MEAN_WINDOW_S = 2.0  # local auto-gain window
MIN_PHRASE_S = 0.15          # drop blips shorter than this
DEFAULT_BREATH_S = 0.5       # within-phrase silence -> split (swept in score.py)
DEFAULT_SUSTAIN_S = 1.5      # min duration for a sustained-note marker (swept)
PITCH_TOLERANCE_CENTS = 60.0  # median-filtered f0 must stay within this band


@dataclass
class Envelope:
    song: str
    sr: int
    hop_length: int
    times: list[float]
    rms: list[float]
    running_mean: list[float]
    ratio: list[float]
    f0_hz: list[float]  # 0.0 where unvoiced/unreliable


def _running_mean(x: np.ndarray, window_frames: int) -> np.ndarray:
    """Centred running mean via cumulative sum; window in frames, odd-sized."""
    if window_frames < 1:
        return x.copy()
    half = window_frames // 2
    padded = np.pad(x, (half, half), mode="edge")
    csum = np.cumsum(np.insert(padded, 0, 0.0))
    out = (csum[window_frames:] - csum[:-window_frames]) / float(window_frames)
    return out[: len(x)]


def compute_envelope(song: str) -> Envelope:
    """Load the vocal stem and compute the local-auto-gain RMS envelope + f0."""
    path = paths.vocals_stem_path(song)
    y, sr = librosa.load(str(path), sr=None, mono=True)

    rms = librosa.feature.rms(y=y, frame_length=FRAME_LENGTH, hop_length=HOP_LENGTH)[0]
    times = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=HOP_LENGTH)

    window_frames = max(1, int(round(RUNNING_MEAN_WINDOW_S * sr / HOP_LENGTH)))
    if window_frames % 2 == 0:
        window_frames += 1
    running_mean = _running_mean(rms, window_frames)
    ratio = rms / (running_mean + EPS)

    # f0 via pYIN, restricted to a singing-voice range (C2..C7). Frames pYIN
    # marks unvoiced come back as NaN; we store 0.0 for "no reliable pitch".
    f0, voiced_flag, _voiced_prob = librosa.pyin(
        y,
        fmin=librosa.note_to_hz("C2"),
        fmax=librosa.note_to_hz("C7"),
        sr=sr,
        frame_length=FRAME_LENGTH,
        hop_length=HOP_LENGTH,
    )
    f0 = np.nan_to_num(f0, nan=0.0)
    f0 = np.where(voiced_flag, f0, 0.0)
    # pyin's frame count can differ by one from rms's depending on centering;
    # align by truncating to the shorter length.
    n = min(len(rms), len(f0), len(times))

    return Envelope(
        song=song,
        sr=int(sr),
        hop_length=HOP_LENGTH,
        times=times[:n].tolist(),
        rms=rms[:n].tolist(),
        running_mean=running_mean[:n].tolist(),
        ratio=ratio[:n].tolist(),
        f0_hz=f0[:n].tolist(),
    )


def save_envelope(env: Envelope) -> None:
    paths.CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    paths.cache_path(env.song).write_text(json.dumps(asdict(env)))


def load_envelope(song: str) -> Envelope:
    raw = json.loads(paths.cache_path(song).read_text())
    return Envelope(**raw)


def _hysteresis_active(ratio: np.ndarray, on: float, off: float) -> np.ndarray:
    """Standard two-threshold (Schmitt-trigger) gate over the ratio curve."""
    active = np.zeros(len(ratio), dtype=bool)
    state = False
    for i, r in enumerate(ratio):
        if not state and r >= on:
            state = True
        elif state and r <= off:
            state = False
        active[i] = state
    return active


def _runs(active: np.ndarray, times: list[float]) -> list[tuple[float, float]]:
    spans: list[tuple[float, float]] = []
    start = None
    for i, a in enumerate(active):
        if a and start is None:
            start = times[i]
        elif not a and start is not None:
            spans.append((start, times[i]))
            start = None
    if start is not None:
        spans.append((start, times[-1]))
    return spans


def _cents_range(f0_run: np.ndarray) -> float:
    voiced = f0_run[f0_run > 0]
    if len(voiced) < 2:
        return 0.0
    lo, hi = voiced.min(), voiced.max()
    return 1200.0 * np.log2(hi / lo)


def derive_phrases(
    env: Envelope,
    *,
    on_ratio: float = ON_RATIO,
    off_ratio: float = OFF_RATIO,
    breath_s: float = DEFAULT_BREATH_S,
    sustain_s: float = DEFAULT_SUSTAIN_S,
    min_phrase_s: float = MIN_PHRASE_S,
) -> dict:
    """Turn the envelope into vocal_phrase / instrumental_gap / sustained_note blocks.

    The hysteresis gate alone closes on every inter-word silence (~0.1 s), far
    below the breath threshold. So the pipeline is: gate at word granularity,
    then **merge** consecutive active runs whose gap is shorter than
    `breath_s` into one phrase. A phrase's boundary is therefore, by
    construction, exactly the set of silences that survive at >= breath_s —
    which is the breath split the plan asks for, expressed as a merge rather
    than a split.
    """
    times = np.array(env.times)
    ratio = np.array(env.ratio)
    f0 = np.array(env.f0_hz)
    active = _hysteresis_active(ratio, on_ratio, off_ratio)
    word_spans = [s for s in _runs(active, env.times)]

    # Merge word-level runs into phrases: glue if the gap to the next run is
    # shorter than breath_s.
    phrase_spans: list[tuple[float, float]] = []
    for (s, e) in word_spans:
        if phrase_spans and s - phrase_spans[-1][1] < breath_s:
            phrase_spans[-1] = (phrase_spans[-1][0], e)
        else:
            phrase_spans.append((s, e))
    phrase_spans = [sp for sp in phrase_spans if sp[1] - sp[0] >= min_phrase_s]

    phrases = []
    for (s, e) in phrase_spans:
        idx = (times >= s) & (times <= e)
        seg_ratio = ratio[idx]
        conf = float(np.clip((seg_ratio.mean() - off_ratio) / max(on_ratio - off_ratio, EPS), 0.0, 1.0))
        phrases.append({
            "start": round(float(s), 3),
            "end": round(float(e), 3),
            "confidence": round(conf, 3),
        })

    # instrumental gaps: the complement of the merged phrase spans.
    gaps = []
    prev_end = 0.0
    total_end = env.times[-1] if env.times else 0.0
    for (s, e) in phrase_spans:
        if s - prev_end >= min_phrase_s:
            gaps.append({"start": round(prev_end, 3), "end": round(s, 3), "confidence": 1.0})
        prev_end = e
    if total_end - prev_end >= min_phrase_s:
        gaps.append({"start": round(prev_end, 3), "end": round(total_end, 3), "confidence": 1.0})

    raw_spans = phrase_spans  # sustained-note pass below scans within phrases

    # sustained notes: within active regions, runs where median-filtered f0
    # stays inside PITCH_TOLERANCE_CENTS for >= sustain_s.
    sustained = []
    hop_s = env.hop_length / env.sr
    kernel = max(1, int(round(0.05 / hop_s)))  # ~50ms median filter
    if kernel % 2 == 0:
        kernel += 1
    from scipy.signal import medfilt
    f0_smooth = medfilt(f0, kernel_size=kernel) if len(f0) > kernel else f0

    for (s, e) in raw_spans:
        idx = np.where((times >= s) & (times <= e))[0]
        if len(idx) < 2:
            continue
        run_start_i = idx[0]
        anchor = None
        for i in idx:
            v = f0_smooth[i]
            if v <= 0:
                if anchor is not None:
                    dur = times[i - 1] - times[run_start_i]
                    if dur >= sustain_s:
                        sustained.append(_sustained_entry(times, f0_smooth, run_start_i, i - 1))
                anchor = None
                run_start_i = i + 1 if i + 1 < len(times) else i
                continue
            if anchor is None:
                anchor = v
                run_start_i = i
                continue
            cents = abs(1200.0 * np.log2(v / anchor))
            if cents > PITCH_TOLERANCE_CENTS:
                dur = times[i - 1] - times[run_start_i]
                if dur >= sustain_s:
                    sustained.append(_sustained_entry(times, f0_smooth, run_start_i, i - 1))
                anchor = v
                run_start_i = i
        if anchor is not None and idx[-1] > run_start_i:
            dur = times[idx[-1]] - times[run_start_i]
            if dur >= sustain_s:
                sustained.append(_sustained_entry(times, f0_smooth, run_start_i, idx[-1]))

    return {
        "vocal_phrases": phrases,
        "instrumental_gaps": gaps,
        "sustained_notes": sustained,
        "params": {
            "on_ratio": on_ratio,
            "off_ratio": off_ratio,
            "breath_s": breath_s,
            "sustain_s": sustain_s,
            "min_phrase_s": min_phrase_s,
            "running_mean_window_s": RUNNING_MEAN_WINDOW_S,
        },
    }


def _sustained_entry(times: np.ndarray, f0: np.ndarray, i0: int, i1: int) -> dict:
    seg = f0[i0:i1 + 1]
    seg = seg[seg > 0]
    note_hz = float(np.median(seg)) if len(seg) else 0.0
    return {
        "start": round(float(times[i0]), 3),
        "end": round(float(times[i1]), 3),
        "note_hz": round(note_hz, 2),
        "confidence": round(min(1.0, (times[i1] - times[i0]) / (DEFAULT_SUSTAIN_S * 2)), 3),
    }
