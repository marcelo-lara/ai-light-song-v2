"""Measure gesture-impact phases against the incumbent event timeline and a
cheap RMS-derivative peak-picker.

    question    Does a gesture built from named sound-design primitives land
                its impact phase where the operator marks a drop impact, more
                often and with better precision than the current event_*
                stack (measured at chance) or a plain peak-picker?
    measurement Recall of the 7 hand-marked drop impacts at +-0.25/0.5/1.0s,
                with gestures/min; per-primitive precision by ear (manual,
                see README); coverage of non-drop hints by any gesture phase.
"""
from __future__ import annotations

import json
import statistics

import numpy as np

from . import export as export_mod, loaders, paths

TOLERANCES = (0.25, 0.5, 1.0)


def _drop_impacts(song: str) -> list[float]:
    return [float(h["start_time"]) for h in loaders.load_hints(song) if str(h.get("title", "")).strip().casefold() == "drop impact"]


def _non_drop_hints(song: str) -> list[dict]:
    return [h for h in loaders.load_hints(song) if not str(h.get("title", "")).strip().casefold().startswith("drop ")]


def _incumbent_impact_times(song: str) -> list[float]:
    path = paths.event_timeline_path(song)
    if not path.exists():
        return []
    events = json.loads(path.read_text())["events"]
    return [float(e["start_time"]) for e in events if e["type"] in ("impact_hit", "drop")]


def _rms_derivative_baseline(song: str) -> list[float]:
    rms = loaders.load_rms_loudness(song)
    mix = rms.values.get("mix")
    if mix is None:
        return []
    deriv = np.diff(mix, prepend=mix[0])
    thresh = np.percentile(deriv, 95)
    peaks = []
    above = deriv >= thresh
    i, n = 0, len(above)
    last_t = -1e9
    while i < n:
        if above[i]:
            j = i
            while j < n and above[j]:
                j += 1
            pk = i + int(np.argmax(deriv[i:j]))
            t = float(rms.times[pk])
            if t - last_t >= 1.0:
                peaks.append(t)
                last_t = t
            i = j
        else:
            i += 1
    return peaks


def _recall(times: list[float], targets: list[float], tol: float) -> int:
    if not times:
        return 0
    return sum(1 for t in targets if any(abs(x - t) <= tol for x in times))


def _per_minute(times: list[float], span: float) -> float:
    return len(times) / (span / 60.0) if span > 0 else 0.0


def impact_recall_table() -> str:
    lines = ["Impact-phase recall vs 7 hand-marked drop impacts", ""]
    header = f"  {'method':<34}" + "".join(f"{'+-' + str(t):>9}" for t in TOLERANCES) + f"{'events/min':>12}"
    lines.append(header)

    agg = {}
    for song in paths.GOLD_SONGS:
        fft = loaders.load_fft_bands(song)
        span = float(fft.times[-1]) if len(fft.times) else 0.0
        impacts_truth = _drop_impacts(song)
        result = export_mod.run_detectors(song)
        gesture_impacts = [g["impact_time"] for g in result["gestures"]]
        incumbent = _incumbent_impact_times(song)
        baseline = _rms_derivative_baseline(song)
        for name, times in (
            ("gesture impact phase", gesture_impacts),
            ("incumbent (song_event_timeline impact/drop)", incumbent),
            ("RMS-derivative peak-picker (baseline)", baseline),
        ):
            agg.setdefault(name, {"hits": {t: 0 for t in TOLERANCES}, "n": 0, "bpm": []})
            for t in TOLERANCES:
                agg[name]["hits"][t] += _recall(times, impacts_truth, t)
            agg[name]["n"] += len(impacts_truth)
            agg[name]["bpm"].append(_per_minute(times, span))

    for name, a in agg.items():
        row = f"  {name:<34}"
        for t in TOLERANCES:
            row += f"{a['hits'][t]:>4}/{a['n']:<4}"
        row += f"{statistics.mean(a['bpm']):>12.2f}"
        lines.append(row)
    return "\n".join(lines)


def non_drop_hint_coverage() -> str:
    lines = ["Non-drop hint coverage — which operator hints a gesture phase overlaps", ""]
    for song in paths.GOLD_SONGS:
        result = export_mod.run_detectors(song)
        gestures = result["gestures"]
        hints = _non_drop_hints(song)
        if not hints:
            continue
        lines.append(f"\n{song}:")
        for h in hints:
            hs, he = float(h["start_time"]), float(h["end_time"])
            covering = []
            for g in gestures:
                for phase_name, ph in g["phases"].items():
                    if ph["start"] <= he and ph["end"] >= hs:
                        covering.append(f"{phase_name}@{ph['start']:.1f}-{ph['end']:.1f}")
            mark = ", ".join(covering) if covering else "MISS"
            lines.append(f"  {h['title'][:30]:<30} {hs:7.2f}-{he:7.2f}  -> {mark}")
    return "\n".join(lines)


def write_report() -> None:
    paths.OUT_ROOT.mkdir(parents=True, exist_ok=True)
    text = "Gestures — score report\n" + "=" * 60 + "\n\n"
    text += impact_recall_table() + "\n\n"
    text += non_drop_hint_coverage() + "\n"
    (paths.OUT_ROOT / "score.txt").write_text(text)
    print(text)
