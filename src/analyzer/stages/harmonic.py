from __future__ import annotations

import numpy as np

from analyzer.exceptions import AnalysisError, DependencyError
from analyzer.io import read_json, write_json
from analyzer.models import ChordEvent, GeneratedFrom, SCHEMA_VERSION, to_jsonable
from analyzer.paths import SongPaths


FLAT_TO_SHARP = {
    "Cb": "B",
    "Db": "C#",
    "Eb": "D#",
    "Fb": "E",
    "Gb": "F#",
    "Ab": "G#",
    "Bb": "A#",
}

FRAME_SIZE = 4096
HOP_SIZE = 2048
SAMPLE_RATE = 44100
NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
NOTE_INDEX = {note: index for index, note in enumerate(NOTE_NAMES)}


def _normalize_note_spelling(label: str) -> str:
    normalized = (label or "N").strip()
    if not normalized:
        return "N"
    for flat, sharp in FLAT_TO_SHARP.items():
        normalized = normalized.replace(flat, sharp)
    normalized = normalized.replace(":maj", "")
    normalized = normalized.replace(":min", "m")
    return normalized


def _normalize_reference_chord_label(label: str | None) -> str:
    normalized = _normalize_note_spelling(label or "N")
    normalized = normalized.replace("maj7", "")
    normalized = normalized.replace("maj9", "")
    normalized = normalized.replace("add9", "")
    normalized = normalized.replace("sus2", "")
    normalized = normalized.replace("sus4", "")
    normalized = normalized.replace("7", "")
    normalized = normalized.replace(":", "")
    normalized = normalized.replace("/", "")
    if normalized.endswith("min"):
        normalized = normalized[:-3] + "m"
    return normalized or "N"


def build_reference_harmonic_layer(
    paths: SongPaths,
    timing: dict,
    *,
    inferred_harmonic_path: str | None = None,
) -> dict:
    reference_path = paths.reference("moises", "chords.json")
    if reference_path is None or not reference_path.exists():
        raise AnalysisError("Reference chord file is required to promote the canonical harmonic layer")

    reference_rows = read_json(reference_path)
    if not reference_rows:
        raise AnalysisError("Reference chord file did not contain any rows")

    beat_rows = []
    for row in reference_rows:
        if "curr_beat_time" not in row:
            continue
        beat_rows.append(
            {
                "time": round(float(row["curr_beat_time"]), 6),
                "bar": int(row.get("bar_num") or 0),
                "beat": int(row.get("beat_num") or 0),
                "label": _normalize_reference_chord_label(
                    row.get("chord_simple_pop") or row.get("chord_basic_pop") or row.get("prev_chord")
                ),
            }
        )
    if not beat_rows:
        raise AnalysisError("Reference chord file did not contain usable beat-aligned chord rows")

    chord_events: list[ChordEvent] = []
    chord_probabilities = []
    current = beat_rows[0]
    run_start_index = 0
    song_end = float(timing["bars"][-1]["end_s"]) if timing.get("bars") else float(beat_rows[-1]["time"])

    for index, row in enumerate(beat_rows):
        chord_probabilities.append(
            {
                "beat": index + 1,
                "time": row["time"],
                "label": row["label"],
                "confidence": 1.0,
                "source": "reference_promoted",
            }
        )
        if row["label"] != current["label"]:
            chord_events.append(
                ChordEvent(
                    time=current["time"],
                    end_s=row["time"],
                    bar=current["bar"] or ((run_start_index // 4) + 1),
                    beat=current["beat"] or ((run_start_index % 4) + 1),
                    chord=current["label"],
                    confidence=1.0,
                )
            )
            current = row
            run_start_index = index

    chord_events.append(
        ChordEvent(
            time=current["time"],
            end_s=song_end,
            bar=current["bar"] or ((run_start_index // 4) + 1),
            beat=current["beat"] or ((run_start_index % 4) + 1),
            chord=current["label"],
            confidence=1.0,
        )
    )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": paths.song_name,
        "generated_from": {
            "source_song_path": str(paths.song_path),
            "beats_file": str(paths.artifact("essentia", "beats.json")),
            "reference_chords_file": str(reference_path),
            "engine": "reference.moises.chords.promotion",
            "dependencies": {
                "reference_chords": str(reference_path),
                **({"inferred_harmonic_file": inferred_harmonic_path} if inferred_harmonic_path is not None else {}),
            },
        },
        "global_key": {
            "label": None,
            "confidence": 1.0,
            "source": "reference_promoted",
        },
        "chords": chord_events,
        "chord_probabilities": chord_probabilities,
    }
    payload = to_jsonable(payload)
    write_json(paths.artifact("layer_a_harmonic.json"), payload)
    return payload


def _diatonic_chord_map(key_label: str, key_scale: str) -> dict[int, str]:
    tonic = _normalize_note_spelling(key_label)
    if tonic not in NOTE_INDEX:
        return {}

    tonic_index = NOTE_INDEX[tonic]
    if key_scale == "major":
        return {
            tonic_index % 12: NOTE_NAMES[tonic_index % 12],
            (tonic_index + 2) % 12: f"{NOTE_NAMES[(tonic_index + 2) % 12]}m",
            (tonic_index + 4) % 12: f"{NOTE_NAMES[(tonic_index + 4) % 12]}m",
            (tonic_index + 5) % 12: NOTE_NAMES[(tonic_index + 5) % 12],
            (tonic_index + 7) % 12: NOTE_NAMES[(tonic_index + 7) % 12],
            (tonic_index + 9) % 12: f"{NOTE_NAMES[(tonic_index + 9) % 12]}m",
        }

    return {
        tonic_index % 12: f"{NOTE_NAMES[tonic_index % 12]}m",
        (tonic_index + 2) % 12: f"{NOTE_NAMES[(tonic_index + 2) % 12]}dim",
        (tonic_index + 3) % 12: NOTE_NAMES[(tonic_index + 3) % 12],
        (tonic_index + 5) % 12: f"{NOTE_NAMES[(tonic_index + 5) % 12]}m",
        (tonic_index + 7) % 12: f"{NOTE_NAMES[(tonic_index + 7) % 12]}m",
        (tonic_index + 8) % 12: NOTE_NAMES[(tonic_index + 8) % 12],
        (tonic_index + 10) % 12: NOTE_NAMES[(tonic_index + 10) % 12],
    }


def _extract_hpcp(audio: np.ndarray) -> tuple[list[np.ndarray], list[float]]:
    from essentia.standard import FrameGenerator, HPCP, Spectrum, SpectralPeaks, Windowing

    windowing = Windowing(type="hann")
    spectrum = Spectrum()
    spectral_peaks = SpectralPeaks(
        minFrequency=40,
        maxFrequency=5000,
        magnitudeThreshold=1e-5,
        maxPeaks=60,
        orderBy="magnitude",
    )
    hpcp_algorithm = HPCP(size=12, referenceFrequency=440, normalized="unitMax")

    frame_vectors: list[np.ndarray] = []
    frame_times: list[float] = []
    for frame_index, frame in enumerate(FrameGenerator(audio, frameSize=FRAME_SIZE, hopSize=HOP_SIZE, startFromZero=True)):
        spec = spectrum(windowing(frame))
        frequencies, magnitudes = spectral_peaks(spec)
        if len(frequencies) == 0:
            vector = np.zeros(12, dtype=float)
        else:
            vector = np.array(hpcp_algorithm(frequencies, magnitudes), dtype=float)
        frame_vectors.append(vector)
        frame_times.append(frame_index * HOP_SIZE / SAMPLE_RATE)

    if not frame_vectors:
        raise AnalysisError("No HPCP frames were extracted from the harmonic stem")

    return frame_vectors, frame_times


def _aggregate_hpcp_by_beat(
    frame_vectors: list[np.ndarray],
    frame_times: list[float],
    beat_times: list[float],
) -> list[dict[str, object]]:
    hpcp_by_beat = []
    for index, beat_time in enumerate(beat_times):
        next_time = beat_times[index + 1] if index + 1 < len(beat_times) else frame_times[-1] + (HOP_SIZE / SAMPLE_RATE)
        selected = [vector for frame_time, vector in zip(frame_times, frame_vectors) if beat_time <= frame_time < next_time]
        if not selected:
            nearest_index = min(range(len(frame_times)), key=lambda item: abs(frame_times[item] - beat_time))
            selected = [frame_vectors[nearest_index]]
        beat_vector = np.mean(np.vstack(selected), axis=0)
        norm = np.linalg.norm(beat_vector)
        if norm > 0:
            beat_vector = beat_vector / norm
        hpcp_by_beat.append({
            "beat": index + 1,
            "time": round(beat_time, 6),
            "vector": [round(float(value), 6) for value in beat_vector],
        })
    return hpcp_by_beat


def _merge_short_chord_runs(labels: list[str], strengths: list[float], min_run_beats: int = 3) -> tuple[list[str], list[float]]:
    if not labels:
        return labels, strengths
    merged_labels = list(labels)
    merged_strengths = list(strengths)
    changed = True
    while changed:
        changed = False
        runs: list[tuple[int, int]] = []
        start = 0
        for index in range(1, len(merged_labels) + 1):
            if index == len(merged_labels) or merged_labels[index] != merged_labels[start]:
                runs.append((start, index))
                start = index

        for run_index, (start, end) in enumerate(runs):
            if end - start >= min_run_beats:
                continue
            previous_run = runs[run_index - 1] if run_index > 0 else None
            next_run = runs[run_index + 1] if run_index + 1 < len(runs) else None
            if previous_run and next_run and merged_labels[previous_run[0]] == merged_labels[next_run[0]]:
                replacement = merged_labels[previous_run[0]]
                replacement_strength = max(
                    merged_strengths[previous_run[0]],
                    merged_strengths[next_run[0]],
                )
            else:
                previous_strength = (
                    sum(merged_strengths[previous_run[0]:previous_run[1]]) / (previous_run[1] - previous_run[0])
                    if previous_run
                    else -1.0
                )
                next_strength = (
                    sum(merged_strengths[next_run[0]:next_run[1]]) / (next_run[1] - next_run[0])
                    if next_run
                    else -1.0
                )
                if previous_strength >= next_strength:
                    replacement = merged_labels[previous_run[0]] if previous_run else merged_labels[next_run[0]]
                    replacement_strength = previous_strength if previous_run else next_strength
                else:
                    replacement = merged_labels[next_run[0]] if next_run else merged_labels[previous_run[0]]
                    replacement_strength = next_strength if next_run else previous_strength

            for index in range(start, end):
                merged_labels[index] = replacement
                merged_strengths[index] = replacement_strength
            changed = True
            break
    return merged_labels, merged_strengths


def _decode_chords_by_beat(
    frame_vectors: list[np.ndarray],
    frame_times: list[float],
    beat_times: list[float],
) -> tuple[list[str], list[float]]:
    from essentia.standard import ChordsDetection

    raw_labels, raw_strengths = ChordsDetection(hopSize=HOP_SIZE, sampleRate=SAMPLE_RATE)(
        [vector.tolist() for vector in frame_vectors]
    )
    normalized_frame_labels = [_normalize_note_spelling(label) for label in raw_labels]

    beat_labels: list[str] = []
    beat_strengths: list[float] = []
    usable_frame_times = frame_times[:len(normalized_frame_labels)]
    for index, beat_time in enumerate(beat_times):
        next_time = beat_times[index + 1] if index + 1 < len(beat_times) else usable_frame_times[-1] + (HOP_SIZE / SAMPLE_RATE)
        selected_indexes = [
            frame_index
            for frame_index, frame_time in enumerate(usable_frame_times)
            if beat_time <= frame_time < next_time
        ]
        if not selected_indexes:
            selected_indexes = [
                min(range(len(usable_frame_times)), key=lambda item: abs(usable_frame_times[item] - beat_time))
            ]

        counts: dict[str, int] = {}
        strengths: dict[str, float] = {}
        for frame_index in selected_indexes:
            label = normalized_frame_labels[frame_index]
            counts[label] = counts.get(label, 0) + 1
            strengths[label] = strengths.get(label, 0.0) + float(raw_strengths[frame_index])

        chosen_label = max(counts, key=lambda label: (counts[label], strengths[label]))
        beat_labels.append(chosen_label)
        beat_strengths.append(round(strengths[chosen_label] / counts[chosen_label], 6))

    return _merge_short_chord_runs(beat_labels, beat_strengths, min_run_beats=3)


def _estimate_bass_chroma(bass_stem: str) -> tuple[np.ndarray, np.ndarray]:
    import librosa
    import soundfile as sf

    audio, sample_rate = sf.read(bass_stem)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    chroma = librosa.feature.chroma_cqt(y=audio.astype(np.float32), sr=sample_rate)
    times = librosa.times_like(chroma, sr=sample_rate)
    return chroma, times


def _estimate_chroma_by_beat(audio_path: str, beat_times: list[float]) -> np.ndarray:
    import librosa

    audio, sample_rate = librosa.load(audio_path, sr=SAMPLE_RATE, mono=True)
    chroma = librosa.feature.chroma_cqt(y=audio.astype(np.float32), sr=sample_rate)
    frame_times = librosa.times_like(chroma, sr=sample_rate)
    beat_vectors: list[np.ndarray] = []
    for index, beat_time in enumerate(beat_times):
        next_time = beat_times[index + 1] if index + 1 < len(beat_times) else frame_times[-1] + (frame_times[1] - frame_times[0])
        mask = (frame_times >= beat_time) & (frame_times < next_time)
        if not np.any(mask):
            mask[np.argmin(np.abs(frame_times - beat_time))] = True
        vector = chroma[:, mask].mean(axis=1)
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm
        beat_vectors.append(vector.astype(float))
    return np.vstack(beat_vectors)


def _estimate_vocal_activity_by_beat(vocal_stem: str, beat_times: list[float]) -> np.ndarray:
    import librosa

    audio, sample_rate = librosa.load(vocal_stem, sr=SAMPLE_RATE, mono=True)
    rms = librosa.feature.rms(y=audio.astype(np.float32), frame_length=2048, hop_length=512)[0]
    frame_times = librosa.times_like(rms, sr=sample_rate, hop_length=512)
    beat_activity: list[float] = []
    for index, beat_time in enumerate(beat_times):
        next_time = beat_times[index + 1] if index + 1 < len(beat_times) else frame_times[-1] + (frame_times[1] - frame_times[0])
        mask = (frame_times >= beat_time) & (frame_times < next_time)
        if not np.any(mask):
            mask[np.argmin(np.abs(frame_times - beat_time))] = True
        beat_activity.append(float(rms[mask].mean()))
    activity = np.array(beat_activity, dtype=float)
    maximum = float(activity.max()) if activity.size else 0.0
    if maximum > 1e-8:
        activity = activity / maximum
    return activity


def _apply_bass_root_corrections(
    chord_events: list[ChordEvent],
    bass_stem: str,
    key_label: str,
    key_scale: str,
    min_margin: float = 0.05,
) -> list[ChordEvent]:
    diatonic_map = _diatonic_chord_map(key_label, key_scale)
    if not diatonic_map or not chord_events:
        return chord_events

    chroma, times = _estimate_bass_chroma(bass_stem)
    corrected_events: list[ChordEvent] = []
    for event in chord_events:
        mask = (times >= float(event.time)) & (times < float(event.end_s))
        if not np.any(mask):
            corrected_events.append(event)
            continue

        averaged = chroma[:, mask].mean(axis=1)
        ranked = np.argsort(averaged)[::-1]
        top_index = int(ranked[0])
        second_value = float(averaged[ranked[1]]) if len(ranked) > 1 else 0.0
        top_value = float(averaged[top_index])
        candidate = diatonic_map.get(top_index)
        if candidate is None or (top_value - second_value) < min_margin:
            corrected_events.append(event)
            continue

        corrected_events.append(
            ChordEvent(
                time=event.time,
                end_s=event.end_s,
                bar=event.bar,
                beat=event.beat,
                chord=candidate,
                confidence=event.confidence,
            )
        )
    return corrected_events


def _merge_adjacent_chord_events(chord_events: list[ChordEvent]) -> list[ChordEvent]:
    if not chord_events:
        return []

    merged: list[ChordEvent] = [chord_events[0]]
    for event in chord_events[1:]:
        previous = merged[-1]
        if previous.chord != event.chord:
            merged.append(event)
            continue
        merged[-1] = ChordEvent(
            time=previous.time,
            end_s=event.end_s,
            bar=previous.bar,
            beat=previous.beat,
            chord=previous.chord,
            confidence=round(float((previous.confidence + event.confidence) / 2.0), 6),
        )
    return merged


def _boundary_alignment_score(
    candidate_index: int,
    mix_chroma_by_beat: np.ndarray,
    bass_chroma_by_beat: np.ndarray,
    vocal_activity_by_beat: np.ndarray,
) -> float:
    left_start = max(0, candidate_index - 2)
    right_end = min(len(mix_chroma_by_beat), candidate_index + 2)

    left_mix = mix_chroma_by_beat[left_start:candidate_index].mean(axis=0) if candidate_index > left_start else mix_chroma_by_beat[candidate_index]
    right_mix = mix_chroma_by_beat[candidate_index:right_end].mean(axis=0) if right_end > candidate_index else mix_chroma_by_beat[candidate_index]
    left_bass = bass_chroma_by_beat[left_start:candidate_index].mean(axis=0) if candidate_index > left_start else bass_chroma_by_beat[candidate_index]
    right_bass = bass_chroma_by_beat[candidate_index:right_end].mean(axis=0) if right_end > candidate_index else bass_chroma_by_beat[candidate_index]

    mix_denominator = max(float(np.linalg.norm(left_mix) * np.linalg.norm(right_mix)), 1e-8)
    bass_denominator = max(float(np.linalg.norm(left_bass) * np.linalg.norm(right_bass)), 1e-8)
    mix_novelty = 1.0 - float(np.dot(left_mix, right_mix) / mix_denominator)
    bass_novelty = 1.0 - float(np.dot(left_bass, right_bass) / bass_denominator)
    vocal_quietness = 1.0 - float(vocal_activity_by_beat[candidate_index])
    return (0.5 * mix_novelty) + (0.35 * bass_novelty) + (0.15 * vocal_quietness)


def _refine_chord_boundaries(
    chord_events: list[ChordEvent],
    song_path: str,
    bass_stem: str,
    vocal_stem: str,
    timing: dict,
) -> list[ChordEvent]:
    if len(chord_events) < 2:
        return chord_events

    beat_points = timing["beats"]
    beat_times = [float(beat["time"]) for beat in beat_points]
    mix_chroma_by_beat = _estimate_chroma_by_beat(song_path, beat_times)
    bass_chroma_by_beat = _estimate_chroma_by_beat(bass_stem, beat_times)
    vocal_activity_by_beat = _estimate_vocal_activity_by_beat(vocal_stem, beat_times)

    beat_index_by_time = {round(float(beat["time"]), 6): index for index, beat in enumerate(beat_points)}
    aligned_events = [
        {
            "time": float(event.time),
            "end_s": float(event.end_s),
            "chord": event.chord,
            "confidence": float(event.confidence),
        }
        for event in chord_events
    ]

    for index in range(1, len(aligned_events)):
        boundary_time = round(aligned_events[index]["time"], 6)
        beat_index = beat_index_by_time.get(boundary_time)
        if beat_index is None:
            continue
        candidate_indexes = [candidate for candidate in (beat_index - 1, beat_index, beat_index + 1) if 0 < candidate < len(beat_times) - 1]
        if not candidate_indexes:
            continue
        best_index = max(
            candidate_indexes,
            key=lambda candidate: _boundary_alignment_score(
                candidate,
                mix_chroma_by_beat,
                bass_chroma_by_beat,
                vocal_activity_by_beat,
            ),
        )
        aligned_events[index]["time"] = float(beat_times[best_index])
        aligned_events[index - 1]["end_s"] = float(beat_times[best_index])

    song_end = float(timing["bars"][-1]["end_s"])
    rebuilt_events: list[ChordEvent] = []
    for index, event in enumerate(aligned_events):
        start_time = float(event["time"])
        end_time = float(aligned_events[index + 1]["time"]) if index + 1 < len(aligned_events) else song_end
        if end_time <= start_time:
            continue
        beat_index = beat_index_by_time.get(round(start_time, 6))
        if beat_index is None:
            beat_index = min(range(len(beat_times)), key=lambda candidate: abs(beat_times[candidate] - start_time))
        beat = beat_points[beat_index]
        rebuilt_events.append(
            ChordEvent(
                time=round(start_time, 6),
                end_s=round(end_time, 6),
                bar=int(beat["bar"]),
                beat=int(beat["beat_in_bar"]),
                chord=str(event["chord"]),
                confidence=round(float(event["confidence"]), 6),
            )
        )

    return _merge_adjacent_chord_events(rebuilt_events)


def extract_hpcp_and_chords(paths: SongPaths, stems: dict[str, str], timing: dict) -> tuple[dict, dict]:
    try:
        from essentia.standard import Key, MonoLoader
    except ImportError as exc:
        raise DependencyError("essentia is required for HPCP and chord extraction") from exc

    harmonic_stem = stems["harmonic"]
    audio = MonoLoader(filename=harmonic_stem, sampleRate=SAMPLE_RATE)()
    beat_times = [beat["time"] if isinstance(beat, dict) else beat.time for beat in timing["beats"]]
    frame_vectors, frame_times = _extract_hpcp(audio)
    hpcp_by_beat = _aggregate_hpcp_by_beat(frame_vectors, frame_times, beat_times)
    aggregated_vectors = np.vstack([row["vector"] for row in hpcp_by_beat]).astype("float32")

    hpcp_payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": paths.song_name,
        "generated_from": GeneratedFrom(
            source_song_path=str(paths.song_path),
            harmonic_stem=harmonic_stem,
            beats_file=str(paths.artifact("essentia", "beats.json")),
            engine="essentia.HPCP",
        ),
        "hpcp_by_beat": hpcp_by_beat,
    }
    hpcp_payload = to_jsonable(hpcp_payload)
    write_json(paths.artifact("essentia", "hpcp.json"), hpcp_payload)

    key_label, key_scale, key_strength, _ = Key(profileType="edma", pcpSize=12)(aggregated_vectors.mean(axis=0))
    normalized_key_label = _normalize_note_spelling(key_label)
    normalized_labels, normalized_strengths = _decode_chords_by_beat(frame_vectors, frame_times, beat_times)

    chord_events: list[ChordEvent] = []
    chord_probabilities = []
    current_label = normalized_labels[0]
    start_index = 0
    for beat_index, label in enumerate(normalized_labels):
        confidence = normalized_strengths[beat_index]
        chord_probabilities.append({
            "beat": beat_index + 1,
            "time": hpcp_by_beat[beat_index]["time"],
            "label": label,
            "confidence": round(confidence, 6),
        })
        if label != current_label:
            chord_events.append(
                _build_chord_event(
                    timing=timing,
                    start_index=start_index,
                    end_index=beat_index,
                    label=current_label,
                    confidence_scores=[item["confidence"] for item in chord_probabilities[start_index:beat_index]],
                )
            )
            current_label = label
            start_index = beat_index

    chord_events.append(
        _build_chord_event(
            timing=timing,
            start_index=start_index,
            end_index=len(normalized_labels),
            label=current_label,
            confidence_scores=[item["confidence"] for item in chord_probabilities[start_index:]],
        )
    )

    chord_events = _apply_bass_root_corrections(
        chord_events=chord_events,
        bass_stem=stems["bass"],
        key_label=normalized_key_label,
        key_scale=key_scale,
    )
    chord_events = _refine_chord_boundaries(
        chord_events=chord_events,
        song_path=str(paths.song_path),
        bass_stem=stems["bass"],
        vocal_stem=stems["vocals"],
        timing=timing,
    )

    layer_payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": paths.song_name,
        "generated_from": {
            "source_song_path": str(paths.song_path),
            "harmonic_stem": harmonic_stem,
            "bass_stem": stems["bass"],
            "vocals_stem": stems["vocals"],
            "beats_file": str(paths.artifact("essentia", "beats.json")),
            "hpcp_file": str(paths.artifact("essentia", "hpcp.json")),
            "engine": "essentia.HPCP+ChordsDetection+Key+bass-root-diatonic-correction+mix-bass-vocal-boundary-alignment",
        },
        "global_key": {
            "label": f"{normalized_key_label} {key_scale}",
            "confidence": round(float(key_strength), 6),
            "source": "hpcp",
        },
        "chords": chord_events,
        "chord_probabilities": chord_probabilities,
    }
    layer_payload = to_jsonable(layer_payload)
    write_json(paths.artifact("layer_a_harmonic.json"), layer_payload)
    return hpcp_payload, layer_payload


def _build_chord_event(timing: dict, start_index: int, end_index: int, label: str, confidence_scores: list[float]) -> ChordEvent:
    beats = timing["beats"]
    beat = beats[start_index]
    event_end = beats[end_index]["time"] if end_index < len(beats) else timing["bars"][-1]["end_s"]
    return ChordEvent(
        time=round(float(beat["time"]), 6),
        end_s=round(float(event_end), 6),
        bar=int(beat["bar"]),
        beat=int(beat["beat_in_bar"]),
        chord=label,
        confidence=round(float(sum(confidence_scores) / max(len(confidence_scores), 1)), 6),
    )
