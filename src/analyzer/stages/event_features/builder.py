from __future__ import annotations

from statistics import median
from typing import Any

from analyzer.io import read_json, write_json
from analyzer.models import SCHEMA_VERSION
from analyzer.paths import SongPaths
from analyzer.stages._stem_activity import estimate_stem_activity_by_beat

from .resampler import _resample_to_100ms_grid
from .timeline import _build_timeline_index
from .utils import (
    ROLLING_WINDOWS,
    _accent_lookup,
    _apply_zscore,
    _attenuated_series,
    _calculate_song_statistics,
    _chord_for_time,
    _phrase_for_time,
    _rolling_mean,
    _rolling_peak,
    _section_for_time,
    _window_end_s,
    _window_note_overlap_score,
)


def _window_size_from_seconds(beat_times: list[float], seconds: float) -> int:
    if len(beat_times) < 2:
        return max(1, int(round(seconds / 0.5)))
    intervals = [max(1e-6, beat_times[i + 1] - beat_times[i]) for i in range(len(beat_times) - 1)]
    typical = max(1e-6, float(median(intervals)))
    return max(1, int(round(seconds / typical)))


def _load_optional_json(path: SongPaths, *parts: str) -> dict[str, Any]:
    artifact_path = path.artifact(*parts)
    if not artifact_path.exists():
        return {}
    payload = read_json(artifact_path)
    return payload if isinstance(payload, dict) else {}


def _beat_band_levels(timing: dict, fft_payload: dict[str, Any]) -> dict[int, dict[str, float]]:
    beats = timing.get("beats", [])
    if not beats:
        return {}

    frames = [dict(row) for row in fft_payload.get("frames", [])]
    bands = [dict(row) for row in fft_payload.get("bands", [])]
    if not frames or not bands:
        return {}

    bass_index = next((index for index, band in enumerate(bands) if str(band.get("id")) == "bass"), None)
    mid_index = next((index for index, band in enumerate(bands) if str(band.get("id")) == "mid"), None)
    if bass_index is None or mid_index is None:
        return {}

    rows: dict[int, dict[str, float]] = {}
    frame_times = [float(frame.get("time", 0.0)) for frame in frames]

    for beat_index, beat in enumerate(beats):
        beat_number = int(beat["index"])
        start_s = float(beat["time"])
        end_s = _window_end_s(timing, beat_index)

        selected = [frame for frame in frames if start_s <= float(frame.get("time", 0.0)) < end_s]
        if not selected:
            closest_index = min(range(len(frame_times)), key=lambda idx: abs(frame_times[idx] - start_s))
            selected = [frames[closest_index]]

        bass_values = [float(frame.get("levels", [0.0] * len(bands))[bass_index]) for frame in selected]
        mid_values = [float(frame.get("levels", [0.0] * len(bands))[mid_index]) for frame in selected]
        rows[beat_number] = {
            "bass_raw": sum(bass_values) / max(len(bass_values), 1),
            "mid_raw": sum(mid_values) / max(len(mid_values), 1),
        }

    return rows


def _beat_mix_rms(timing: dict, rms_payload: dict[str, Any]) -> dict[int, float]:
    beats = timing.get("beats", [])
    frames = [dict(row) for row in rms_payload.get("frames", [])]
    sources = [dict(row) for row in rms_payload.get("sources", [])]
    if not beats or not frames or not sources:
        return {}

    mix_index = next((index for index, source in enumerate(sources) if str(source.get("id")) == "mix"), 0)

    rows: dict[int, float] = {}
    for beat_index, beat in enumerate(beats):
        beat_number = int(beat["index"])
        start_s = float(beat["time"])
        end_s = _window_end_s(timing, beat_index)

        selected = [frame for frame in frames if start_s <= float(frame.get("time", 0.0)) < end_s]
        if not selected:
            selected = [min(frames, key=lambda frame: abs(float(frame.get("time", 0.0)) - start_s))]

        values = [float(frame.get("values", [0.0])[mix_index]) for frame in selected]
        rows[beat_number] = sum(values) / max(len(values), 1)

    return rows


def build_event_feature_layer(
    paths: SongPaths,
    timing: dict,
    harmonic: dict,
    symbolic: dict,
    energy_features: dict,
    energy_layer: dict,
    sections_payload: dict,
    genre_result: dict | None = None,
) -> dict[str, Any]:
    beats = timing.get("beats", [])
    sections = sections_payload.get("sections", [])
    chords = harmonic.get("chords", [])
    phrases = symbolic.get("phrase_windows", [])
    note_events = symbolic.get("note_events", [])
    vocal_notes = [note for note in note_events if str(note.get("source_stem")) == "vocals"]
    bass_notes = [note for note in note_events if str(note.get("source_stem")) == "bass"]

    raw_energy_by_beat = {int(row["beat"]): dict(row) for row in energy_features.get("beat_features", [])}
    derived_energy_by_beat = {int(row["beat"]): dict(row) for row in energy_layer.get("beat_energy", [])}
    symbolic_density_by_beat = {int(row["beat"]): dict(row) for row in symbolic.get("density_per_beat", [])}
    accent_candidates = [dict(row) for row in energy_layer.get("accent_candidates", [])]

    fft_payload = _load_optional_json(paths, "essentia", "fft_bands.json")
    rms_payload = _load_optional_json(paths, "essentia", "rms_loudness.json")
    beat_fft_levels = _beat_band_levels(timing, fft_payload)
    beat_mix_rms = _beat_mix_rms(timing, rms_payload)

    beat_times = [float(beat["time"]) for beat in beats]
    song_end = (
        float(timing.get("bars", [{}])[-1].get("end_s", beat_times[-1] if beat_times else 0.0))
        if beats or timing.get("bars")
        else 0.0
    )
    stem_activity = {
        "vocals_stem_activity": estimate_stem_activity_by_beat(paths.stems_dir / "vocals.wav", beat_times, song_end),
        "drums_stem_activity": estimate_stem_activity_by_beat(paths.stems_dir / "drums.wav", beat_times, song_end),
        "harmonic_stem_activity": estimate_stem_activity_by_beat(paths.stems_dir / "harmonic.wav", beat_times, song_end),
        "bass_stem_activity": estimate_stem_activity_by_beat(paths.stems_dir / "bass.wav", beat_times, song_end),
    }

    raw_rows: list[dict[str, Any]] = []
    silence_gap_seconds = 0.0
    previous_chord_label: str | None = None
    for index, beat in enumerate(beats):
        beat_number = int(beat["index"])
        start_s = float(beat["time"])
        end_s = _window_end_s(timing, index)
        midpoint = (start_s + end_s) / 2.0

        raw_energy = raw_energy_by_beat.get(beat_number, {})
        derived_energy = derived_energy_by_beat.get(beat_number, {})
        density_row = symbolic_density_by_beat.get(beat_number, {})
        section = _section_for_time(midpoint, sections)
        phrase = _phrase_for_time(midpoint, phrases)
        chord = _chord_for_time(start_s, chords)
        accent_id, accent_intensity = _accent_lookup(accent_candidates, start_s, end_s)

        note_count = int(density_row.get("note_count", 0))
        beat_duration = max(end_s - start_s, 1e-6)
        silence_gap_seconds = round(silence_gap_seconds + beat_duration, 6) if note_count == 0 else 0.0

        chord_label = str(chord.get("chord", "N")) if chord else "N"
        chord_confidence = float(chord.get("confidence", 0.0)) if chord else 0.0
        chord_change = 1.0 if previous_chord_label not in (None, chord_label) else 0.0
        previous_chord_label = chord_label

        fft_levels = beat_fft_levels.get(beat_number, {})
        mix_rms = float(beat_mix_rms.get(beat_number, 0.0))

        raw_rows.append(
            {
                "beat": beat_number,
                "bar": int(beat["bar"]),
                "beat_in_bar": int(beat["beat_in_bar"]),
                "start_time": round(start_s, 6),
                "end_time": round(end_s, 6),
                "section_id": section.get("section_id") if section else None,
                "section_name": (section.get("section_character") or section.get("label")) if section else None,
                "phrase_window_id": phrase.get("id") if phrase else None,
                "phrase_group_id": phrase.get("phrase_group_id") if phrase else None,
                "chord": chord_label,
                "chord_confidence": round(chord_confidence, 6),
                "chord_change": chord_change,
                "loudness_avg": float(raw_energy.get("loudness_avg", 0.0)),
                "onset_density": float(raw_energy.get("onset_density", 0.0)),
                "spectral_flux": float(raw_energy.get("flux_avg", 0.0)),
                "spectral_centroid": float(raw_energy.get("centroid_avg", 0.0)),
                "energy_score": float(derived_energy.get("energy_score", 0.0)),
                "symbolic_density": float(density_row.get("density", 0.0)),
                "symbolic_note_count": note_count,
                "vocal_presence": round(_window_note_overlap_score(vocal_notes, start_s, end_s), 6),
                "bass_activation": round(_window_note_overlap_score(bass_notes, start_s, end_s), 6),
                "vocals_stem_activity": float(stem_activity["vocals_stem_activity"][index]) if index < len(stem_activity["vocals_stem_activity"]) else 0.0,
                "drums_stem_activity": float(stem_activity["drums_stem_activity"][index]) if index < len(stem_activity["drums_stem_activity"]) else 0.0,
                "harmonic_stem_activity": float(stem_activity["harmonic_stem_activity"][index]) if index < len(stem_activity["harmonic_stem_activity"]) else 0.0,
                "bass_stem_activity": float(stem_activity["bass_stem_activity"][index]) if index < len(stem_activity["bass_stem_activity"]) else 0.0,
                "accent_id": accent_id,
                "accent_intensity": round(accent_intensity, 6),
                "silence_gap_seconds": silence_gap_seconds,
                "bass_band_energy_raw": round(float(fft_levels.get("bass_raw", 0.0)), 6),
                "mid_band_energy_raw": round(float(fft_levels.get("mid_raw", 0.0)), 6),
                "mix_rms": round(mix_rms, 6),
            }
        )

    bass_att_values = _attenuated_series([float(row["bass_band_energy_raw"]) for row in raw_rows], decay=0.86)
    mid_att_values = _attenuated_series([float(row["mid_band_energy_raw"]) for row in raw_rows], decay=0.9)

    history_2s = _window_size_from_seconds(beat_times, 2.0)
    history_5s = _window_size_from_seconds(beat_times, 5.0)

    for index, row in enumerate(raw_rows):
        row["bass_att"] = round(float(bass_att_values[index]), 6)
        row["mid_att"] = round(float(mid_att_values[index]), 6)
        row["bass_att_lma"] = round(
            sum(float(candidate["bass_att"]) for candidate in raw_rows[max(0, index - history_2s + 1) : index + 1])
            / max(1, len(raw_rows[max(0, index - history_2s + 1) : index + 1])),
            6,
        )
        row["spectral_flux_lma"] = round(
            sum(float(candidate["spectral_flux"]) for candidate in raw_rows[max(0, index - history_2s + 1) : index + 1])
            / max(1, len(raw_rows[max(0, index - history_2s + 1) : index + 1])),
            6,
        )
        row["bass_att_ratio"] = round(float(row["bass_att"]) / max(float(row["bass_att_lma"]), 1e-6), 6)
        row["spectral_flux_ratio"] = round(float(row["spectral_flux"]) / max(float(row["spectral_flux_lma"]), 1e-6), 6)

        lookback_2s = raw_rows[max(0, index - history_2s + 1) : index + 1]
        lookback_5s = raw_rows[max(0, index - history_5s + 1) : index + 1]
        mean_2s = sum(float(candidate["mix_rms"]) for candidate in lookback_2s) / max(1, len(lookback_2s))
        mean_5s = sum(float(candidate["mix_rms"]) for candidate in lookback_5s) / max(1, len(lookback_5s))
        row["mix_rms_rel_2s"] = round(float(row["mix_rms"]) / max(mean_2s, 1e-6), 6)
        row["mix_rms_rel_5s"] = round(float(row["mix_rms"]) / max(mean_5s, 1e-6), 6)

    numeric_keys = [
        "loudness_avg",
        "onset_density",
        "spectral_flux",
        "spectral_centroid",
        "energy_score",
        "symbolic_density",
        "vocal_presence",
        "bass_activation",
        "vocals_stem_activity",
        "drums_stem_activity",
        "harmonic_stem_activity",
        "bass_stem_activity",
        "accent_intensity",
        "chord_confidence",
        "bass_band_energy_raw",
        "mid_band_energy_raw",
        "bass_att",
        "mid_att",
        "mix_rms",
        "mix_rms_rel_2s",
        "mix_rms_rel_5s",
    ]
    song_statistics = _calculate_song_statistics(raw_rows, numeric_keys)

    statistics_payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": paths.song_name,
        "generated_from": {
            "features_file": str(paths.artifact("event_inference", "features.json")),
        },
        "normalization_method": "z-score",
        "statistics": song_statistics,
    }
    write_json(paths.artifact("event_inference", "song_statistics.json"), statistics_payload)

    normalized_rows: list[dict[str, Any]] = []
    for index, row in enumerate(raw_rows):
        normalized = {key: _apply_zscore(float(row[key]), stats["mean"], stats["std_dev"]) for key, stats in song_statistics.items()}
        previous = normalized_rows[index - 1] if index > 0 else None

        derived = {
            "energy_delta": round(normalized["energy_score"] - float(previous["normalized"]["energy_score"]), 6) if previous else 0.0,
            "density_delta": round(normalized["symbolic_density"] - float(previous["normalized"]["symbolic_density"]), 6) if previous else 0.0,
            "silence_gap_seconds": round(float(row["silence_gap_seconds"]), 6),
            "vocal_presence_score": normalized["vocal_presence"],
            "bass_activation_score": normalized["bass_activation"],
            "vocals_stem_score": normalized["vocals_stem_activity"],
            "drums_stem_score": normalized["drums_stem_activity"],
            "harmonic_stem_score": normalized["harmonic_stem_activity"],
            "bass_stem_score": normalized["bass_stem_activity"],
            "vocal_focus_score": round(min(1.0, (normalized["vocal_presence"] * 0.55) + (normalized["vocals_stem_activity"] * 0.45)), 6),
            "percussion_focus_score": round(max(0.0, normalized["drums_stem_activity"] - max(normalized["vocals_stem_activity"], normalized["harmonic_stem_activity"])), 6),
            "instrumental_focus_score": round(max(0.0, ((normalized["harmonic_stem_activity"] * 0.6) + (normalized["bass_stem_activity"] * 0.4)) - (normalized["vocals_stem_activity"] * 0.5)), 6),
            "vocal_stem_delta": round(normalized["vocals_stem_activity"] - float(previous["normalized"]["vocals_stem_activity"]), 6) if previous else 0.0,
            "harmonic_tension_proxy": round(min(1.0, max(0.0, ((1.0 - normalized["chord_confidence"]) + float(row["chord_change"])) / 2.0)), 6),
            "accent_intensity": normalized["accent_intensity"],
            "bass_att": round(float(row["bass_att"]), 6),
            "mid_att": round(float(row["mid_att"]), 6),
            "bass_att_lma": round(float(row["bass_att_lma"]), 6),
            "spectral_flux_lma": round(float(row["spectral_flux_lma"]), 6),
            "bass_att_ratio": round(float(row["bass_att_ratio"]), 6),
            "spectral_flux_ratio": round(float(row["spectral_flux_ratio"]), 6),
            "mix_rms_rel_2s": round(float(row["mix_rms_rel_2s"]), 6),
            "mix_rms_rel_5s": round(float(row["mix_rms_rel_5s"]), 6),
        }

        normalized_rows.append(
            {
                "beat": row["beat"],
                "bar": row["bar"],
                "beat_in_bar": row["beat_in_bar"],
                "start_time": row["start_time"],
                "end_time": row["end_time"],
                "section_id": row["section_id"],
                "section_name": row["section_name"],
                "phrase_window_id": row["phrase_window_id"],
                "phrase_group_id": row["phrase_group_id"],
                "chord": row["chord"],
                "normalized": normalized,
                "derived": derived,
                "source_refs": {
                    "energy_feature_beat": row["beat"],
                    "symbolic_density_beat": row["beat"],
                    "accent_id": row["accent_id"],
                },
            }
        )

    for index, row in enumerate(normalized_rows):
        row["rolling"] = {
            name: {
                "energy_mean": _rolling_mean(normalized_rows, index, "normalized.energy_score", window_size),
                "density_mean": _rolling_mean(normalized_rows, index, "normalized.symbolic_density", window_size),
                "vocal_presence_mean": _rolling_mean(normalized_rows, index, "derived.vocal_presence_score", window_size),
                "bass_activation_mean": _rolling_mean(normalized_rows, index, "derived.bass_activation_score", window_size),
                "harmonic_tension_mean": _rolling_mean(normalized_rows, index, "derived.harmonic_tension_proxy", window_size),
                "bass_att_mean": _rolling_mean(normalized_rows, index, "derived.bass_att", window_size),
                "mix_rms_rel_2s_mean": _rolling_mean(normalized_rows, index, "derived.mix_rms_rel_2s", window_size),
                "mix_rms_rel_2s_peak": _rolling_peak(normalized_rows, index, "derived.mix_rms_rel_2s", window_size),
            }
            for name, window_size in ROLLING_WINDOWS.items()
        }

    duration_s = (
        float(timing.get("bars", [{}])[-1].get("end_s", beats[-1]["time"] if beats else 0.0))
        if beats or timing.get("bars")
        else 0.0
    )
    payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": paths.song_name,
        "generated_from": {
            "source_song_path": str(paths.song_path),
            "beats_file": str(paths.artifact("essentia", "beats.json")),
            "harmonic_layer_file": str(paths.artifact("layer_a_harmonic.json")),
            "symbolic_layer_file": str(paths.artifact("layer_b_symbolic.json")),
            "energy_features_file": str(paths.artifact("energy_summary", "features.json")),
            "energy_layer_file": str(paths.artifact("layer_c_energy.json")),
            "fft_bands_file": str(paths.artifact("essentia", "fft_bands.json")),
            "rms_loudness_file": str(paths.artifact("essentia", "rms_loudness.json")),
            "sections_file": str(paths.artifact("section_segmentation", "sections.json")),
            "genre_file": str(paths.artifact("genre.json")) if genre_result is not None else None,
            "engine": "rule-based-event-feature-alignment",
            "normalization_rules": {
                "numeric_fields": {
                    key: {"method": "per-song z-score", "mean": stats["mean"], "std_dev": stats["std_dev"]}
                    for key, stats in song_statistics.items()
                },
                "silence_gap": "accumulate consecutive beat durations where symbolic_note_count equals zero",
                "rolling_windows_beats": dict(ROLLING_WINDOWS),
                "history_windows_beats": {"2s": history_2s, "5s": history_5s},
                "attenuated_features": ["bass_att", "mid_att"],
                "harmonic_tension_proxy": "average of inverse normalized chord confidence and chord change flag",
            },
        },
        "metadata": {
            "duration_s": round(duration_s, 6),
            "beat_count": len(beats),
            "bar_count": len(timing.get("bars", [])),
            "section_count": len(sections),
            "phrase_count": len(phrases),
            "genres": list(genre_result.get("genres", [])) if genre_result else [],
        },
        "feature_catalog": {
            "normalized": list(song_statistics.keys()),
            "derived": [
                "energy_delta",
                "density_delta",
                "silence_gap_seconds",
                "vocal_presence_score",
                "bass_activation_score",
                "vocals_stem_score",
                "drums_stem_score",
                "harmonic_stem_score",
                "bass_stem_score",
                "vocal_focus_score",
                "percussion_focus_score",
                "instrumental_focus_score",
                "vocal_stem_delta",
                "harmonic_tension_proxy",
                "accent_intensity",
                "bass_att",
                "mid_att",
                "bass_att_lma",
                "spectral_flux_lma",
                "bass_att_ratio",
                "spectral_flux_ratio",
                "mix_rms_rel_2s",
                "mix_rms_rel_5s",
            ],
        },
        "features": normalized_rows,
    }

    for row in payload["features"]:
        if float(row["start_time"]) < 0.0 or float(row["end_time"]) > duration_s + 1e-6:
            raise ValueError("Event feature windows must stay within song duration")

    grid_features = _resample_to_100ms_grid(normalized_rows, duration_s)
    contextual_payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": paths.song_name,
        "generated_from": {
            "source_song_path": str(paths.song_path),
            "features_file": str(paths.artifact("event_inference", "features.json")),
            "song_statistics_file": str(paths.artifact("event_inference", "song_statistics.json")),
        },
        "metadata": {
            "duration_s": round(duration_s, 6),
            "grid_resolution_s": 0.1,
            "grid_size": len(grid_features),
            "normalization_method": "z-score",
        },
        "feature_catalog": {"normalized": list(song_statistics.keys())},
        "features": grid_features,
    }
    write_json(paths.artifact("event_inference", "contextual_features.json"), contextual_payload)

    write_json(paths.artifact("event_inference", "features.json"), payload)
    _build_timeline_index(
        paths=paths,
        timing=timing,
        sections=sections,
        phrases=phrases,
        chords=chords,
        accent_candidates=accent_candidates,
    )
    return payload
