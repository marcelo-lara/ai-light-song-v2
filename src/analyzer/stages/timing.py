from __future__ import annotations

from statistics import median

from analyzer.exceptions import AnalysisError, DependencyError
from analyzer.io import write_json
from analyzer.models import BarWindow, BeatPoint, GeneratedFrom, SCHEMA_VERSION, to_jsonable
from analyzer.paths import SongPaths


def extract_timing_grid(paths: SongPaths) -> dict:
    try:
        from essentia.standard import MonoLoader, RhythmExtractor2013
    except ImportError as exc:
        raise DependencyError("essentia is required for beat and tempo extraction") from exc

    sample_rate = 44100
    audio = MonoLoader(filename=str(paths.song_path), sampleRate=sample_rate)()
    duration = float(len(audio) / sample_rate)
    rhythm_extractor = RhythmExtractor2013(method="multifeature")
    tempo, beat_times, _, _, _ = rhythm_extractor(audio)
    beat_list = [float(value) for value in beat_times]
    if not beat_list:
        raise AnalysisError("Essentia returned no beats for the input song")

    median_interval = median(
        max(beat_list[index + 1] - beat_list[index], 1e-6)
        for index in range(len(beat_list) - 1)
    ) if len(beat_list) > 1 else 60.0 / float(tempo)

    beats = []
    for index, beat_time in enumerate(beat_list, start=1):
        beat_in_bar = ((index - 1) % 4) + 1
        beats.append(
            BeatPoint(
                index=index,
                time=round(beat_time, 6),
                bar=((index - 1) // 4) + 1,
                beat_in_bar=beat_in_bar,
                type="downbeat" if beat_in_bar == 1 else "beat",
            )
        )

    bars = []
    downbeat_indexes = [index for index, beat in enumerate(beats) if beat.beat_in_bar == 1]
    for bar_number, beat_index in enumerate(downbeat_indexes, start=1):
        start_s = beats[beat_index].time
        if bar_number < len(downbeat_indexes):
            end_s = beats[downbeat_indexes[bar_number]].time
        else:
            end_s = min(duration, beats[-1].time + median_interval)
        bars.append(BarWindow(bar=bar_number, start_s=round(start_s, 6), end_s=round(end_s, 6)))

    payload = {
        "schema_version": SCHEMA_VERSION,
        "song_id": paths.song_id,
        "tempo": round(float(tempo), 3),
        "time_signature": "4/4",
        "generated_from": GeneratedFrom(
            source_song_path=str(paths.song_path),
            engine="essentia.RhythmExtractor2013",
        ),
        "beats": beats,
        "bars": bars,
    }
    payload = to_jsonable(payload)
    write_json(paths.artifact("essentia", "beats.json"), payload)
    return payload
