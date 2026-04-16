from __future__ import annotations

from collections import Counter
from pathlib import Path
import subprocess
from statistics import median
import sys

from analyzer.exceptions import AnalysisError, DependencyError
from analyzer.io import ensure_directory, write_json
from analyzer.models import SCHEMA_VERSION
from analyzer.paths import SongPaths
from analyzer.stages._omnizart_runtime import resolve_omnizart_drum_model_path
from analyzer.stages.symbolic import _nearest_beat_alignment, _section_for_time


SUPPORTED_EVENT_TYPES = ["kick", "snare", "hat", "unresolved"]
KICK_PITCHES = {35, 36}
SNARE_PITCHES = {37, 38, 39, 40}
HAT_PITCHES = {42, 44, 46}


def _event_type_for_pitch(pitch: int) -> str:
    if pitch in KICK_PITCHES:
        return "kick"
    if pitch in SNARE_PITCHES:
        return "snare"
    if pitch in HAT_PITCHES:
        return "hat"
    return "unresolved"


def _bar_for_time(time_s: float, bars: list[dict]) -> int | None:
    for bar in bars:
        if float(bar["start_s"]) <= time_s < float(bar["end_s"]):
            return int(bar["bar"])
    if bars and time_s >= float(bars[-1]["start_s"]):
        return int(bars[-1]["bar"])
    return None


def _transcribe_drums(stem_path: str, midi_path: Path) -> tuple[object, Path, str]:
    try:
        model_path, model_source = resolve_omnizart_drum_model_path()
    except ImportError as exc:
        raise DependencyError("Omnizart drum transcription is required for Story 3.2") from exc

    ensure_directory(midi_path.parent)
    try:
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "from pathlib import Path; "
                    "import sys; "
                    "from omnizart.drum import app; "
                    "stem_path, model_path, midi_path = sys.argv[1:4]; "
                    "midi = app.transcribe(stem_path, model_path=model_path, output=midi_path); "
                    "output_path = Path(midi_path); "
                    "output_path.parent.mkdir(parents=True, exist_ok=True); "
                    "(midi.write(str(output_path)) if hasattr(midi, 'write') else None)"
                ),
                stem_path,
                str(model_path),
                str(midi_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise DependencyError("Omnizart CLI is not available in the runtime") from exc
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        stdout = (exc.stdout or "").strip()
        detail = stderr or stdout or str(exc)
        raise AnalysisError(f"Omnizart drum transcription failed for {stem_path}: {detail}") from exc

    if not midi_path.exists():
        raise AnalysisError(f"Omnizart did not produce the expected MIDI cache: {midi_path}")

    try:
        import pretty_midi
    except ImportError as exc:
        raise DependencyError("pretty_midi is required to parse Omnizart drum output") from exc

    try:
        midi = pretty_midi.PrettyMIDI(str(midi_path))
    except Exception as exc:  # pragma: no cover - depends on external MIDI parsing
        raise AnalysisError(f"Failed to parse Omnizart drum MIDI cache at {midi_path}: {exc}") from exc

    if completed.stdout:
        _ = completed.stdout
    return midi, model_path, model_source


def _build_events(midi: object, timing: dict, sections_payload: dict) -> list[dict]:
    beat_points = timing.get("beats", [])
    beat_times = [float(beat["time"]) for beat in beat_points]
    bars = timing.get("bars", [])
    sections = sections_payload.get("sections", [])

    raw_notes: list[dict] = []
    for instrument in getattr(midi, "instruments", []):
        for note in getattr(instrument, "notes", []):
            raw_notes.append(
                {
                    "time": round(float(note.start), 6),
                    "end_s": round(float(note.end), 6),
                    "duration": round(float(note.end - note.start), 6),
                    "velocity": int(note.velocity),
                    "source_note_pitch": int(note.pitch),
                    "event_type": _event_type_for_pitch(int(note.pitch)),
                }
            )
    raw_notes.sort(key=lambda row: (float(row["time"]), int(row["source_note_pitch"]), float(row["end_s"])))

    events: list[dict] = []
    for index, note in enumerate(raw_notes, start=1):
        aligned_beat_index, beat_delta = _nearest_beat_alignment(float(note["time"]), beat_times)
        aligned_bar = None
        aligned_beat = None
        aligned_beat_global = None
        if aligned_beat_index is not None:
            beat = beat_points[aligned_beat_index]
            aligned_bar = int(beat["bar"])
            aligned_beat = int(beat["beat_in_bar"])
            aligned_beat_global = int(beat["index"])
        else:
            aligned_bar = _bar_for_time(float(note["time"]), bars)

        section = _section_for_time(float(note["time"]), sections)
        events.append(
            {
                "event_id": f"drum-event-{index:05d}",
                "time": note["time"],
                "end_s": note["end_s"],
                "duration": note["duration"],
                "event_type": note["event_type"],
                "confidence": None,
                "velocity": note["velocity"],
                "source": "drums_stem",
                "transcription_engine": "omnizart",
                "source_note_pitch": note["source_note_pitch"],
                "aligned_beat": aligned_beat,
                "aligned_beat_global": aligned_beat_global,
                "aligned_bar": aligned_bar,
                "beat_time_delta": round(float(beat_delta), 6) if beat_delta is not None else None,
                "alignment_resolved": aligned_beat_index is not None,
                "section_id": section.get("section_id") if section else None,
                "section_name": (section.get("section_character") or section.get("label")) if section else None,
            }
        )
    return events


def _reference_beat_interval(timing: dict) -> float | None:
    beat_times = [float(beat["time"]) for beat in timing.get("beats", [])]
    if len(beat_times) < 2:
        return None
    intervals = [later - earlier for earlier, later in zip(beat_times, beat_times[1:]) if later > earlier]
    if not intervals:
        return None
    return float(median(intervals))


def _quality_flags(events: list[dict], timing: dict) -> list[str]:
    counts = Counter(str(event["event_type"]) for event in events)
    flags: list[str] = []
    if counts["kick"] == 0 or counts["snare"] == 0:
        flags.append("missing_core_backbeat_components")
    if counts["unresolved"] > 0:
        flags.append("unresolved_hits_present")

    beat_interval = _reference_beat_interval(timing)
    hat_times = [float(event["time"]) for event in events if event["event_type"] == "hat"]
    if beat_interval is not None and len(hat_times) >= 2:
        hat_intervals = [later - earlier for earlier, later in zip(hat_times, hat_times[1:]) if later > earlier]
        if hat_intervals:
            median_hat_interval = float(median(hat_intervals))
            if median_hat_interval < beat_interval / 5.0:
                flags.append("hat_density_high")
            elif median_hat_interval > beat_interval * 1.25:
                flags.append("hat_density_sparse")

    aligned_ratio = sum(1 for event in events if event.get("alignment_resolved")) / len(events) if events else 0.0
    if events and aligned_ratio < 0.35:
        flags.append("alignment_coverage_low")
    return flags


def _summary(events: list[dict]) -> dict:
    counts = Counter(str(event["event_type"]) for event in events)
    return {
        "event_count": len(events),
        "kick_count": counts["kick"],
        "snare_count": counts["snare"],
        "hat_count": counts["hat"],
        "unresolved_count": counts["unresolved"],
    }


def extract_drum_events(paths: SongPaths, stems: dict[str, str], timing: dict, sections_payload: dict) -> dict:
    omnizart_dir = ensure_directory(paths.artifact("symbolic_transcription", "omnizart"))
    midi_path = omnizart_dir / "drums.mid"
    midi, model_path, model_source = _transcribe_drums(stems["drums"], midi_path)
    events = _build_events(midi, timing, sections_payload)
    auxiliary_cache_path = paths.artifact("symbolic_transcription", "basic_pitch", "drums.json")

    payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": paths.song_name,
        "generated_from": {
            "source_song_path": str(paths.song_path),
            "engine": "audiohacking.omnizart.drum",
            "dependencies": {
                "drums_stem": stems["drums"],
                "beats_file": str(paths.artifact("essentia", "beats.json")),
                "raw_midi_cache": str(midi_path),
                "model_path": str(model_path),
                "model_source": model_source,
                "auxiliary_note_cache": str(auxiliary_cache_path) if auxiliary_cache_path.exists() else None,
            },
            "debug_sources": {
                "full_mix": str(paths.song_path),
                "drums_stem": stems["drums"],
            },
        },
        "supported_event_types": SUPPORTED_EVENT_TYPES,
        "summary": _summary(events),
        "quality_flags": _quality_flags(events, timing),
        "events": events,
    }
    write_json(paths.artifact("symbolic_transcription", "drum_events.json"), payload)
    return payload