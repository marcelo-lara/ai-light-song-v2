from __future__ import annotations
from typing import Any
from collections import defaultdict
from analyzer.event_contracts import validate_song_event_payload
import re

from analyzer.io import write_json
from analyzer.models import SCHEMA_VERSION
from analyzer.paths import SongPaths

from .utils import *


# v1.1 item 1.2 — drop detection is accumulated weighted evidence against a
# single fixed decision threshold, not a conjunction of song-adaptive thresholds.
# All weights and the threshold are FIXED (not derived from the song's own mean
# and stdev): B2 showed that a track which is mostly drops raises its own bar
# until nothing qualifies.
DROP_EVIDENCE_PROFILE = {
    "name": "stem_relative_weighted_v1",
    "decision_threshold": 0.5,
    "bass_reentry_lookback_beats": 8,
    "min_spacing_seconds": 6.0,
    "weights": {
        "bass_reentry": 0.28,      # bass_stem_rel now, minus its recent floor
        "bass_stem_rel": 0.14,     # absolute stem-relative bass level
        "energy_delta": 0.16,      # positive z-score energy jump
        "spectral_flux_rel": 0.12,
        "onset_density_rel": 0.12,
        "accent_intensity": 0.10,
        "bass_att_ratio": 0.08,    # band-energy re-entry ratio > 1
    },
}


def _drop_evidence(row: dict, recent_rows: list[dict]) -> dict:
    """Per-beat weighted drop evidence. Returns the sub-scores, the contributing
    features with their weights, and the accumulated score."""
    derived = row["derived"]
    bass_stem_rel = float(derived.get("bass_stem_rel", 0.0))
    floor = min(
        (float(candidate["derived"].get("bass_stem_rel", 0.0)) for candidate in recent_rows),
        default=bass_stem_rel,
    )
    sub = {
        "bass_reentry": _clamp01(bass_stem_rel - floor),
        "bass_stem_rel": _clamp01(bass_stem_rel),
        "energy_delta": _clamp01(float(derived.get("energy_delta", 0.0)) / 2.0),
        "spectral_flux_rel": _clamp01(float(derived.get("spectral_flux_rel", 0.0))),
        "onset_density_rel": _clamp01(float(derived.get("onset_density_rel", 0.0))),
        "accent_intensity": _clamp01(float(derived.get("accent_intensity", 0.0))),
        "bass_att_ratio": _clamp01((float(derived.get("bass_att_ratio", 1.0)) - 1.0) / 1.0),
    }
    weights = DROP_EVIDENCE_PROFILE["weights"]
    contributions = [
        {"name": name, "sub_score": round(value, 6), "weight": weights[name],
         "weighted": round(value * weights[name], 6)}
        for name, value in sub.items()
    ]
    score = round(sum(item["weighted"] for item in contributions), 6)
    return {"sub_scores": sub, "contributions": contributions, "score": score}


def generate_rule_candidates(
    paths: SongPaths,
    event_features: dict,
    sections_payload: dict,
    genre_result: dict | None = None,
) -> dict[str, Any]:
    import statistics
    import numpy as np
    from sklearn.cluster import KMeans

    features = [dict(row) for row in event_features.get("features", [])]
    sections = [dict(row) for row in sections_payload.get("sections", [])]

    random_seed = 42

    # K-Means Clustering (Alternative 3) on Beat Features
    if len(features) > 10:
        km_data = np.array([
            [
                float(r["normalized"]["energy_score"]),
                float(r["derived"]["bass_activation_score"]),
                float(r["normalized"]["onset_density"])
            ] for r in features
        ])
        kmeans = KMeans(n_clusters=3, random_state=random_seed, n_init="auto")
        labels = kmeans.fit_predict(km_data)
        
        # Sort cluster IDs by their energy centroid to map Low -> 0, Mid -> 1, High -> 2
        cluster_energies = {i: kmeans.cluster_centers_[i][0] for i in range(3)}
        sorted_clusters = sorted(cluster_energies.keys(), key=lambda k: cluster_energies[k])
        cluster_map = {sorted_clusters[0]: 0, sorted_clusters[1]: 1, sorted_clusters[2]: 2}
        
        for i, row in enumerate(features):
            row["_intensity_cluster"] = cluster_map[labels[i]]
    else:
        for row in features:
            row["_intensity_cluster"] = 2

    def _safe_stat(vals, fn, default=0.0):
        return fn(vals) if len(vals) > 1 else default

    energy_deltas = [float(r["derived"]["energy_delta"]) for r in features]
    mean_energy_delta = _safe_stat(energy_deltas, statistics.mean)
    stdev_energy_delta = _safe_stat(energy_deltas, statistics.stdev)

    tension_means = [float(r["rolling"]["local"]["harmonic_tension_mean"]) for r in features]
    mean_tension = _safe_stat(tension_means, statistics.mean)
    stdev_tension = _safe_stat(tension_means, statistics.stdev)

    energy_means = [float(r["rolling"]["local"]["energy_mean"]) for r in features]
    mean_energy_mean = _safe_stat(energy_means, statistics.mean)
    stdev_energy_mean = _safe_stat(energy_means, statistics.stdev)

    bass_ratios = [max(0.0, float(r["derived"].get("bass_att_ratio", 1.0))) for r in features]
    flux_ratios = [max(0.0, float(r["derived"].get("spectral_flux_ratio", 1.0))) for r in features]
    mean_bass_ratio = _safe_stat(bass_ratios, statistics.mean, default=1.0)
    stdev_bass_ratio = _safe_stat(bass_ratios, statistics.stdev, default=0.0)
    mean_flux_ratio = _safe_stat(flux_ratios, statistics.mean, default=1.0)
    stdev_flux_ratio = _safe_stat(flux_ratios, statistics.stdev, default=0.0)

    # Use dynamically calculated statistical thresholds based on track features
    thresholds = {
        "name": "dynamic_z_score_v1_1",
        "drop_evidence_profile": DROP_EVIDENCE_PROFILE,
        "transition": {
            "build_energy_delta": max(0.04, mean_energy_delta + 1.2 * stdev_energy_delta),
            "build_tension_mean": max(0.15, mean_tension + 0.8 * stdev_tension),
            "build_energy_mean": max(0.25, mean_energy_mean + 0.8 * stdev_energy_mean),
            "breakdown_energy_delta": min(-0.1, mean_energy_delta - 1.2 * stdev_energy_delta),
            "breakdown_density_delta": -0.15,
            # Drop thresholds removed in v1.1 item 1.2 — see DROP_EVIDENCE_PROFILE.
            "fake_drop_tension_mean": max(0.20, mean_tension + 1.0 * stdev_tension),
            "impact_intensity_min": 0.65,
            "impact_ratio_min": max(1.15, mean_flux_ratio + 0.4 * stdev_flux_ratio),
            "pause_gap_seconds": 0.5,
            "pause_energy_max": 0.4
        },
        "state": {
            "groove_energy_min": max(0.30, mean_energy_mean + 0.5 * stdev_energy_mean),
            "groove_bass_min": 0.30,
            "groove_volatility_max": 0.3,
            "atmo_energy_max": max(0.1, mean_energy_mean - 0.5 * stdev_energy_mean),
            "atmo_onset_max": 0.3,
            "atmo_volatility_max": 0.2,
            "tension_mean_min": max(0.3, mean_tension + 0.5 * stdev_tension),
            "no_drop_energy_min": 0.35,
            "no_drop_energy_max": 0.6
        }
    }
    event_counter: defaultdict[str, int] = defaultdict(int)
    events: list[dict[str, Any]] = []

    def next_event_id(event_type: str) -> str:
        event_counter[event_type] += 1
        return f"rule_{event_type}_{event_counter[event_type]:03d}"

    build_anchors = [
        row
        for row in features
        if float(row["derived"]["energy_delta"]) >= thresholds["transition"]["build_energy_delta"]
        and float(row["rolling"]["local"]["harmonic_tension_mean"]) >= thresholds["transition"]["build_tension_mean"]
        and float(row["rolling"]["local"]["energy_mean"]) >= thresholds["transition"]["build_energy_mean"]
        and row.get("_intensity_cluster", 2) >= 1  # Alt 3: Must reach Mid or High energy
    ]
    for rows in _merge_anchor_rows(build_anchors):
        section = _section_for_time(float(rows[0]["start_time"]), sections)
        energy_mean = _mean([float(row["rolling"]["local"]["energy_mean"]) for row in rows])
        tension_mean = _mean([float(row["rolling"]["local"]["harmonic_tension_mean"]) for row in rows])
        events.append(
            _build_event(
                event_id=next_event_id("build"),
                event_type="build",
                rows=rows,
                section=section,
                confidence=_clamp01(0.45 + energy_mean * 0.25 + tension_mean * 0.3),
                intensity=_clamp01(energy_mean),
                summary="Rising short-window energy and harmonic tension indicate an obvious build phase.",
                rule_names=["build_energy_rise"],
                metrics=[
                    {"name": "energy_mean", "value": energy_mean, "threshold": thresholds["transition"]["build_energy_mean"], "comparator": ">=", "source_layer": "event_features"},
                    {"name": "harmonic_tension_mean", "value": tension_mean, "threshold": thresholds["transition"]["build_tension_mean"], "comparator": ">=", "source_layer": "event_features"},
                ],
                notes="Merged consecutive build anchors to preserve the multi-beat rise window.",
                candidates=[{"type": "tension_hold", "confidence": max(0.0, tension_mean - 0.1), "notes": "High tension may also read as a held-state."}],
            )
        )

    breakdown_anchors = [
        row
        for row in features
        if float(row["derived"]["energy_delta"]) <= thresholds["transition"]["breakdown_energy_delta"]
        and float(row["derived"]["density_delta"]) <= thresholds["transition"]["breakdown_density_delta"]
        and row.get("_intensity_cluster", 0) <= 1  # Alt 3: Must drop into Low or Mid
    ]
    for rows in _merge_anchor_rows(breakdown_anchors):
        section = _section_for_time(float(rows[0]["start_time"]), sections)
        energy_drop = abs(_mean([float(row["derived"]["energy_delta"]) for row in rows]))
        density_drop = abs(_mean([float(row["derived"]["density_delta"]) for row in rows]))
        events.append(
            _build_event(
                event_id=next_event_id("breakdown"),
                event_type="breakdown",
                rows=rows,
                section=section,
                confidence=_clamp01(0.45 + energy_drop * 0.3 + density_drop * 0.2),
                intensity=_clamp01(energy_drop),
                summary="Energy and symbolic density both drop sharply across this window.",
                rule_names=["breakdown_dual_drop"],
                metrics=[
                    {"name": "energy_delta", "value": -energy_drop, "threshold": thresholds["transition"]["breakdown_energy_delta"], "comparator": "<=", "source_layer": "event_features"},
                    {"name": "density_delta", "value": -density_drop, "threshold": thresholds["transition"]["breakdown_density_delta"], "comparator": "<=", "source_layer": "event_features"},
                ],
                notes="Breakdown candidates are merged across adjacent negative-delta beats.",
            )
        )

    # v1.1 item 1.2 — weighted-evidence drop detection.
    drop_events: list[dict[str, Any]] = []
    lookback = int(DROP_EVIDENCE_PROFILE["bass_reentry_lookback_beats"])
    decision_threshold = float(DROP_EVIDENCE_PROFILE["decision_threshold"])
    drop_anchor_rows: list[dict] = []
    evidence_by_beat: dict[int, dict] = {}
    for index, row in enumerate(features):
        evidence = _drop_evidence(row, features[max(0, index - lookback):index])
        evidence_by_beat[int(row["beat"])] = evidence
        # A drop raises energy — a pure dropout with high stem-rel is not a drop.
        if evidence["score"] >= decision_threshold and float(row["derived"].get("energy_delta", 0.0)) > 0.0:
            drop_anchor_rows.append(row)

    # Non-maximum suppression: a drop is a rare structural moment, so keep only
    # the highest-scoring anchor inside each min-spacing window.
    min_spacing = float(DROP_EVIDENCE_PROFILE["min_spacing_seconds"])
    drop_anchor_rows.sort(key=lambda r: evidence_by_beat[int(r["beat"])]["score"], reverse=True)
    kept: list[dict] = []
    for row in drop_anchor_rows:
        if all(abs(float(row["start_time"]) - float(other["start_time"])) >= min_spacing for other in kept):
            kept.append(row)
    drop_anchor_rows = sorted(kept, key=lambda r: float(r["start_time"]))

    for rows in _merge_anchor_rows(drop_anchor_rows):
        peak_row = max(rows, key=lambda candidate: evidence_by_beat[int(candidate["beat"])]["score"])
        evidence = evidence_by_beat[int(peak_row["beat"])]
        section = _section_for_time(float(rows[0]["start_time"]), sections)
        # Map [threshold, 1.0] of accumulated score onto [0.55, 0.95] confidence.
        headroom = max(1e-6, 1.0 - decision_threshold)
        confidence = 0.55 + 0.4 * min(1.0, (evidence["score"] - decision_threshold) / headroom)
        intensity = _clamp01(max(
            float(peak_row["normalized"]["energy_score"]),
            float(peak_row["derived"].get("bass_stem_rel", 0.0)),
            float(peak_row["derived"].get("accent_intensity", 0.0)),
        ))
        contributing = [item["name"] for item in evidence["contributions"] if item["weighted"] > 0.0]
        event = _build_event(
            event_id=next_event_id("drop"),
            event_type="drop",
            rows=rows,
            section=section,
            confidence=_clamp01(confidence),
            intensity=intensity,
            summary="Accumulated stem-relative evidence (bass re-entry, energy jump, spectral flux, onset density) crosses the drop decision threshold.",
            rule_names=["drop_weighted_evidence"],
            metrics=[
                {"name": "drop_evidence_score", "value": evidence["score"], "threshold": decision_threshold, "comparator": ">=", "source_layer": "event_features"},
                *[
                    {"name": item["name"], "value": item["sub_score"], "threshold": 0.0, "comparator": ">", "source_layer": "event_features"}
                    for item in evidence["contributions"]
                ],
            ],
            notes=f"Weighted-evidence drop; contributing features: {', '.join(contributing)}.",
            candidates=[{"type": "impact_hit", "confidence": _clamp01(float(peak_row["derived"].get("accent_intensity", 0.0)) + 0.1), "notes": "Short accent overlap suggests an impact reading too."}],
        )
        # Full weighted breakdown (weights + weighted contributions) lives in
        # evidence.metadata, the schema's pass-through slot.
        event["evidence"]["metadata"] = {
            "drop_evidence": {
                "profile": DROP_EVIDENCE_PROFILE["name"],
                "decision_threshold": decision_threshold,
                "score": evidence["score"],
                "contributions": evidence["contributions"],
            }
        }
        drop_events.append(event)
        events.append(event)

    def _is_peak(idx: int, vals: list[float], r: int = 2, min_val: float = 0.0) -> bool:
        val = vals[idx]
        if val < min_val: return False
        start = max(0, idx - r)
        end = min(len(vals), idx + r + 1)
        for i in range(start, end):
            if i == idx: continue
            if vals[i] > val: return False
        return True

    accent_values = [float(row["derived"]["accent_intensity"]) for row in features]
    for i, row in enumerate(features):
        intensity = float(row["derived"]["accent_intensity"])
        ratio_gate = max(
            float(row["derived"].get("spectral_flux_ratio", 1.0)),
            float(row["derived"].get("bass_att_ratio", 1.0)),
        )
        threshold = thresholds["transition"]["impact_intensity_min"]
        if intensity < threshold or ratio_gate < thresholds["transition"]["impact_ratio_min"] or not _is_peak(i, accent_values, r=4, min_val=threshold):
            continue
        section = _section_for_time(float(row["start_time"]), sections)
        events.append(
            _build_event(
                event_id=next_event_id("impact_hit"),
                event_type="impact_hit",
                rows=[row],
                section=section,
                confidence=_clamp01(0.4 + intensity * 0.5),
                intensity=_clamp01(intensity),
                summary="Accent intensity crosses the impact threshold on this beat.",
                rule_names=["impact_accent_peak"],
                metrics=[
                    {"name": "accent_intensity", "value": intensity, "threshold": thresholds["transition"]["impact_intensity_min"], "comparator": ">=", "source_layer": "event_features"},
                    {"name": "impact_support_ratio", "value": ratio_gate, "threshold": thresholds["transition"]["impact_ratio_min"], "comparator": ">=", "source_layer": "event_features"},
                ],
                notes="Impact hits remain single-beat candidates.",
            )
        )

    pause_rows = [
        row
        for row in features
        if float(row["derived"]["silence_gap_seconds"]) >= thresholds["transition"]["pause_gap_seconds"]
        and float(row["normalized"]["energy_score"]) <= thresholds["transition"]["pause_energy_max"]
        and row.get("_intensity_cluster", 0) == 0  # Alt 3: Breaks/Pauses must be in the Low energy cluster
    ]
    for row in pause_rows:
        section = _section_for_time(float(row["start_time"]), sections)
        gap = float(row["derived"]["silence_gap_seconds"])
        events.append(
            _build_event(
                event_id=next_event_id("pause_break"),
                event_type="pause_break",
                rows=[row],
                section=section,
                confidence=_clamp01(0.45 + gap * 0.2),
                intensity=_clamp01(max(0.0, 1.0 - float(row["normalized"]["energy_score"]))),
                summary="Silence gap duration and low energy indicate a pause or stop-time break.",
                rule_names=["pause_gap_low_energy"],
                metrics=[
                    {"name": "silence_gap_seconds", "value": gap, "threshold": thresholds["transition"]["pause_gap_seconds"], "comparator": ">=", "source_layer": "event_features"},
                    {"name": "energy_score", "value": float(row["normalized"]["energy_score"]), "threshold": thresholds["transition"]["pause_energy_max"], "comparator": "<=", "source_layer": "event_features"},
                ],
                notes="Pause candidates are kept even when they may precede a later release.",
                candidates=[{"type": "fake_drop", "confidence": min(0.95, float(row["rolling"]["local"]["harmonic_tension_mean"])), "notes": "Held tension may resolve to a fake drop instead of a true pause."}],
            )
        )

    # v1.1 item 1.3 — fake_drop symmetry. A fake_drop requires POSITIVE evidence
    # of a withheld release: a `build` that ends just before this point (the
    # release was set up) AND no qualifying `drop` in the release window that
    # follows (the release never came). It may no longer fire on a bare
    # low-tension pause, which was easier to satisfy than `drop` itself (B3).
    BUILD_LOOKBACK_SECONDS = 6.0
    RELEASE_WINDOW_SECONDS = 4.0
    build_events = [event for event in events if event["type"] == "build"]
    for row in pause_rows:
        pause_start = float(row["start_time"])
        pause_end = float(row["end_time"])
        preceding_build = next(
            (
                event for event in build_events
                if pause_start - BUILD_LOOKBACK_SECONDS <= float(event["end_time"]) <= pause_start + 1.0
            ),
            None,
        )
        if preceding_build is None:
            continue
        release_present = any(
            pause_end < float(candidate["start_time"]) <= pause_end + RELEASE_WINDOW_SECONDS
            for candidate in drop_events
        )
        if release_present:
            continue
        tension_mean = float(row["rolling"]["local"]["harmonic_tension_mean"])
        section = _section_for_time(pause_start, sections)
        events.append(
            _build_event(
                event_id=next_event_id("fake_drop"),
                event_type="fake_drop",
                rows=[row],
                section=section,
                confidence=_clamp01(0.4 + float(preceding_build["confidence"]) * 0.3 + tension_mean * 0.2),
                intensity=_clamp01(max(tension_mean, float(preceding_build["intensity"]))),
                summary="A build sets up a release, but the expected drop never arrives in the window that follows.",
                rule_names=["fake_drop_withheld_release"],
                metrics=[
                    {"name": "preceding_build_end", "value": float(preceding_build["end_time"]), "threshold": pause_start, "comparator": "<=", "source_layer": "event_features"},
                    {"name": "release_window_drop_count", "value": 0.0, "threshold": 1.0, "comparator": "<", "source_layer": "event_features"},
                    {"name": "harmonic_tension_mean", "value": tension_mean, "threshold": thresholds["transition"]["fake_drop_tension_mean"], "comparator": ">=", "source_layer": "event_features"},
                ],
                notes=f"Withheld-release fake_drop paired with build {preceding_build['id']}.",
                candidates=[{"type": "pause_break", "confidence": 0.5, "notes": "Window also satisfies the baseline pause rule."}],
            )
        )

    build_sections = {event.get("section_id") for event in events if event["type"] == "build"}
    drop_sections = {event.get("section_id") for event in drop_events}
    for section in sections:
        section_rows = _state_section_rows(features, str(section["section_id"]))
        if not section_rows:
            continue
        energy_values = [float(row["normalized"]["energy_score"]) for row in section_rows]
        onset_values = [float(row["normalized"]["onset_density"]) for row in section_rows]
        bass_values = [float(row["derived"]["bass_activation_score"]) for row in section_rows]
        tension_values = [float(row["derived"]["harmonic_tension_proxy"]) for row in section_rows]
        energy_mean = _mean(energy_values)
        onset_mean = _mean(onset_values)
        bass_mean = _mean(bass_values)
        tension_mean = _mean(tension_values)
        energy_volatility = round(max(energy_values) - min(energy_values), 6)
        section_rows_window = [section_rows[0], section_rows[-1]] if len(section_rows) > 1 else section_rows

        if energy_mean >= thresholds["state"]["groove_energy_min"] and bass_mean >= thresholds["state"]["groove_bass_min"] and energy_volatility <= thresholds["state"]["groove_volatility_max"]:
            events.append(
                _build_event(
                    event_id=next_event_id("groove_loop"),
                    event_type="groove_loop",
                    rows=section_rows_window,
                    section=section,
                    confidence=_clamp01(0.45 + energy_mean * 0.2 + bass_mean * 0.2),
                    intensity=_clamp01(energy_mean),
                    summary="Stable section energy and bass activation indicate a sustained groove-loop state.",
                    rule_names=["groove_loop_section_state"],
                    metrics=[
                        {"name": "energy_mean", "value": energy_mean, "threshold": thresholds["state"]["groove_energy_min"], "comparator": ">=", "source_layer": "event_features"},
                        {"name": "bass_mean", "value": bass_mean, "threshold": thresholds["state"]["groove_bass_min"], "comparator": ">=", "source_layer": "event_features"},
                        {"name": "energy_volatility", "value": energy_volatility, "threshold": thresholds["state"]["groove_volatility_max"], "comparator": "<=", "source_layer": "event_features"},
                    ],
                    notes="Section-level sustained-state candidate.",
                )
            )

        if energy_mean <= thresholds["state"]["atmo_energy_max"] and onset_mean <= thresholds["state"]["atmo_onset_max"] and energy_volatility <= thresholds["state"]["atmo_volatility_max"]:
            events.append(
                _build_event(
                    event_id=next_event_id("atmospheric_plateau"),
                    event_type="atmospheric_plateau",
                    rows=section_rows_window,
                    section=section,
                    confidence=_clamp01(0.45 + (1.0 - energy_mean) * 0.2 + (1.0 - onset_mean) * 0.2),
                    intensity=_clamp01(max(0.0, 1.0 - energy_mean)),
                    summary="Low-energy low-motion section profile indicates an atmospheric plateau.",
                    rule_names=["atmospheric_plateau_section_state"],
                    metrics=[
                        {"name": "energy_mean", "value": energy_mean, "threshold": thresholds["state"]["atmo_energy_max"], "comparator": "<=", "source_layer": "event_features"},
                        {"name": "onset_mean", "value": onset_mean, "threshold": thresholds["state"]["atmo_onset_max"], "comparator": "<=", "source_layer": "event_features"},
                    ],
                    notes="Section-level held-state candidate.",
                )
            )

        if tension_mean >= thresholds["state"]["tension_mean_min"] and str(section["section_id"]) not in drop_sections:
            events.append(
                _build_event(
                    event_id=next_event_id("tension_hold"),
                    event_type="tension_hold",
                    rows=section_rows_window,
                    section=section,
                    confidence=_clamp01(0.4 + tension_mean * 0.35),
                    intensity=_clamp01(tension_mean),
                    summary="Sustained harmonic tension stays elevated across the section without a qualifying release.",
                    rule_names=["tension_hold_section_state"],
                    metrics=[
                        {"name": "tension_mean", "value": tension_mean, "threshold": thresholds["state"]["tension_mean_min"], "comparator": ">=", "source_layer": "event_features"},
                    ],
                    notes="Held-state candidate preserved even when overlapping build windows exist.",
                )
            )

        if str(section["section_id"]) in build_sections and str(section["section_id"]) not in drop_sections and thresholds["state"]["no_drop_energy_min"] <= energy_mean <= thresholds["state"]["no_drop_energy_max"]:
            events.append(
                _build_event(
                    event_id=next_event_id("no_drop_plateau"),
                    event_type="no_drop_plateau",
                    rows=section_rows_window,
                    section=section,
                    confidence=_clamp01(0.4 + tension_mean * 0.25 + energy_mean * 0.15),
                    intensity=_clamp01(energy_mean),
                    summary="Build evidence is present, but the section settles into a plateau without a qualifying drop.",
                    rule_names=["no_drop_plateau_unresolved_build"],
                    metrics=[
                        {"name": "energy_mean", "value": energy_mean, "threshold": thresholds["state"]["no_drop_energy_min"], "comparator": ">=", "source_layer": "event_features"},
                        {"name": "tension_mean", "value": tension_mean, "threshold": thresholds["state"]["tension_mean_min"], "comparator": ">=", "source_layer": "event_features"},
                    ],
                    notes="Unresolved-release candidate preserved for later identifier review.",
                )
            )

    events = sorted(events, key=lambda row: (float(row["start_time"]), float(row["end_time"]), str(row["type"])))
    payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": paths.song_name,
        "generated_from": {
            "source_song_path": str(paths.song_path),
            "event_features_file": str(paths.artifact("event_inference", "features.json")),
            "sections_file": str(paths.artifact("section_segmentation", "sections.json")),
            "genre_file": str(paths.artifact("genre.json")) if genre_result is not None else None,
            "engine": "rule-based-event-detection.v2",
            "threshold_profile": thresholds,
            "determinism": {
                "random_engine": "MT19937",
                "seed": random_seed,
            },
        },
        "review_status": "rule_candidates",
        "notes": "Deterministic baseline candidates with explicit evidence and preserved ambiguities.",
        "metadata": {
            "event_count": len(events),
            "genres": list(genre_result.get("genres", [])) if genre_result else [],
        },
        "events": events,
    }
    validated = validate_song_event_payload(payload)
    write_json(paths.artifact("event_inference", "rule_candidates.json"), validated)
    return validated