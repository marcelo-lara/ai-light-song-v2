"""Measure reactive-band accents against the incumbent normalisation and a
cheap baseline.

    question    Does an accent detector built on locally auto-gained band
                power find the operator's drop impacts better — especially
                inside quiet passages — than the *same* detector run on the
                incumbent's whole-song-percentile normalisation?
    measurement Recall of the 7 hand-marked drop impacts at +-0.25/0.5/1.0 s,
                reported with accents/min.
    incumbent   Identical accent detector, `bands.percentile_ratio` in place
                of the local running-mean ratio.
    baseline    Thresholded raw per-stem RMS from `rms_loudness.json` — no
                band split, no auto-gain.
"""
from __future__ import annotations

import json
import statistics

import numpy as np

from . import accents as accents_mod
from . import aggregate, bands, paths, pipeline

TOLERANCES = (0.25, 0.5, 1.0)


def _drop_impacts(song: str) -> list[float]:
    path = paths.hints_path(song)
    if not path.exists():
        return []
    rows = json.loads(path.read_text())["human_hints"]
    return [float(h["start_time"]) for h in rows if str(h.get("title", "")).strip().casefold() == "drop impact"]


def _recall(times: list[float], targets: list[float], tol: float) -> int:
    if not times:
        return 0
    return sum(1 for t in targets if any(abs(x - t) <= tol for x in times))


def _per_minute(times: list[float], span: float) -> float:
    return len(times) / (span / 60.0) if span > 0 else 0.0


def _rms_baseline(song: str, threshold_ratio: float = 1.5) -> list[float]:
    """Thresholded raw per-stem RMS from rms_loudness.json — no band split,
    no auto-gain. Uses the drums stem, the one most tied to an impact."""
    data = json.loads(paths.rms_loudness_path(song).read_text())
    idx = [s["id"] for s in data["sources"]].index("drums")
    values = np.array([f["values"][idx] for f in data["frames"]])
    times = np.array([f["time"] for f in data["frames"]])
    thresh = float(np.median(values[values > 0])) * threshold_ratio if (values > 0).any() else 0.0
    above = values >= thresh
    out = []
    i, n = 0, len(above)
    while i < n:
        if above[i]:
            j = i
            while j < n and above[j]:
                j += 1
            peak = i + int(np.argmax(values[i:j]))
            out.append(float(times[peak]))
            i = j
        else:
            i += 1
    return out


def _accent_times_for(song: str, source: str, band: str, window_s: float, ratio_fn, threshold: float = 2.0) -> tuple[list[float], float]:
    bp = pipeline.load_cache(song, source)
    power = bp.power_3[band]
    if ratio_fn == "local":
        inst, att = pipeline.ratios_for_band(power, window_s=window_s)
    else:
        inst = bands.percentile_ratio(power)
        att = bands.ema(inst, pipeline.ema_alpha_for_tau(pipeline.DEFAULT_DAMPING_TAU_S))
    acc = accents_mod.find_accents(bp.times, inst, att, aggregate.load_beats(song), band, threshold=threshold)
    span = float(bp.times[-1]) if len(bp.times) else 0.0
    return [a["time"] for a in acc], span


def threshold_sweep_table() -> str:
    """Accent threshold calibration: the excess-over-damped-twin cutoff trades
    recall against accents/min almost linearly. 0.5 (the first value tried)
    fires ~90/min — useless as a discrete accent list; this sweep is what
    picked the shipped default (2.0)."""
    lines = ["Accent-threshold calibration — bass band, mix source, local (2s) normalisation", ""]
    lines.append(f"  {'threshold':<10}{'hits @0.5':>12}{'hits @1.0':>12}{'accents/min avg':>18}")
    for thresh in (0.5, 0.8, 1.0, 1.3, 1.6, 2.0, 2.5, 3.0, 4.0, 5.0):
        hits5 = hits10 = n = 0
        bpms = []
        for song in paths.GOLD_SONGS:
            impacts = _drop_impacts(song)
            times, span = _accent_times_for(song, "mix", "bass", pipeline.DEFAULT_WINDOW_S, "local", threshold=thresh)
            hits5 += _recall(times, impacts, 0.5)
            hits10 += _recall(times, impacts, 1.0)
            n += len(impacts)
            bpms.append(_per_minute(times, span))
        marker = "  <- shipped default" if thresh == 2.0 else ""
        lines.append(f"  {thresh:<10}{hits5:>6}/{n:<5}{hits10:>6}/{n:<5}{statistics.mean(bpms):>18.2f}{marker}")
    return "\n".join(lines)


def window_sweep_table() -> str:
    lines = ["Window sweep — bass-band accents vs. 7 drop impacts, mix source", ""]
    header = f"  {'window_s':<10}{'hits @0.5':>12}{'accents/min avg':>18}"
    lines.append(header)
    for w in pipeline.WINDOW_CANDIDATES_S:
        total_hits = 0
        total_impacts = 0
        bpms = []
        for song in paths.GOLD_SONGS:
            impacts = _drop_impacts(song)
            times, span = _accent_times_for(song, "mix", "bass", w, "local")
            total_hits += _recall(times, impacts, 0.5)
            total_impacts += len(impacts)
            bpms.append(_per_minute(times, span))
        lines.append(f"  {w:<10}{total_hits:>6}/{total_impacts:<5}{statistics.mean(bpms):>18.2f}")

    # Bar-length window, per-song.
    lines.append("\n  bar-length window (per-song median bar duration):")
    total_hits = 0
    total_impacts = 0
    bpms = []
    for song in paths.GOLD_SONGS:
        beats = aggregate.load_beats(song)
        downbeats = [b["time"] for b in beats if b.get("type") == "downbeat"]
        bar_len = float(np.median(np.diff(downbeats))) if len(downbeats) > 1 else 2.0
        impacts = _drop_impacts(song)
        times, span = _accent_times_for(song, "mix", "bass", bar_len, "local")
        total_hits += _recall(times, impacts, 0.5)
        total_impacts += len(impacts)
        bpms.append(_per_minute(times, span))
    lines.append(f"  {'bar-len':<10}{total_hits:>6}/{total_impacts:<5}{statistics.mean(bpms):>18.2f}")
    return "\n".join(lines)


def _accents_at_target_rate(song: str, kind: str, target_per_min: float, band: str = "bass") -> tuple[list[float], float]:
    """Binary-search the accent threshold so both normalisations are compared
    at a matched accents/min budget. A **shared absolute threshold is not a
    fair comparison here** — local ratio is unbounded (power/running-mean) and
    the incumbent's percentile ratio is clipped to [0, 2], so a fixed cutoff
    like 2.0 makes the percentile curve fire ~0 accents regardless of how good
    its normalisation is. This was caught during the run (see README) and
    replaced with budget matching, which is the only fair comparison."""
    bp = pipeline.load_cache(song, "mix")
    power = bp.power_3[band]
    if kind == "local":
        inst, att = pipeline.ratios_for_band(power, window_s=pipeline.DEFAULT_WINDOW_S)
    else:
        inst = bands.percentile_ratio(power)
        att = bands.ema(inst, pipeline.ema_alpha_for_tau(pipeline.DEFAULT_DAMPING_TAU_S))
    excess = inst - att
    span = float(bp.times[-1]) if len(bp.times) else 0.0
    target_n = max(1, int(round(target_per_min * span / 60)))
    beats = aggregate.load_beats(song)
    lo, hi = float(excess.min()), float(excess.max())
    best: list[dict] = []
    for _ in range(25):
        mid = (lo + hi) / 2
        acc = accents_mod.find_accents(bp.times, inst, att, beats, band, threshold=mid)
        if len(acc) > target_n:
            lo = mid
        else:
            hi = mid
        best = acc
    return [a["time"] for a in best], span


def normalization_ablation_table(target_rate: float = 29.0) -> str:
    lines = [
        "Normalisation ablation — local running mean vs. whole-song percentile,",
        f"BUDGET-MATCHED at ~{target_rate}/min each (a shared absolute threshold is not a",
        "fair comparison — see docstring on _accents_at_target_rate). This replaced an",
        "earlier fixed-threshold version that made the percentile curve fire ~0",
        "accents purely because its scale is clipped to [0, 2] — an artifact of the",
        "threshold, not a finding about the normalisation.",
        "",
    ]
    header = f"  {'normalisation':<40}" + "".join(f"{'+-' + str(t):>9}" for t in TOLERANCES) + f"{'accents/min':>13}"
    lines.append(header)

    low_loudness_impacts: dict[str, list[float]] = {}
    for song in paths.GOLD_SONGS:
        bp = pipeline.load_cache(song, "mix")
        total_power = bp.power_3["bass"] + bp.power_3["mid"] + bp.power_3["treb"]
        pct = bands.percentile_ratio(total_power)
        low_mask_times = bp.times[pct < 0.67]
        impacts = _drop_impacts(song)
        low_loudness_impacts[song] = [i for i in impacts if any(abs(t - i) < 1.0 for t in low_mask_times)]
    n_low = sum(len(v) for v in low_loudness_impacts.values())

    for label, kind in (("local running mean (2s)", "local"), ("whole-song percentile (incumbent)", "pct")):
        for restrict, tag in ((False, "all impacts"), (True, f"impacts in low-loudness passages (n={n_low})")):
            total_hits = {t: 0 for t in TOLERANCES}
            total_impacts = 0
            bpms = []
            for song in paths.GOLD_SONGS:
                impacts = low_loudness_impacts[song] if restrict else _drop_impacts(song)
                times, span = _accents_at_target_rate(song, kind, target_rate)
                for t in TOLERANCES:
                    total_hits[t] += _recall(times, impacts, t)
                total_impacts += len(impacts)
                bpms.append(_per_minute(times, span))
            row = f"  {label + ' — ' + tag:<58}"
            for t in TOLERANCES:
                row += f"{total_hits[t]:>4}/{total_impacts:<4}"
            row += f"{statistics.mean(bpms):>13.2f}"
            lines.append(row)
    if n_low <= 3:
        lines.append(f"\n  NOTE: only {n_low} drop impacts fall in a low-loudness passage across the")
        lines.append("  gold set — too few to resolve the low-loudness hypothesis either way. This")
        lines.append("  is the constitution §3 noise-floor case: more hand-marked low-loudness")
        lines.append("  impacts are needed before this specific claim can be tested, not more tuning.")
    return "\n".join(lines)


def baseline_table() -> str:
    lines = ["Cheap baseline — thresholded raw drums-stem RMS (no band split, no auto-gain)", ""]
    header = f"  {'method':<32}" + "".join(f"{'+-' + str(t):>9}" for t in TOLERANCES) + f"{'accents/min':>13}"
    lines.append(header)
    for label, fn in (
        ("reactive-bands accents (bass, mix)", lambda s: _accent_times_for(s, "mix", "bass", pipeline.DEFAULT_WINDOW_S, "local")),
        ("drums-RMS threshold baseline", lambda s: (_rms_baseline(s), None)),
    ):
        total_hits = {t: 0 for t in TOLERANCES}
        total_impacts = 0
        bpms = []
        for song in paths.GOLD_SONGS:
            impacts = _drop_impacts(song)
            times, span = fn(song)
            if span is None:
                data = json.loads(paths.rms_loudness_path(song).read_text())
                span = data["frames"][-1]["time"] if data["frames"] else 0.0
            for t in TOLERANCES:
                total_hits[t] += _recall(times, impacts, t)
            total_impacts += len(impacts)
            bpms.append(_per_minute(times, span))
        row = f"  {label:<32}"
        for t in TOLERANCES:
            row += f"{total_hits[t]:>4}/{total_impacts:<4}"
        row += f"{statistics.mean(bpms):>13.2f}"
        lines.append(row)
    return "\n".join(lines)


def write_report() -> None:
    paths.OUT_ROOT.mkdir(parents=True, exist_ok=True)
    text = "Reactive band dynamics — score report\n" + "=" * 60 + "\n\n"
    text += threshold_sweep_table() + "\n\n"
    text += window_sweep_table() + "\n\n"
    text += normalization_ablation_table() + "\n\n"
    text += baseline_table() + "\n"
    (paths.OUT_ROOT / "score.txt").write_text(text)
    print(text)
