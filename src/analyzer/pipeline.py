from __future__ import annotations

from collections.abc import Callable
import gc
import sys
from typing import TypeVar

from analyzer.config import ValidationConfig
from analyzer.io import ensure_directory, read_json, write_json
from analyzer.exceptions import AnalysisError
from analyzer.models import SCHEMA_VERSION, build_song_schema_fields
from analyzer.paths import SongPaths
from analyzer.stages.gestures import build_gestures
from analyzer.stages.energy import extract_energy_features
from analyzer.stages.energy import derive_energy_layer
from analyzer.stages.genre import classify_genre
from analyzer.stages.drums import extract_drum_events
from analyzer.stages.fft_bands import extract_fft_bands
from analyzer.stages.harmonic import extract_hpcp_and_chords
from analyzer.stages.hint_alignment import build_human_hints_alignment
from analyzer.stages.hints import generate_section_hints
from analyzer.stages.loudness import extract_mix_stem_loudness
from analyzer.stages.segmentation import segment_sections
from analyzer.stages.stems import ensure_stems
from analyzer.stages.timing import extract_timing_grid
from analyzer.stages.ui_data import build_ui_data
from analyzer.stages.validation import (
    build_validation_report,
    skipped_result,
    validate_chords,
    validate_beats,
    write_validation_markdown,
    write_validation_report,
)


_BATCH_PROGRESS: tuple[int, int] | None = None


STAGE_PIPELINE_IDS: dict[str, str] = {
    "ensure-stems": "1.1",
    "extract-timing-grid": "1.2",
    "validate-beats": "1.2",
    "extract-fft-bands": "1.3",
    "extract-mix-stem-loudness": "1.4",
    "extract-hpcp-and-chords": "2.1-2.2",
    "validate-chords": "2.2",
    "extract-drum-events": "2.5",
    "extract-energy-features": "2.6",
    "segment-sections": "3.1",
    "derive-energy-layer": "4.1",
    "build-gestures": "5.0",
    "classify-genre": "6.1",
    "generate-section-hints": "6.2",
    "build-ui-data": "7.2",
    "build-human-hints-alignment": "8.8",
    "build-validation-report": "validation",
    "write-validation-report": "validation",
    "write-validation-markdown": "validation",
}


SINGLE_STAGE_BLOCKLIST: set[str] = {
    "build-validation-report",
    "write-validation-report",
    "write-validation-markdown",
}

SINGLE_STAGE_NAMES: tuple[str, ...] = tuple(
    sorted(stage_name for stage_name in STAGE_PIPELINE_IDS.keys() if stage_name not in SINGLE_STAGE_BLOCKLIST)
)


def _required_artifact_payload(paths: SongPaths, stage_name: str, *artifact_parts: str) -> dict:
    artifact_path = paths.artifact(*artifact_parts)
    if not artifact_path.exists():
        joined = "/".join(artifact_parts)
        raise AnalysisError(
            f"Single-stage execution for '{stage_name}' requires existing artifact '{joined}'. "
            "Run prerequisite stages first or execute the full pipeline once."
        )
    payload = read_json(artifact_path)
    if not isinstance(payload, dict):
        joined = "/".join(artifact_parts)
        raise AnalysisError(f"Artifact '{joined}' must contain a JSON object payload.")
    return payload


def _optional_artifact_payload(paths: SongPaths, *artifact_parts: str) -> dict | None:
    artifact_path = paths.artifact(*artifact_parts)
    if not artifact_path.exists():
        return None
    payload = read_json(artifact_path)
    return payload if isinstance(payload, dict) else None


def _existing_stems(paths: SongPaths, stage_name: str) -> dict[str, str]:
    stems = {
        "bass": paths.stems_dir / "bass.wav",
        "drums": paths.stems_dir / "drums.wav",
        "harmonic": paths.stems_dir / "harmonic.wav",
        "vocals": paths.stems_dir / "vocals.wav",
    }
    missing = [name for name, stem_path in stems.items() if not stem_path.exists()]
    if missing:
        raise AnalysisError(
            f"Single-stage execution for '{stage_name}' requires existing stems for {missing}. "
            "Run 'ensure-stems' first."
        )
    return {name: str(stem_path) for name, stem_path in stems.items()}


def _run_single_stage(paths: SongPaths, config: ValidationConfig, stage_name: str) -> int:
    ensure_directory(paths.song_artifacts_dir)

    if stage_name == "ensure-stems":
        _run_stage(paths.song_name, "phase-1", stage_name, ensure_stems, paths)
        return 0
    if stage_name == "extract-timing-grid":
        stems = _existing_stems(paths, stage_name)
        _run_stage(paths.song_name, "phase-1", stage_name, extract_timing_grid, paths, stems)
        return 0
    if stage_name == "validate-beats":
        timing = _required_artifact_payload(paths, stage_name, "essentia", "beats.json")
        _run_stage(paths.song_name, "phase-1", stage_name, validate_beats, paths, timing, config.beat_tolerance_seconds)
        return 0
    if stage_name == "extract-fft-bands":
        _run_stage(paths.song_name, "phase-1", stage_name, extract_fft_bands, paths)
        return 0
    if stage_name == "extract-mix-stem-loudness":
        stems = _existing_stems(paths, stage_name)
        _run_stage(paths.song_name, "phase-1", stage_name, extract_mix_stem_loudness, paths, stems)
        return 0
    if stage_name == "classify-genre":
        _run_stage(paths.song_name, "phase-1", stage_name, classify_genre, paths)
        return 0
    if stage_name == "extract-hpcp-and-chords":
        stems = _existing_stems(paths, stage_name)
        timing = _required_artifact_payload(paths, stage_name, "essentia", "beats.json")
        _run_stage(paths.song_name, "phase-1", stage_name, extract_hpcp_and_chords, paths, stems, timing)
        return 0
    if stage_name == "validate-chords":
        harmonic = _required_artifact_payload(paths, stage_name, "layer_a_harmonic.json")
        timing = _required_artifact_payload(paths, stage_name, "essentia", "beats.json")
        _run_stage(paths.song_name, "phase-1", stage_name, validate_chords, paths, harmonic, timing, config.chord_min_overlap)
        return 0
    if stage_name == "extract-energy-features":
        timing = _required_artifact_payload(paths, stage_name, "essentia", "beats.json")
        _run_stage(paths.song_name, "phase-1", stage_name, extract_energy_features, paths, timing)
        return 0
    if stage_name == "segment-sections":
        stems = _existing_stems(paths, stage_name)
        timing = _required_artifact_payload(paths, stage_name, "essentia", "beats.json")
        _run_stage(paths.song_name, "phase-1", stage_name, segment_sections, paths, stems, timing)
        return 0
    if stage_name == "extract-drum-events":
        stems = _existing_stems(paths, stage_name)
        timing = _required_artifact_payload(paths, stage_name, "essentia", "beats.json")
        sections = _required_artifact_payload(paths, stage_name, "section_segmentation", "sections.json")
        _run_stage(paths.song_name, "phase-1", stage_name, extract_drum_events, paths, stems, timing, sections)
        return 0
    if stage_name == "generate-section-hints":
        sections = _required_artifact_payload(paths, stage_name, "section_segmentation", "sections.json")
        _run_stage(paths.song_name, "phase-1", stage_name, generate_section_hints, paths, sections)
        return 0
    if stage_name == "build-ui-data":
        _run_stage(paths.song_name, "phase-1", stage_name, build_ui_data, paths)
        return 0
    if stage_name == "derive-energy-layer":
        timing = _required_artifact_payload(paths, stage_name, "essentia", "beats.json")
        energy_features = _run_stage(paths.song_name, "phase-1", "extract-energy-features", extract_energy_features, paths, timing)
        sections = _required_artifact_payload(paths, stage_name, "section_segmentation", "sections.json")
        _run_stage(paths.song_name, "phase-1", stage_name, derive_energy_layer, paths, timing, energy_features, sections)
        return 0
    if stage_name == "build-gestures":
        fft_bands = _required_artifact_payload(paths, stage_name, "essentia", "fft_bands.json")
        rms_loudness = _required_artifact_payload(paths, stage_name, "essentia", "rms_loudness.json")
        drum_events = _required_artifact_payload(paths, stage_name, "symbolic_transcription", "drum_events.json")
        timing = _required_artifact_payload(paths, stage_name, "essentia", "beats.json")
        sections = _required_artifact_payload(paths, stage_name, "section_segmentation", "sections.json")
        _run_stage(paths.song_name, "phase-1", stage_name, build_gestures, paths, fft_bands, rms_loudness, drum_events, timing, sections)
        return 0
    if stage_name == "build-human-hints-alignment":
        _run_stage(paths.song_name, "phase-1", stage_name, build_human_hints_alignment, paths)
        return 0

    raise AnalysisError(
        f"Single-stage execution for '{stage_name}' is not supported. "
        f"Supported stages: {list(SINGLE_STAGE_NAMES)}"
    )


def set_batch_progress(current_song: int, total_songs: int) -> None:
    if current_song < 1:
        raise ValueError("current_song must be >= 1")
    if total_songs < 1:
        raise ValueError("total_songs must be >= 1")
    if current_song > total_songs:
        raise ValueError("current_song must be <= total_songs")

    global _BATCH_PROGRESS
    _BATCH_PROGRESS = (current_song, total_songs)


def clear_batch_progress() -> None:
    global _BATCH_PROGRESS
    _BATCH_PROGRESS = None


def format_batch_progress_prefix() -> str:
    if _BATCH_PROGRESS is None:
        return ""

    current_song, total_songs = _BATCH_PROGRESS
    return f"[{current_song}/{total_songs}]"


def _print_phase_marker(song_name: str, phase_name: str, edge: str) -> None:
    print(f"{format_batch_progress_prefix()}{song_name}-{phase_name}-{edge}", flush=True)


def _print_stage_marker(song_name: str, _phase_name: str, stage_name: str) -> None:
    stage_id = STAGE_PIPELINE_IDS.get(stage_name)
    if stage_id:
        # Extract the major epic number (e.g. "1.2" -> "1", "2.1-2.2" -> "2")
        epic_num = stage_id.split(".")[0]
        stage_prefix = f"[EPIC {epic_num} | {stage_id}] "
    else:
        stage_prefix = ""
    print(f"{format_batch_progress_prefix()}{stage_prefix}{song_name} | {stage_name}", flush=True)


StageResult = TypeVar("StageResult")


def _release_gpu_memory() -> None:
    # Always collect Python references first.
    gc.collect()

    torch_module = sys.modules.get("torch")
    if torch_module is not None:
        try:
            if torch_module.cuda.is_available():
                torch_module.cuda.empty_cache()
                torch_module.cuda.ipc_collect()
        except Exception:
            pass

    tensorflow_module = sys.modules.get("tensorflow")
    if tensorflow_module is not None:
        try:
            tensorflow_module.keras.backend.clear_session()
        except Exception:
            pass


def _run_stage(
    song_name: str,
    phase_name: str,
    stage_name: str,
    operation: Callable[..., StageResult],
    *args: object,
    **kwargs: object,
) -> StageResult:
    _release_gpu_memory()
    _print_stage_marker(song_name, phase_name, stage_name)
    try:
        return operation(*args, **kwargs)
    finally:
        _release_gpu_memory()


def run_phase_1(paths: SongPaths, config: ValidationConfig, stage_name: str | None = None) -> int:
    _print_phase_marker(paths.song_name, "phase-1", "start")
    try:
        if stage_name is not None:
            return _run_single_stage(paths, config, stage_name)

        ensure_directory(paths.song_artifacts_dir)
        stems = _run_stage(paths.song_name, "phase-1", "ensure-stems", ensure_stems, paths)
        # extract-timing-grid (1.2) now needs allin1's downbeat activation
        # (item 8) before segment-sections (3.1) runs later in this function —
        # stems are already available from ensure-stems, so
        # `analyzer.allin1_cache.get_allin1_result` triggers the one allin1
        # run here and segment-sections reads the cache it wrote. See
        # the v3.0 plan's item 8 resolved ordering note (plan deleted with the
        # release; recoverable via `git log --diff-filter=D -- docs/`).
        timing = _run_stage(paths.song_name, "phase-1", "extract-timing-grid", extract_timing_grid, paths, stems)
        fft_bands = _run_stage(paths.song_name, "phase-1", "extract-fft-bands", extract_fft_bands, paths)
        loudness = _run_stage(paths.song_name, "phase-1", "extract-mix-stem-loudness", extract_mix_stem_loudness, paths, stems)
        beat_validation = (
            _run_stage(
                paths.song_name,
                "phase-1",
                "validate-beats",
                validate_beats,
                paths,
                timing,
                config.beat_tolerance_seconds,
            )
            if "beats" in config.compare_targets
            else skipped_result()
        )
        _, harmonic = _run_stage(paths.song_name, "phase-1", "extract-hpcp-and-chords", extract_hpcp_and_chords, paths, stems, timing)
        chord_validation = (
            _run_stage(
                paths.song_name,
                "phase-1",
                "validate-chords",
                validate_chords,
                paths,
                harmonic,
                timing,
                config.chord_min_overlap,
            )
            if "chords" in config.compare_targets
            else skipped_result()
        )
        energy_features = _run_stage(paths.song_name, "phase-1", "extract-energy-features", extract_energy_features, paths, timing)
        sections = _run_stage(paths.song_name, "phase-1", "segment-sections", segment_sections, paths, stems, timing)
        drum_events = _run_stage(paths.song_name, "phase-1", "extract-drum-events", extract_drum_events, paths, stems, timing, sections)
        genre_result = _run_stage(paths.song_name, "phase-1", "classify-genre", classify_genre, paths)
        energy = _run_stage(paths.song_name, "phase-1", "derive-energy-layer", derive_energy_layer, paths, timing, energy_features, sections)
        event_timeline = _run_stage(
            paths.song_name,
            "phase-1",
            "build-gestures",
            build_gestures,
            paths,
            fft_bands,
            loudness["rms_loudness"],
            drum_events,
            timing,
            sections,
        )
        hints = _run_stage(paths.song_name, "phase-1", "generate-section-hints", generate_section_hints, paths, sections)
        ui_outputs = _run_stage(paths.song_name, "phase-1", "build-ui-data", build_ui_data, paths)
        human_hint_alignment = _run_stage(paths.song_name, "phase-1", "build-human-hints-alignment", build_human_hints_alignment, paths)

        info_payload = {
            "schema_version": SCHEMA_VERSION,
            **build_song_schema_fields(paths, bpm=timing["bpm"], duration=timing["duration"]),
            "song_path": str(paths.song_path),
            "artifacts": {
                "beats": str(paths.artifact("essentia", "beats.json")),
                "fft_bands": str(paths.artifact("essentia", "fft_bands.json")),
                "rms_loudness": str(paths.artifact("essentia", "rms_loudness.json")),
                "loudness_envelope": str(paths.artifact("essentia", "loudness_envelope.json")),
                "genre": str(paths.artifact("genre.json")),
                "hpcp": str(paths.artifact("essentia", "hpcp.json")),
                "harmonic_layer": str(paths.artifact("layer_a_harmonic.json")),
                "drum_events": str(paths.artifact("symbolic_transcription", "drum_events.json")),
                "drum_midi": str(paths.artifact("symbolic_transcription", "omnizart", "drums.mid")),
                "energy_layer": str(paths.artifact("layer_c_energy.json")),
                "song_facts": str(paths.reference("human", "song_facts.json")),
                "human_hints_alignment": human_hint_alignment["json_path"] if human_hint_alignment else None,
                "human_hints_alignment_markdown": human_hint_alignment["markdown_path"] if human_hint_alignment else None,
                "sections": str(paths.artifact("section_segmentation", "sections.json")),
            },
            "generated_from": {
                "source_song_path": str(paths.song_path),
                "timing_grid": str(paths.artifact("essentia", "beats.json")),
                "fft_bands_file": str(paths.artifact("essentia", "fft_bands.json")),
                "rms_loudness_file": str(paths.artifact("essentia", "rms_loudness.json")),
                "loudness_envelope_file": str(paths.artifact("essentia", "loudness_envelope.json")),
            },
            "outputs": {
                "beats": ui_outputs["beats"],
                "hints": hints["hints"],
                "sections": ui_outputs["sections"],
                "song_event_timeline": str(paths.timeline_output_path),
            },
            "debug": {
                "fft_band_count": len(fft_bands.get("bands", [])),
                "loudness_source_count": len(loudness["rms_loudness"].get("sources", [])),
                "drum_events_engine": drum_events["generated_from"]["engine"],
            },
        }
        write_json(paths.info_output_path, info_payload)

        report, exit_code = _run_stage(
            paths.song_name,
            "phase-1",
            "build-validation-report",
            build_validation_report,
            paths=paths,
            compare_targets=config.compare_targets,
            beat_validation=beat_validation,
            chord_validation=chord_validation,
            beat_tolerance_seconds=config.beat_tolerance_seconds,
            tolerance_seconds=config.tolerance_seconds,
            chord_min_overlap=config.chord_min_overlap,
            fail_on_mismatch=config.fail_on_mismatch,
        )
        if human_hint_alignment:
            report["generated_artifacts"]["human_hints_alignment_file"] = human_hint_alignment["json_path"]
            report["generated_artifacts"]["human_hints_alignment_markdown"] = human_hint_alignment["markdown_path"]
            report["notes"].append("Human hint alignment review files compare narrative hint windows against generated sections, events, and harmonic events when human hints are available.")
        _run_stage(paths.song_name, "phase-1", "write-validation-report", write_validation_report, report, config.report_json)
        _run_stage(paths.song_name, "phase-1", "write-validation-markdown", write_validation_markdown, report, config.report_md)
        return exit_code
    finally:
        _print_phase_marker(paths.song_name, "phase-1", "end")
