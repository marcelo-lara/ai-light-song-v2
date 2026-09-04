"""Assemble detected primitives into composite gestures with named internal
phases (approach -> build -> tension -> impact -> release), anchored on each
detected impact. This module explicitly does **not** name the section — it
says "a build of this shape happens here", not "this is the drop"
(constitution §5.2)."""
from __future__ import annotations

import numpy as np


def _bar_len(beats: list[dict]) -> float:
    downbeat_times = [b["time"] for b in beats if b.get("type") == "downbeat"]
    return float(np.median(np.diff(downbeat_times))) if len(downbeat_times) > 1 else 2.0


def assemble(
    impacts: list[dict],
    ramps: list[dict],
    reverse_cymbals: list[dict],
    snare_rolls: list[dict],
    pre_drop_gaps: list[dict],
    beats: list[dict],
    rms_mix_times: np.ndarray,
    rms_mix_values: np.ndarray,
) -> list[dict]:
    bar_len = _bar_len(beats)
    gestures = []
    for impact in impacts:
        t_impact = impact["start"]
        window_start = t_impact - 16 * bar_len

        def in_window(p):
            return window_start <= p["end"] <= t_impact + 0.1

        near_ramps = sorted((p for p in ramps if in_window(p)), key=lambda p: p["end"])
        near_gap = next((g for g in pre_drop_gaps if abs(g["end"] - t_impact) <= 0.15), None)
        near_cymbal = sorted((c for c in reverse_cymbals if in_window(c)), key=lambda c: c["end"])
        near_roll = sorted((r for r in snare_rolls if in_window(r)), key=lambda r: r["end"])

        phases: dict[str, dict] = {}

        # Tension: the pre-drop gap immediately abutting the impact, or (if
        # absent) the closest reverse-cymbal/riser ending within 1 bar.
        if near_gap:
            phases["tension"] = {"start": near_gap["start"], "end": near_gap["end"], "confidence": near_gap["confidence"], "from": "pre_drop_gap"}
        elif near_cymbal and t_impact - near_cymbal[-1]["end"] <= bar_len:
            c = near_cymbal[-1]
            phases["tension"] = {"start": c["start"], "end": c["end"], "confidence": c["confidence"], "from": "reverse_cymbal"}

        tension_start = phases["tension"]["start"] if "tension" in phases else t_impact

        # Build: the riser/snare-roll ending closest to (and before) the
        # tension phase, within 8 bars.
        build_candidates = [p for p in near_ramps if p["end"] <= tension_start + 0.2 and p["type"] == "riser"]
        build_candidates += [r for r in near_roll if r["end"] <= tension_start + 0.2]
        if build_candidates:
            build_candidates.sort(key=lambda p: p["end"])
            b = build_candidates[-1]
            phases["build"] = {"start": b["start"], "end": b["end"], "confidence": b["confidence"], "from": b["type"]}

        build_start = phases["build"]["start"] if "build" in phases else tension_start

        # Approach: an earlier riser/downlifter ending before the build starts.
        approach_candidates = [p for p in near_ramps if p["end"] <= build_start + 0.2]
        if approach_candidates:
            approach_candidates.sort(key=lambda p: p["end"])
            a = approach_candidates[-1]
            if a["end"] <= build_start + 0.2 and a["start"] < build_start:
                phases["approach"] = {"start": a["start"], "end": a["end"], "confidence": a["confidence"], "from": a["type"]}

        phases["impact"] = {"start": t_impact, "end": t_impact, "confidence": impact["confidence"], "from": "impact"}

        # Release: does the mix RMS stay elevated (above its own pre-impact
        # trough) for the 2 bars after the impact? If not, omit — never guess.
        post_idx = (rms_mix_times >= t_impact) & (rms_mix_times <= t_impact + 2 * bar_len)
        pre_idx = (rms_mix_times >= t_impact - bar_len) & (rms_mix_times < t_impact)
        if post_idx.any() and pre_idx.any():
            post_level = float(np.median(rms_mix_values[post_idx]))
            pre_level = float(np.median(rms_mix_values[pre_idx]))
            if post_level >= pre_level * 0.9:
                conf = float(np.clip((post_level - pre_level) / max(pre_level, 1e-6), 0.0, 1.0))
                phases["release"] = {
                    "start": t_impact, "end": round(t_impact + 2 * bar_len, 3),
                    "confidence": round(0.5 + 0.5 * conf, 3), "from": "post-impact RMS plateau",
                }

        if "approach" in phases:
            span_start = phases["approach"]["start"]
        elif "build" in phases:
            span_start = phases["build"]["start"]
        elif "tension" in phases:
            span_start = phases["tension"]["start"]
        else:
            span_start = t_impact
        span_end = phases["release"]["end"] if "release" in phases else t_impact

        gestures.append({
            "start": round(span_start, 3),
            "end": round(span_end, 3),
            "impact_time": round(t_impact, 3),
            "phases": phases,
            "confidence": impact["confidence"],
        })
    return gestures
