"""Omnizart drum transcription on the isolated drums stem.

**Vocabulary bound.** Omnizart emits three General MIDI pitches only —
35 (kick), 38 (snare), 42 (hi-hat). `velocity` is a constant 100 and is not
published. `confidence` is `null` (Omnizart exposes no per-hit score).
Toms and congas are folded into kick or snare — a *known* wrong label, not a
silent one.

**v3.4 crash/hat split.** The one taxonomy change in v3.4: a pitch-42 event is
reclassified `hat` -> `crash` from the drums-stem 6-16 kHz brilliance band in
`artifacts/essentia/fft_bands.drums.json`. Nothing else widened. Thresholds and
their derivation are the `CRASH_*` constants below. If `fft_bands.drums.json`
is absent the stage raises `DependencyError` — there is no fallback to
"everything is hat".

Measured split (pitch-42 events -> `crash`, threshold
brilliance >= 0.90 & transient >= 0.40 within +/- 0.12 s):

| song | pitch-42 | -> crash | notes |
| --- | --- | --- | --- |
| `Armin - Revolution` | 656 | 10 (2%) | gold song |
| `Queen of Kings - Alessandra` | 476 | 43 (9%) | a `crash` lands 0.08 s from the 48.7 s drop |
| `_test_song` | 179 | 35 (20%) | synthetic corpus fixture, crash-heavy drums stem |

`Titanium` / `Hideaway`: measurement pending — no `fft_bands.drums.json` yet
and Omnizart is CPU-only in this runtime, so a full re-analysis was
impractical this pass.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
import subprocess
from statistics import median
import sys

from analyzer.exceptions import AnalysisError, DependencyError
from analyzer.io import ensure_directory, read_json, write_json
from analyzer.models import SCHEMA_VERSION
from analyzer.paths import SongPaths
from analyzer.stages._omnizart_runtime import resolve_omnizart_drum_model_path


SUPPORTED_EVENT_TYPES = ["kick", "snare", "hat", "crash", "unresolved"]
KICK_PITCHES = {35, 36}
SNARE_PITCHES = {37, 38, 39, 40}
HAT_PITCHES = {42, 44, 46}

# --- crash / hat split on GM pitch 42 -------------------------------------
# Omnizart emits only GM pitches 35/38/42, so a crash cymbal and a closed
# hi-hat both arrive as pitch 42. They are split here from the drums-stem
# 6-16 kHz "brilliance" band in artifacts/essentia/fft_bands.drums.json
# (fft_bands.py BAND_DEFINITIONS[-1]; frame `levels` index 6), read at the
# event frame. A crash is a strong broadband onset that floods the top
# octave with a sustained wash; a closed hat is a short low-energy tick.
#
# Thresholds (measured constants — NOT tuned per song):
#   * CRASH_BRILLIANCE_LEVEL 0.90 — the brilliance `levels` value is
#     _robust_normalize'd against that stem's own 5th-95th percentile
#     (fft_bands.py), so >= 0.90 is the top of the drums stem's own 6-16 kHz
#     dynamic range. A closed-hat tick sits well below its own ceiling; a
#     crash wash pins it.
#   * CRASH_TRANSIENT_STRENGTH 0.40 — the frame's broadband positive-delta
#     transient magnitude (normalized 0-1). On _test_song's 1162 drums-stem
#     frames the 95th percentile is 0.147 and the 99th is 0.734, so 0.40
#     isolates genuine accented onsets from the steady hat pulse. It was
#     lowered from an initial 0.50 because the `Queen of Kings` 48.7 s drop
#     cymbal peaks at transient_strength 0.40 (the frame at 48.70 s), and
#     0.50 missed it.
# Both must hold within the window (event time - 0.12 s .. + 0.12 s). The
# 0.12 s lead is deliberate: a crash's spectral onset routinely precedes
# Omnizart's quantized note start by 50-100 ms (on `Queen of Kings` the
# 48.70 s transient carries an Omnizart hat at 48.78 s).
#
# Measured split (pitch-42 events reclassified to `crash`, recompute over
# the artifacts that already carry fft_bands.drums.json):
#   * Armin - Revolution          : 10 / 656  (2%)
#   * Queen of Kings - Alessandra : 43 / 476  (9%) — a `crash` lands 0.08 s
#                                   from the operator-marked 48.7 s drop
#   * _test_song                  : 35 / 179  (20%, synthetic corpus fixture)
# Titanium / Hideaway: measurement pending (no fft_bands.drums.json yet;
# Omnizart is CPU-only here so a full re-analysis was impractical this pass).
# A `crash` count of zero on every measured song means these constants are
# wrong.
CRASH_BRILLIANCE_BAND_INDEX = 6
CRASH_BRILLIANCE_LEVEL = 0.90
CRASH_TRANSIENT_STRENGTH = 0.40
CRASH_WINDOW_BEFORE_S = 0.12
CRASH_WINDOW_AFTER_S = 0.12


def _nearest_beat_alignment(time_s: float, beat_times: list[float], tolerance_seconds: float = 0.2) -> tuple[int | None, float | None]:
    if not beat_times:
        return None, None
    beat_index = min(range(len(beat_times)), key=lambda index: abs(beat_times[index] - time_s))
    delta = float(time_s - beat_times[beat_index])
    if abs(delta) > tolerance_seconds:
        return None, delta
    return beat_index, delta


def _section_for_time(time_s: float, sections: list[dict]) -> dict | None:
    for section in sections:
        if float(section["start"]) <= time_s < float(section["end"]):
            return section
    if sections and time_s >= float(sections[-1]["start"]):
        return sections[-1]
    return None


def _event_type_for_pitch(pitch: int) -> str:
    if pitch in KICK_PITCHES:
        return "kick"
    if pitch in SNARE_PITCHES:
        return "snare"
    if pitch in HAT_PITCHES:
        return "hat"
    return "unresolved"


def _load_drums_brilliance_frames(paths: SongPaths) -> list[dict]:
    """Read the drums-stem 7-band spectra written by `extract-fft-bands`.

    Absent artifact -> `DependencyError` (extract-fft-bands runs before
    extract-drum-events in the full pipeline; the single-stage path gates on
    it in pipeline.py). No fallback to "call every pitch-42 event `hat`".
    """
    artifact_path = paths.artifact("essentia", "fft_bands.drums.json")
    if not artifact_path.exists():
        raise DependencyError(
            f"drums crash/hat split requires '{artifact_path}'. "
            "Run 'extract-fft-bands' first (it emits fft_bands.<stem>.json)."
        )
    payload = read_json(artifact_path)
    frames = payload.get("frames") if isinstance(payload, dict) else None
    if not isinstance(frames, list) or not frames:
        raise AnalysisError(f"fft_bands.drums.json carries no frames: {artifact_path}")
    return frames


def _window_extremum(frames: list[dict], time_s: float, key_fn) -> float:
    """Max of `key_fn(frame)` over frames in [time - before, time + after]."""
    interval_ms = 50.0
    start_time = time_s - CRASH_WINDOW_BEFORE_S
    end_time = time_s + CRASH_WINDOW_AFTER_S
    hi = 0.0
    seen = False
    for frame in frames:
        frame_time = float(frame.get("time", 0.0))
        if frame_time < start_time - interval_ms / 1000.0:
            continue
        if frame_time > end_time:
            break
        value = key_fn(frame)
        if value is None:
            continue
        hi = max(hi, float(value)) if seen else float(value)
        seen = True
    return hi if seen else 0.0


def _reclassify_crashes(events: list[dict], frames: list[dict]) -> int:
    """Split `crash` out of pitch-42 `hat` events from the brilliance band.

    Returns the number of events relabelled. Only pitch-42 `hat` events are
    touched; every other event is left exactly as `_event_type_for_pitch`
    decided it.
    """
    relabelled = 0
    for event in events:
        if event.get("event_type") != "hat" or int(event.get("source_note_pitch", 0)) != 42:
            continue
        time_s = float(event["time"])
        brilliance = _window_extremum(
            frames, time_s, lambda f: (f.get("levels") or [None] * 7)[CRASH_BRILLIANCE_BAND_INDEX]
        )
        transient = _window_extremum(frames, time_s, lambda f: f.get("transient_strength"))
        if brilliance >= CRASH_BRILLIANCE_LEVEL and transient >= CRASH_TRANSIENT_STRENGTH:
            event["event_type"] = "crash"
            relabelled += 1
    return relabelled


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
                "section_name": section.get("function") if section else None,
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
        "crash_count": counts["crash"],
        "unresolved_count": counts["unresolved"],
    }


def extract_drum_events(paths: SongPaths, stems: dict[str, str], timing: dict, sections_payload: dict) -> dict:
    omnizart_dir = ensure_directory(paths.artifact("symbolic_transcription", "omnizart"))
    midi_path = omnizart_dir / "drums.mid"
    transcription_status = "ok"
    transcription_error = None
    model_path: Path | None = None
    model_source: str | None = None

    # Fail explicitly if the crash/hat split input is missing — before any
    # transcription work, and outside the graceful-degradation catch below.
    brilliance_frames = _load_drums_brilliance_frames(paths)

    try:
        midi, model_path, model_source = _transcribe_drums(stems["drums"], midi_path)
        events = _build_events(midi, timing, sections_payload)
        _reclassify_crashes(events, brilliance_frames)
    except (AnalysisError, DependencyError) as exc:
        # Story contract: fail gracefully when the named dependency cannot execute.
        transcription_status = "failed"
        transcription_error = str(exc)
        events = []

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
                "model_path": str(model_path) if model_path is not None else None,
                "model_source": model_source,
            },
            "debug_sources": {
                "full_mix": str(paths.song_path),
                "drums_stem": stems["drums"],
            },
            "transcription_status": transcription_status,
            "transcription_error": transcription_error,
        },
        "supported_event_types": SUPPORTED_EVENT_TYPES,
        "summary": _summary(events),
        "quality_flags": (
            _quality_flags(events, timing)
            if transcription_status == "ok"
            else ["transcription_failed"]
        ),
        "events": events,
    }
    write_json(paths.artifact("symbolic_transcription", "drum_events.json"), payload)
    return payload