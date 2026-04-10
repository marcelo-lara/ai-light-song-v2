from __future__ import annotations

import numpy as np

from analyzer.exceptions import AnalysisError, DependencyError
from analyzer.io import write_json
from analyzer.models import EnergyBeat, EnergyFrame, GeneratedFrom, SCHEMA_VERSION, to_jsonable
from analyzer.paths import SongPaths


def _section_for_time(time_s: float, sections: list[dict]) -> dict | None:
    for section in sections:
        if float(section["start"]) <= time_s < float(section["end"]):
            return section
    if sections and time_s >= float(sections[-1]["start"]):
        return sections[-1]
    return None


def _energy_score(beat_row: dict) -> float:
    return (
        (float(beat_row["loudness_avg"]) * 0.5)
        + (float(beat_row["flux_avg"]) * 0.25)
        + (float(beat_row["onset_density"]) * 0.25)
    )


def _trend_label(values: list[float]) -> str:
    if not values:
        return "flat"
    if len(values) < 3:
        delta = values[-1] - values[0]
    else:
        chunk = max(1, len(values) // 3)
        delta = float(np.mean(values[-chunk:]) - np.mean(values[:chunk]))
    spread = max(values) - min(values)
    if delta >= 0.08:
        return "build"
    if delta <= -0.08:
        return "release"
    if spread <= 0.08:
        return "plateau"
    return "wave"


def _level_label(value: float, low_threshold: float, high_threshold: float) -> str:
    if value >= high_threshold:
        return "high"
    if value <= low_threshold:
        return "low"
    return "medium"


def extract_energy_features(paths: SongPaths, timing: dict) -> dict:
    try:
        from essentia.standard import FrameGenerator, MonoLoader, Spectrum, Windowing
    except ImportError as exc:
        raise DependencyError("essentia is required for energy feature extraction") from exc

    sample_rate = 44100
    frame_size = 2048
    hop_size = 512
    audio = MonoLoader(filename=str(paths.song_path), sampleRate=sample_rate)()
    windowing = Windowing(type="hann")
    spectrum = Spectrum(size=frame_size)

    raw_rows: list[dict[str, float]] = []
    previous_magnitude = None
    frequencies = np.fft.rfftfreq(frame_size, d=1.0 / sample_rate)
    for frame_index, frame in enumerate(FrameGenerator(audio, frameSize=frame_size, hopSize=hop_size, startFromZero=True)):
        spec = np.asarray(spectrum(windowing(frame)), dtype=float)
        magnitude_sum = float(spec.sum())
        loudness = float(np.sqrt(np.mean(np.square(frame))))
        centroid = float((frequencies * spec).sum() / magnitude_sum) if magnitude_sum > 0 else 0.0
        normalized = spec / max(magnitude_sum, 1e-8)
        if previous_magnitude is None:
            flux = 0.0
        else:
            flux = float(np.linalg.norm(normalized - previous_magnitude))
        previous_magnitude = normalized
        onset_strength = float(max(flux, loudness))
        raw_rows.append({
            "time": frame_index * hop_size / sample_rate,
            "frame_index": frame_index,
            "loudness": loudness,
            "spectral_centroid": centroid,
            "spectral_flux": flux,
            "onset_strength": onset_strength,
        })

    if not raw_rows:
        raise AnalysisError("No energy frames were extracted from the source song")

    loudness_values = np.array([row["loudness"] for row in raw_rows], dtype=float)
    centroid_values = np.array([row["spectral_centroid"] for row in raw_rows], dtype=float)
    flux_values = np.array([row["spectral_flux"] for row in raw_rows], dtype=float)
    onset_values = np.array([row["onset_strength"] for row in raw_rows], dtype=float)

    def normalize(values: np.ndarray) -> np.ndarray:
        minimum = float(values.min())
        maximum = float(values.max())
        if maximum - minimum < 1e-8:
            return np.zeros_like(values)
        return (values - minimum) / (maximum - minimum)

    loudness_norm = normalize(loudness_values)
    centroid_norm = normalize(centroid_values)
    flux_norm = normalize(flux_values)
    onset_norm = normalize(onset_values)

    frames = [
        EnergyFrame(
            time=round(float(row["time"]), 6),
            frame_index=int(row["frame_index"]),
            loudness=round(float(loudness_norm[index]), 6),
            spectral_centroid=round(float(centroid_values[index]), 6),
            spectral_flux=round(float(flux_norm[index]), 6),
            onset_strength=round(float(onset_norm[index]), 6),
        )
        for index, row in enumerate(raw_rows)
    ]

    beat_times = [beat["time"] for beat in timing["beats"]]
    beat_rows: list[EnergyBeat] = []
    for index, beat_time in enumerate(beat_times):
        next_time = beat_times[index + 1] if index + 1 < len(beat_times) else frames[-1].time + (hop_size / sample_rate)
        selected = [frame for frame in frames if beat_time <= frame.time < next_time]
        if not selected:
            selected = [min(frames, key=lambda frame: abs(frame.time - beat_time))]
        beat_rows.append(
            EnergyBeat(
                beat=index + 1,
                time=round(float(beat_time), 6),
                loudness_avg=round(float(np.mean([frame.loudness for frame in selected])), 6),
                centroid_avg=round(float(np.mean([frame.spectral_centroid for frame in selected])), 6),
                flux_avg=round(float(np.mean([frame.spectral_flux for frame in selected])), 6),
                onset_density=round(float(np.mean([frame.onset_strength for frame in selected])), 6),
            )
        )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": paths.song_name,
        "generated_from": GeneratedFrom(
            source_song_path=str(paths.song_path),
            beats_file=str(paths.artifact("essentia", "beats.json")),
            engine="essentia+numpy",
        ),
        "features": frames,
        "beat_features": beat_rows,
        "metadata": {
            "frame_rate": round(sample_rate / hop_size, 6),
            "total_frames": len(frames),
            "duration": round(float(frames[-1].time), 6),
            "normalization_scope": "per-song",
        },
    }
    payload = to_jsonable(payload)
    write_json(paths.artifact("energy_summary", "features.json"), payload)
    return payload


def derive_energy_layer(paths: SongPaths, timing: dict, energy_features: dict, sections_payload: dict) -> dict:
    beat_points = timing["beats"]
    bar_rows = timing["bars"]
    sections = sections_payload.get("sections", [])
    beat_features = [dict(row) for row in energy_features["beat_features"]]

    beat_to_bar = {int(beat["index"]): int(beat["bar"]) for beat in beat_points}
    beat_to_beat_in_bar = {int(beat["index"]): int(beat["beat_in_bar"]) for beat in beat_points}

    enriched_beats: list[dict] = []
    energy_scores: list[float] = []
    for row in beat_features:
        beat_index = int(row["beat"])
        score = round(_energy_score(row), 6)
        section = _section_for_time(float(row["time"]), sections)
        enriched = {
            **row,
            "bar": beat_to_bar.get(beat_index),
            "beat_in_bar": beat_to_beat_in_bar.get(beat_index),
            "energy_score": score,
            "section_id": section.get("section_id") if section else None,
            "section_name": (section.get("section_character") or section.get("label")) if section else None,
        }
        enriched_beats.append(enriched)
        energy_scores.append(score)

    if energy_scores:
        low_threshold = float(np.quantile(np.array(energy_scores), 0.33))
        high_threshold = float(np.quantile(np.array(energy_scores), 0.67))
    else:
        low_threshold = 0.0
        high_threshold = 0.0

    for row in enriched_beats:
        row["level"] = _level_label(float(row["energy_score"]), low_threshold, high_threshold)

    section_energy: list[dict] = []
    for section in sections:
        start_s = float(section["start"])
        end_s = float(section["end"])
        local_beats = [row for row in enriched_beats if start_s <= float(row["time"]) < end_s]
        if not local_beats:
            continue
        local_scores = [float(row["energy_score"]) for row in local_beats]
        local_bars = sorted({int(row["bar"]) for row in local_beats if row.get("bar") is not None})
        section_energy.append(
            {
                "section_id": section["section_id"],
                "section_name": section.get("section_character") or section.get("label"),
                "start_s": round(start_s, 6),
                "end_s": round(end_s, 6),
                "bar_start": min(local_bars) if local_bars else None,
                "bar_end": max(local_bars) if local_bars else None,
                "mean": round(float(np.mean(local_scores)), 6),
                "peak": round(float(np.max(local_scores)), 6),
                "transient_density": round(float(np.mean([row["onset_density"] for row in local_beats])), 6),
                "level": _level_label(float(np.mean(local_scores)), low_threshold, high_threshold),
                "trend": _trend_label(local_scores),
            }
        )

    accent_candidates: list[dict] = []
    if enriched_beats:
        onset_threshold = float(np.quantile(np.array([float(row["onset_density"]) for row in enriched_beats]), 0.9))
        score_threshold = float(np.quantile(np.array(energy_scores), 0.85)) if energy_scores else 0.0
        last_kept_time = -999.0
        for index, row in enumerate(enriched_beats):
            current_onset = float(row["onset_density"])
            current_score = float(row["energy_score"])
            previous_onset = float(enriched_beats[index - 1]["onset_density"]) if index > 0 else current_onset
            next_onset = float(enriched_beats[index + 1]["onset_density"]) if index + 1 < len(enriched_beats) else current_onset
            is_peak = current_onset >= previous_onset and current_onset > next_onset and current_onset >= onset_threshold
            previous_score = float(enriched_beats[index - 1]["energy_score"]) if index > 0 else current_score
            is_rise = current_score >= score_threshold and (current_score - previous_score) >= 0.08
            if not (is_peak or is_rise):
                continue
            if float(row["time"]) - last_kept_time < 0.75:
                continue
            accent_candidates.append(
                {
                    "id": f"accent_{len(accent_candidates) + 1:03d}",
                    "time": round(float(row["time"]), 6),
                    "kind": "rise" if is_rise and current_score >= current_onset else "hit",
                    "intensity": round(max(current_onset, current_score), 6),
                    "bar": row.get("bar"),
                    "beat": row.get("beat_in_bar"),
                    "section_id": row.get("section_id"),
                    "section_name": row.get("section_name"),
                }
            )
            last_kept_time = float(row["time"])

    global_energy = {
        "mean": round(float(np.mean(energy_scores)), 6) if energy_scores else 0.0,
        "peak": round(float(np.max(energy_scores)), 6) if energy_scores else 0.0,
        "dynamic_range": round(float((np.max(energy_scores) - np.min(energy_scores))), 6) if energy_scores else 0.0,
        "transient_density": round(float(np.mean([row["onset_density"] for row in enriched_beats])), 6) if enriched_beats else 0.0,
        "energy_trend": _trend_label(energy_scores),
    }

    payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": paths.song_name,
        "generated_from": {
            "source_song_path": str(paths.song_path),
            "beats_file": str(paths.artifact("essentia", "beats.json")),
            "energy_features_file": str(paths.artifact("energy_summary", "features.json")),
            "sections_file": str(paths.artifact("section_segmentation", "sections.json")),
            "engine": "rule-based-energy-derivation",
        },
        "global_energy": global_energy,
        "section_energy": section_energy,
        "accent_candidates": accent_candidates,
        "beat_energy": enriched_beats,
        "metadata": {
            "bar_count": len(bar_rows),
            "beat_count": len(beat_points),
        },
    }
    write_json(paths.artifact("layer_c_energy.json"), payload)
    return payload
