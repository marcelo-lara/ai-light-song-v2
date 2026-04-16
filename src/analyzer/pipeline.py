from __future__ import annotations

from analyzer.config import ValidationConfig
from analyzer.io import ensure_directory, write_json
from analyzer.exceptions import AnalysisError
from analyzer.models import SCHEMA_VERSION, build_song_schema_fields
from analyzer.paths import SongPaths
from analyzer.stages.event_benchmark import benchmark_event_outputs
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
from analyzer.stages.harmonic import build_reference_harmonic_layer, extract_hpcp_and_chords
from analyzer.stages.hint_alignment import build_human_hints_alignment
from analyzer.stages.hints import generate_section_hints
from analyzer.stages.light_design import generate_lighting_score
from analyzer.stages.lighting import generate_lighting_events
from analyzer.stages.patterns import extract_chord_patterns
from analyzer.stages.sections_v2 import segment_sections
from analyzer.stages.symbolic import extract_symbolic_features
from analyzer.stages.stems import ensure_stems
from analyzer.stages.timing import build_reference_timing_grid, extract_timing_grid
from analyzer.stages.ui_data import build_ui_data
from analyzer.stages.unified import assemble_music_feature_layers
from analyzer.stages.validation import (
    build_validation_report,
    skipped_result,
    validate_chords,
    validate_beats,
    write_validation_markdown,
    write_validation_report,
)


def _print_phase_marker(song_name: str, phase_name: str, edge: str) -> None:
    print(f"{song_name}-{phase_name}-{edge}", flush=True)


def run_phase_1(paths: SongPaths, config: ValidationConfig) -> int:
    _print_phase_marker(paths.song_name, "phase-1", "start")
    try:
        ensure_directory(paths.song_artifacts_dir)
        reference_chords_path = paths.reference("moises", "chords.json")
        has_reference_chords = reference_chords_path is not None and reference_chords_path.exists()
        stems = ensure_stems(paths)
        timing = extract_timing_grid(paths)
        beat_validation = (
            validate_beats(paths, timing, config.beat_tolerance_seconds)
            if "beats" in config.compare_targets
            else skipped_result()
        )
        inferred_beats_path: str | None = None
        if has_reference_chords:
            inferred_beats_path = paths.artifact("essentia", "beats_inferred.json")
            write_json(inferred_beats_path, timing)
            timing = build_reference_timing_grid(
                paths,
                float(timing.get("duration", 0.0)),
                reference_chords_path=str(reference_chords_path),
                inferred_beats_path=str(inferred_beats_path),
            )
            if not timing.get("beats"):
                raise AnalysisError("Reference timing takeover did not produce any canonical beats")
            write_json(paths.artifact("essentia", "beats.json"), timing)
        genre_result = classify_genre(paths)
        _, harmonic = extract_hpcp_and_chords(paths, stems, timing)
        chord_validation = (
            validate_chords(paths, harmonic, config.chord_min_overlap)
            if "chords" in config.compare_targets
            else skipped_result()
        )
        inferred_harmonic_path: str | None = None
        if has_reference_chords:
            inferred_harmonic_path = paths.artifact("harmonic_inference", "layer_a_harmonic.inferred.json")
            write_json(inferred_harmonic_path, harmonic)
            harmonic = build_reference_harmonic_layer(
                paths,
                timing,
                inferred_harmonic_path=str(inferred_harmonic_path),
            )
        energy_features = extract_energy_features(paths, timing)
        sections = segment_sections(paths, timing, harmonic, energy_features)
        symbolic = extract_symbolic_features(paths, stems, timing, sections)
        drum_events = extract_drum_events(paths, stems, timing, sections)
        hints = generate_section_hints(paths, symbolic, sections)
        ui_outputs = build_ui_data(paths)
        energy = derive_energy_layer(paths, timing, energy_features, sections)
        event_features = build_event_feature_layer(paths, timing, harmonic, symbolic, energy_features, energy, sections, genre_result)
        rule_candidates = generate_rule_candidates(paths, event_features, sections, genre_result)
        event_identifiers = infer_song_identifiers(paths, event_features, energy_features, energy, rule_candidates, sections)
        machine_events = generate_machine_events(paths, event_features, rule_candidates, event_identifiers, symbolic, sections)
        review_outputs = generate_event_review(paths, machine_events)
        event_timeline = export_event_timeline(paths, review_outputs["merged_payload"])
        event_benchmark = benchmark_event_outputs(paths, review_outputs["merged_payload"], genre_result)
        patterns = extract_chord_patterns(paths, timing, harmonic)
        unified = assemble_music_feature_layers(paths, timing, harmonic, symbolic, energy, patterns, sections)
        lighting = generate_lighting_events(paths)
        lighting_score = generate_lighting_score(paths)
        human_hint_alignment = build_human_hints_alignment(paths)

        info_payload = {
            "schema_version": SCHEMA_VERSION,
            **build_song_schema_fields(paths, bpm=timing["bpm"], duration=timing["duration"]),
            "song_path": str(paths.song_path),
            "artifacts": {
                "beats": str(paths.artifact("essentia", "beats.json")),
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
            },
            "outputs": {
                "beats": ui_outputs["beats"],
                "hints": hints["hints"],
                "sections": ui_outputs["sections"],
                "song_event_timeline": str(paths.timeline_output_path),
                "lighting_score": str(paths.lighting_score_output_path),
            },
            "debug": {
                "drum_events_engine": drum_events["generated_from"]["engine"],
            },
        }
        write_json(paths.info_output_path, info_payload)

        report, exit_code = build_validation_report(
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
        write_validation_report(report, config.report_json)
        write_validation_markdown(report, config.report_md)
        return exit_code
    finally:
        _print_phase_marker(paths.song_name, "phase-1", "end")
