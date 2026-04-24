from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from analyzer.config import ValidationConfig
from analyzer.io import ensure_directory, write_json
from analyzer.exceptions import AnalysisError
from analyzer.models import SCHEMA_VERSION, build_song_schema_fields
from analyzer.paths import SongPaths
from analyzer.stages.event_benchmark import benchmark_event_outputs
from analyzer.stages.event_ml import generate_ml_events
from analyzer.stages.event_features import build_event_feature_layer
from analyzer.stages.event_identifiers import infer_song_identifiers
from analyzer.stages.event_machine import generate_machine_events
from analyzer.stages.event_rules import generate_rule_candidates
from analyzer.stages.event_review import generate_event_review
from analyzer.stages.event_timeline import export_event_timeline
from analyzer.stages.energy import extract_energy_features
from analyzer.stages.energy import derive_energy_layer
from analyzer.stages.genre import classify_genre
from analyzer.stages.drums import extract_drum_events
from analyzer.stages.fft_bands import extract_fft_bands
from analyzer.stages.harmonic import build_reference_harmonic_layer, extract_hpcp_and_chords
from analyzer.stages.hint_alignment import build_human_hints_alignment
from analyzer.stages.hints import generate_section_hints
from analyzer.stages.light_design import generate_lighting_score
from analyzer.stages.lighting import generate_lighting_events
from analyzer.stages.loudness import extract_mix_stem_loudness
from analyzer.stages.patterns import extract_chord_patterns
from analyzer.stages.sections_v2 import segment_sections
from analyzer.stages.symbolic import extract_symbolic_features
from analyzer.stages.stems import ensure_stems
from analyzer.stages.timing import build_reference_timing_grid, extract_timing_grid
from analyzer.stages.ui_data import build_ui_data
from analyzer.stages.unified import assemble_music_feature_layers
from analyzer.stages.validation import (
    build_validation_report,
    generate_timing_diagnosis,
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
    "build-reference-timing-grid": "1.2",
    "validate-beats": "1.2",
    "generate-timing-diagnosis": "1.2",
    "extract-fft-bands": "1.3",
    "extract-mix-stem-loudness": "1.4",
    "extract-hpcp-and-chords": "2.1-2.2",
    "build-reference-harmonic-layer": "2.1-2.2",
    "validate-chords": "2.2",
    "extract-chord-patterns": "2.3",
    "extract-symbolic-features": "2.4-4.3",
    "extract-drum-events": "2.5",
    "extract-energy-features": "2.6",
    "segment-sections": "3.1",
    "derive-energy-layer": "4.1",
    "build-event-feature-layer": "4.4",
    "infer-song-identifiers": "4.5",
    "generate-rule-candidates": "5.2",
    "generate-ml-events": "5.3",
    "generate-machine-events": "5.4",
    "generate-event-review": "5.5",
    "benchmark-event-outputs": "5.5",
    "export-event-timeline": "5.6",
    "classify-genre": "6.1",
    "generate-section-hints": "6.2",
    "assemble-music-feature-layers": "7.1",
    "build-ui-data": "7.2",
    "generate-lighting-events": "7.3",
    "generate-lighting-score": "7.4",
    "build-human-hints-alignment": "8.8",
    "build-validation-report": "validation",
    "write-validation-report": "validation",
    "write-validation-markdown": "validation",
}


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


def _run_stage(
    song_name: str,
    phase_name: str,
    stage_name: str,
    operation: Callable[..., StageResult],
    *args: object,
    **kwargs: object,
) -> StageResult:
    _print_stage_marker(song_name, phase_name, stage_name)
    return operation(*args, **kwargs)


def run_phase_1(paths: SongPaths, config: ValidationConfig) -> int:
    _print_phase_marker(paths.song_name, "phase-1", "start")
    try:
        ensure_directory(paths.song_artifacts_dir)
        reference_chords_path = paths.reference("moises", "chords.json")
        has_reference_chords = reference_chords_path is not None and reference_chords_path.exists()
        stems = _run_stage(paths.song_name, "phase-1", "ensure-stems", ensure_stems, paths)
        timing = _run_stage(paths.song_name, "phase-1", "extract-timing-grid", extract_timing_grid, paths)
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
        inferred_beats_path: str | None = None
        if has_reference_chords:
            inferred_beats_path = paths.artifact("essentia", "beats_inferred.json")
            inferred_timing = timing
            write_json(inferred_beats_path, inferred_timing)
            timing = _run_stage(
                paths.song_name,
                "phase-1",
                "build-reference-timing-grid",
                build_reference_timing_grid,
                paths,
                float(inferred_timing.get("duration", 0.0)),
                reference_chords_path=str(reference_chords_path),
                inferred_beats_path=str(inferred_beats_path),
            )
            if not timing.get("beats"):
                raise AnalysisError("Reference timing takeover did not produce any canonical beats")
            write_json(paths.artifact("essentia", "beats.json"), timing)
            _run_stage(
                paths.song_name,
                "phase-1",
                "generate-timing-diagnosis",
                generate_timing_diagnosis,
                paths,
                inferred_timing,
                timing,
            )
        genre_result = _run_stage(paths.song_name, "phase-1", "classify-genre", classify_genre, paths)
        _, harmonic = _run_stage(paths.song_name, "phase-1", "extract-hpcp-and-chords", extract_hpcp_and_chords, paths, stems, timing)
        chord_validation = (
            _run_stage(
                paths.song_name,
                "phase-1",
                "validate-chords",
                validate_chords,
                paths,
                harmonic,
                config.chord_min_overlap,
            )
            if "chords" in config.compare_targets
            else skipped_result()
        )
        inferred_harmonic_path: str | None = None
        if has_reference_chords:
            inferred_harmonic_path = paths.artifact("harmonic_inference", "layer_a_harmonic.inferred.json")
            write_json(inferred_harmonic_path, harmonic)
            harmonic = _run_stage(
                paths.song_name,
                "phase-1",
                "build-reference-harmonic-layer",
                build_reference_harmonic_layer,
                paths,
                timing,
                inferred_harmonic_path=str(inferred_harmonic_path),
            )
        energy_features = _run_stage(paths.song_name, "phase-1", "extract-energy-features", extract_energy_features, paths, timing)
        sections = _run_stage(paths.song_name, "phase-1", "segment-sections", segment_sections, paths, timing, harmonic, energy_features)
        symbolic = _run_stage(paths.song_name, "phase-1", "extract-symbolic-features", extract_symbolic_features, paths, stems, timing, sections)
        drum_events = _run_stage(paths.song_name, "phase-1", "extract-drum-events", extract_drum_events, paths, stems, timing, sections)
        hints = _run_stage(paths.song_name, "phase-1", "generate-section-hints", generate_section_hints, paths, symbolic, sections)
        ui_outputs = _run_stage(paths.song_name, "phase-1", "build-ui-data", build_ui_data, paths)
        energy = _run_stage(paths.song_name, "phase-1", "derive-energy-layer", derive_energy_layer, paths, timing, energy_features, sections)
        event_features = _run_stage(
            paths.song_name,
            "phase-1",
            "build-event-feature-layer",
            build_event_feature_layer,
            paths,
            timing,
            harmonic,
            symbolic,
            energy_features,
            energy,
            sections,
            genre_result,
        )
        ml_events = _run_stage(paths.song_name, "phase-1", "generate-ml-events", generate_ml_events, paths)
        rule_candidates = _run_stage(paths.song_name, "phase-1", "generate-rule-candidates", generate_rule_candidates, paths, event_features, sections, genre_result)
        event_identifiers = _run_stage(
            paths.song_name,
            "phase-1",
            "infer-song-identifiers",
            infer_song_identifiers,
            paths,
            energy,
            sections,
        )
        machine_events = _run_stage(
            paths.song_name,
            "phase-1",
            "generate-machine-events",
            generate_machine_events,
            paths,
            event_features,
            rule_candidates,
            event_identifiers,
            symbolic,
            sections,
        )
        review_outputs = _run_stage(paths.song_name, "phase-1", "generate-event-review", generate_event_review, paths, machine_events)
        event_timeline = _run_stage(paths.song_name, "phase-1", "export-event-timeline", export_event_timeline, paths, review_outputs["merged_payload"])
        event_benchmark = _run_stage(
            paths.song_name,
            "phase-1",
            "benchmark-event-outputs",
            benchmark_event_outputs,
            paths,
            review_outputs["merged_payload"],
            genre_result,
        )
        patterns = _run_stage(paths.song_name, "phase-1", "extract-chord-patterns", extract_chord_patterns, paths, timing, harmonic)
        unified = _run_stage(
            paths.song_name,
            "phase-1",
            "assemble-music-feature-layers",
            assemble_music_feature_layers,
            paths,
            timing,
            harmonic,
            symbolic,
            energy,
            patterns,
            sections,
        )
        lighting = _run_stage(paths.song_name, "phase-1", "generate-lighting-events", generate_lighting_events, paths)
        lighting_score = _run_stage(paths.song_name, "phase-1", "generate-lighting-score", generate_lighting_score, paths)
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
                "symbolic_layer": str(paths.artifact("layer_b_symbolic.json")),
                "drum_events": str(paths.artifact("symbolic_transcription", "drum_events.json")),
                "drum_midi": str(paths.artifact("symbolic_transcription", "omnizart", "drums.mid")),
                "symbolic_hints": hints["symbolic_hints"],
                "symbolic_validation": str(paths.artifact("symbolic_transcription", "validation.json")),
                "energy_features": str(paths.artifact("energy_summary", "features.json")),
                "energy_layer": str(paths.artifact("layer_c_energy.json")),
                "energy_identifiers": str(paths.artifact("energy_summary", "hints.json")),
                "event_features": str(paths.artifact("event_inference", "features.json")),
                "event_timeline_index": str(paths.artifact("event_inference", "timeline_index.json")),
                "event_rule_candidates": str(paths.artifact("event_inference", "rule_candidates.json")),
                "event_machine": str(paths.artifact("event_inference", "events.machine.json")),
                "event_review": str(paths.review_json_path),
                "event_overrides": str(paths.overrides_path),
                "event_timeline_markdown": str(paths.timeline_md_path),
                "event_benchmark": str(paths.artifact("validation", "event_benchmark.json")),
                "human_hints_alignment": human_hint_alignment["json_path"] if human_hint_alignment else None,
                "human_hints_alignment_markdown": human_hint_alignment["markdown_path"] if human_hint_alignment else None,
                "sections": str(paths.artifact("section_segmentation", "sections.json")),
                "patterns_layer": str(paths.artifact("layer_d_patterns.json")),
                "pattern_mining": str(paths.artifact("pattern_mining", "chord_patterns.json")),
                "music_feature_layers": str(paths.artifact("music_feature_layers.json")),
                "lighting_events": str(paths.artifact("lighting_events.json")),
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
                "lighting_score": str(paths.lighting_score_output_path),
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
        if inferred_beats_path is not None:
            report["generated_artifacts"]["inferred_beats_file"] = str(inferred_beats_path)
            report["notes"].append("Moises chord reference data was present, so downstream phases used the canonical beat grid rebuilt from that reference while preserving the inferred beat grid separately for diagnostics.")
        if inferred_harmonic_path is not None:
            report["generated_artifacts"]["inferred_harmonic_file"] = str(inferred_harmonic_path)
            report["notes"].append("Moises chord reference data was present, so downstream phases used the canonical harmonic layer rebuilt from that reference while preserving the inferred harmonic layer separately for diagnostics.")
        if human_hint_alignment:
            report["generated_artifacts"]["human_hints_alignment_file"] = human_hint_alignment["json_path"]
            report["generated_artifacts"]["human_hints_alignment_markdown"] = human_hint_alignment["markdown_path"]
            report["notes"].append("Human hint alignment review files compare narrative hint windows against generated sections, events, patterns, and harmonic events when human hints are available.")
        _run_stage(paths.song_name, "phase-1", "write-validation-report", write_validation_report, report, config.report_json)
        _run_stage(paths.song_name, "phase-1", "write-validation-markdown", write_validation_markdown, report, config.report_md)
        return exit_code
    finally:
        _print_phase_marker(paths.song_name, "phase-1", "end")
