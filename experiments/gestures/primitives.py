"""One detector per sound-design primitive, each an explicit written rule with
its own confidence — no single global threshold that means different things
per song (thresholds are relative to the song's own levels throughout)."""
from __future__ import annotations

import numpy as np

from . import loaders


def _bar_length(beats: list[dict]) -> float:
    downbeat_times = [b["time"] for b in beats if b.get("type") == "downbeat"]
    if len(downbeat_times) > 1:
        return float(np.median(np.diff(downbeat_times)))
    return 2.0


def _nearest_beat(beats: list[dict], t: float) -> dict | None:
    if not beats:
        return None
    times = np.array([b["time"] for b in beats])
    return beats[int(np.argmin(np.abs(times - t)))]


def _linreg(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """Returns (slope, r_squared)."""
    if len(x) < 3 or np.std(y) < 1e-9:
        return 0.0, 0.0
    slope, intercept = np.polyfit(x, y, 1)
    pred = slope * x + intercept
    ss_res = np.sum((y - pred) ** 2)
    ss_tot = np.sum((y - y.mean()) ** 2)
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 1e-9 else 0.0
    return float(slope), float(max(0.0, r2))


def detect_ramps(fft: loaders.FftBands, beats: list[dict], *, kind: str) -> list[dict]:
    """Riser/uplifter (kind='riser', ascending) or downlifter (kind='downlifter',
    descending) — a near-monotonic ramp in high-band energy over a bar-multiple
    span, no chord change required (this detector does not look at chords)."""
    high = fft.levels[:, (4, 5, 6)].mean(axis=1)
    bar_len = _bar_length(beats)
    span_range = max(high.max() - high.min(), 1e-6)
    sign = 1 if kind == "riser" else -1

    candidates = []
    for n_bars in (2, 4, 8, 16):
        window_s = n_bars * bar_len
        step_s = max(bar_len / 2.0, 0.25)
        t = fft.times[0]
        while t + window_s <= fft.times[-1]:
            idx = (fft.times >= t) & (fft.times < t + window_s)
            if idx.sum() >= 4:
                slope, r2 = _linreg(fft.times[idx], high[idx])
                delta = slope * window_s
                if sign * delta > 0 and r2 >= 0.5 and abs(delta) / span_range >= 0.25:
                    candidates.append({
                        "start": float(t), "end": float(t + window_s),
                        "r2": r2, "delta": abs(delta) / span_range, "n_bars": n_bars,
                    })
            t += step_s

    # Non-max suppression: keep the strongest (highest r2*delta) among overlaps.
    candidates.sort(key=lambda c: c["r2"] * c["delta"], reverse=True)
    kept: list[dict] = []
    for c in candidates:
        if any(not (c["end"] <= k["start"] or c["start"] >= k["end"]) for k in kept):
            continue
        kept.append(c)
    kept.sort(key=lambda c: c["start"])

    out = []
    for c in kept:
        anchor = _nearest_beat(beats, c["end"] if kind == "riser" else c["start"])
        out.append({
            "type": kind,
            "start": round(c["start"], 3),
            "end": round(c["end"], 3),
            "confidence": round(min(1.0, c["r2"] * (0.5 + 0.5 * min(1.0, c["delta"]))), 3),
            "anchor_beat": anchor["beat"] if anchor else None,
            "anchor_bar": anchor["bar"] if anchor else None,
            "evidence": f"high-band r2={c['r2']:.2f} over {c['n_bars']} bars, delta={c['delta']:.2f}x range",
        })
    return out


def detect_reverse_cymbal(fft: loaders.FftBands, rms: loaders.RmsLoudness, beats: list[dict]) -> list[dict]:
    """Amplitude ramp terminating in a transient — envelope rising into a
    transient_strength spike."""
    thresh = np.percentile(fft.transient, 92)
    peaks = _local_peaks(fft.transient, thresh, min_gap=1.0, times=fft.times)
    mix = rms.values.get("mix")
    out = []
    for peak_t, strength in peaks:
        lookback = 3.0
        idx = (fft.times >= peak_t - lookback) & (fft.times <= peak_t)
        if idx.sum() < 4 or mix is None:
            continue
        rms_idx = (rms.times >= peak_t - lookback) & (rms.times <= peak_t)
        if rms_idx.sum() < 4:
            continue
        slope, r2 = _linreg(rms.times[rms_idx], mix[rms_idx])
        if slope > 0 and r2 >= 0.4:
            start = float(rms.times[rms_idx][0])
            anchor = _nearest_beat(beats, peak_t)
            out.append({
                "type": "reverse_cymbal",
                "start": round(start, 3),
                "end": round(float(peak_t), 3),
                "confidence": round(min(1.0, r2 * min(1.0, strength / max(thresh, 1e-6))), 3),
                "anchor_beat": anchor["beat"] if anchor else None,
                "anchor_bar": anchor["bar"] if anchor else None,
                "evidence": f"mix-RMS rise r2={r2:.2f} into transient={strength:.2f}",
            })
    return out


def detect_snare_roll(drum_events: list[dict], beats: list[dict]) -> list[dict]:
    """Onset density from drum_events.json doubling across consecutive bars."""
    bars = sorted({b["bar"] for b in beats})
    if len(bars) < 3:
        return []
    bar_times = {}
    for b in beats:
        if b["bar"] not in bar_times or b["beat"] == 1:
            bar_times[b["bar"]] = b["time"]
    bar_end = {bars[i]: bar_times.get(bars[i + 1], bar_times[bars[i]] + 2.0) for i in range(len(bars) - 1)}
    bar_end[bars[-1]] = bar_times[bars[-1]] + 2.0

    snare_hat_times = sorted(e["time"] for e in drum_events if e.get("event_type") in ("snare", "hat"))
    counts = {}
    for bar in bars:
        t0, t1 = bar_times[bar], bar_end[bar]
        counts[bar] = sum(1 for t in snare_hat_times if t0 <= t < t1)

    out = []
    i = 1
    while i < len(bars):
        prev_bar, cur_bar = bars[i - 1], bars[i]
        prev_c, cur_c = counts[prev_bar], counts[cur_bar]
        if prev_c >= 2 and cur_c >= 1.6 * prev_c:
            j = i
            while j + 1 < len(bars) and counts[bars[j + 1]] >= 1.4 * counts[bars[j]] and counts[bars[j]] > 0:
                j += 1
            start_bar, end_bar = bars[i - 1], bars[min(j + 1, len(bars) - 1)]
            ratio = counts[bars[j]] / max(prev_c, 1)
            anchor = _nearest_beat(beats, bar_end[end_bar])
            out.append({
                "type": "snare_roll",
                "start": round(bar_times[start_bar], 3),
                "end": round(bar_end[end_bar], 3),
                "confidence": round(min(1.0, (ratio - 1.0)), 3),
                "anchor_beat": anchor["beat"] if anchor else None,
                "anchor_bar": anchor["bar"] if anchor else None,
                "evidence": f"onset density {prev_c}->{counts[bars[j]]} across bars {start_bar}-{end_bar}",
            })
            i = j + 2
        else:
            i += 1
    return out


def detect_impacts(fft: loaders.FftBands, beats: list[dict]) -> list[dict]:
    """Simultaneous sub and brilliance transient on a downbeat — the crash-and-
    sub hit that lands the drop."""
    t_thresh = np.percentile(fft.transient, 92)
    sub = fft.levels[:, 0]
    sub_thresh = np.percentile(sub, 70)
    peaks = _local_peaks(fft.transient, t_thresh, min_gap=1.0, times=fft.times)
    out = []
    for peak_t, strength in peaks:
        idx = np.argmin(np.abs(fft.times - peak_t))
        window = slice(max(0, idx - 2), idx + 3)
        if sub[window].max() < sub_thresh:
            continue
        anchor = _nearest_beat(beats, peak_t)
        on_downbeat = anchor is not None and anchor.get("type") == "downbeat"
        out.append({
            "type": "impact",
            "start": round(float(peak_t), 3),
            "end": round(float(peak_t), 3),
            "confidence": round(min(1.0, strength / max(t_thresh, 1e-6)) * (1.0 if on_downbeat else 0.75), 3),
            "anchor_beat": anchor["beat"] if anchor else None,
            "anchor_bar": anchor["bar"] if anchor else None,
            "on_downbeat": on_downbeat,
            "evidence": f"transient={strength:.2f}, sub-band elevated, {'on' if on_downbeat else 'off'} downbeat",
        })
    return out


def detect_pre_drop_gaps(fft: loaders.FftBands, impacts: list[dict], beats: list[dict]) -> list[dict]:
    """One to two beats of near-silence immediately before an impact — a
    dropout_strength spike / broadband RMS collapse."""
    d_thresh = np.percentile(fft.dropout, 85)
    out = []
    for imp in impacts:
        window = (fft.times >= imp["start"] - 2.0) & (fft.times < imp["start"])
        if not window.any():
            continue
        seg_times = fft.times[window]
        seg_dropout = fft.dropout[window]
        if seg_dropout.max() < d_thresh:
            continue
        peak_i = int(np.argmax(seg_dropout))
        peak_t = float(seg_times[peak_i])
        # span: contiguous run around the peak where dropout stays above the
        # 50th percentile of the pre-impact window.
        half_thresh = np.percentile(seg_dropout, 50)
        lo = peak_i
        while lo > 0 and seg_dropout[lo - 1] >= half_thresh:
            lo -= 1
        hi = peak_i
        while hi < len(seg_dropout) - 1 and seg_dropout[hi + 1] >= half_thresh:
            hi += 1
        anchor = _nearest_beat(beats, peak_t)
        out.append({
            "type": "pre_drop_gap",
            "start": round(float(seg_times[lo]), 3),
            "end": round(float(imp["start"]), 3),
            "confidence": round(min(1.0, float(seg_dropout[peak_i]) / max(d_thresh, 1e-6)), 3),
            "anchor_beat": anchor["beat"] if anchor else None,
            "anchor_bar": anchor["bar"] if anchor else None,
            "evidence": f"dropout_strength peak {seg_dropout[peak_i]:.2f} at {peak_t:.2f}s, {imp['start']-peak_t:.2f}s before impact",
        })
    return out


def _local_peaks(values: np.ndarray, threshold: float, *, min_gap: float, times: np.ndarray) -> list[tuple[float, float]]:
    above = values >= threshold
    peaks = []
    i, n = 0, len(values)
    last_t = -1e9
    while i < n:
        if above[i]:
            j = i
            while j < n and above[j]:
                j += 1
            peak_idx = i + int(np.argmax(values[i:j]))
            t = float(times[peak_idx])
            if t - last_t >= min_gap:
                peaks.append((t, float(values[peak_idx])))
                last_t = t
            i = j
        else:
            i += 1
    return peaks
