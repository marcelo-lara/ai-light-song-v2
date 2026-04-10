from __future__ import annotations

from statistics import median

from analyzer.exceptions import AnalysisError, DependencyError
from analyzer.io import read_json, write_json
from analyzer.models import BarWindow, BeatPoint, GeneratedFrom, SCHEMA_VERSION, build_song_schema_fields, round_schema_float, to_jsonable
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
        **build_song_schema_fields(paths, bpm=tempo, duration=duration),
        "time_signature": "4/4",
        "generated_from": GeneratedFrom(
            source_song_path=str(paths.song_path),
            engine="essentia.RhythmExtractor2013",
        ),
        "tempo": round_schema_float(tempo),
        "beats": beats,
        "bars": bars,
    }
    payload = to_jsonable(payload)
    write_json(paths.artifact("essentia", "beats.json"), payload)
    return payload


def build_reference_timing_grid(
    paths: SongPaths,
    duration: float,
    *,
    reference_chords_path: str | None = None,
    inferred_beats_path: str | None = None,
) -> dict:
    reference_path = paths.reference("moises", "chords.json") if reference_chords_path is None else None
    if reference_chords_path is not None:
        from pathlib import Path

        reference_path = Path(reference_chords_path)
    if reference_path is None or not reference_path.exists():
        raise AnalysisError("Reference chord beat file is required to build the canonical reference timing grid")

    reference_rows = read_json(reference_path)
    beat_rows: list[dict] = []
    seen_times: set[float] = set()
    for row in reference_rows:
        if "curr_beat_time" not in row:
            continue
        beat_time = round(float(row["curr_beat_time"]), 6)
        if beat_time in seen_times:
            continue
        seen_times.add(beat_time)
        beat_rows.append(
            {
                "time": beat_time,
                "bar": int(row.get("bar_num") or 0),
                "beat_in_bar": int(row.get("beat_num") or 0),
            }
        )
    if not beat_rows:
        raise AnalysisError("Reference chord beat file did not contain usable beat timestamps")

    beat_rows.sort(key=lambda item: item["time"])
    beat_list = [row["time"] for row in beat_rows]
    median_interval = median(
        max(beat_list[index + 1] - beat_list[index], 1e-6)
        for index in range(len(beat_list) - 1)
    ) if len(beat_list) > 1 else 0.0
    tempo = 60.0 / median_interval if median_interval > 0 else 0.0

    beats = []
    for index, row in enumerate(beat_rows, start=1):
        beat_in_bar = row["beat_in_bar"] if row["beat_in_bar"] > 0 else ((index - 1) % 4) + 1
        bar_number = row["bar"] if row["bar"] > 0 else ((index - 1) // 4) + 1
        beats.append(
            BeatPoint(
                index=index,
                time=row["time"],
                bar=bar_number,
                beat_in_bar=beat_in_bar,
                type="downbeat" if beat_in_bar == 1 else "beat",
            )
        )

    bars = []
    bar_starts: list[tuple[int, float]] = []
    for beat in beats:
        if not bar_starts or bar_starts[-1][0] != beat.bar:
            bar_starts.append((beat.bar, beat.time))
    for index, (bar_number, start_s) in enumerate(bar_starts):
        if index + 1 < len(bar_starts):
            end_s = bar_starts[index + 1][1]
        else:
            end_s = min(float(duration), beats[-1].time + median_interval) if median_interval > 0 else float(duration)
        bars.append(BarWindow(bar=bar_number, start_s=round(start_s, 6), end_s=round(end_s, 6)))

    dependencies = {"reference_chords": str(reference_path)}
    if inferred_beats_path is not None:
        dependencies["inferred_beats_file"] = str(inferred_beats_path)
    payload = {
        "schema_version": SCHEMA_VERSION,
        **build_song_schema_fields(paths, bpm=tempo, duration=duration),
        "time_signature": "4/4",
        "generated_from": GeneratedFrom(
            source_song_path=str(paths.song_path),
            engine="reference.moises.chords",
            dependencies=dependencies,
        ),
        "tempo": round_schema_float(tempo),
        "beats": beats,
        "bars": bars,
    }
    return to_jsonable(payload)
