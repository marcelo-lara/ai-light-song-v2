from __future__ import annotations

from analyzer.config import ValidationConfig
from analyzer.io import ensure_directory, write_json
from analyzer.exceptions import AnalysisError
from analyzer.models import SCHEMA_VERSION, build_song_schema_fields
from analyzer.paths import SongPaths
from analyzer.stages.energy import extract_energy_features
from analyzer.stages.energy import derive_energy_layer
from analyzer.stages.harmonic import extract_hpcp_and_chords
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
    validate_beats,
    write_validation_markdown,
    write_validation_report,
)


def run_phase_1(paths: SongPaths, config: ValidationConfig) -> int:
    ensure_directory(paths.song_artifacts_dir)
    stems = ensure_stems(paths)
    timing = extract_timing_grid(paths)
    beat_validation = (
        validate_beats(paths, timing, config.beat_tolerance_seconds)
        if "beats" in config.compare_targets
        else skipped_result()
    )
    if beat_validation.status == "failed" and beat_validation.reference_file is not None:
        inferred_beats_path = paths.artifact("essentia", "beats_inferred.json")
        write_json(inferred_beats_path, timing)
        timing = build_reference_timing_grid(
            paths,
            float(timing.get("duration", 0.0)),
            reference_chords_path=beat_validation.reference_file,
            inferred_beats_path=str(inferred_beats_path),
        )
        if not timing.get("beats"):
            raise AnalysisError("Reference timing takeover did not produce any canonical beats")
        write_json(paths.artifact("essentia", "beats.json"), timing)
    _, harmonic = extract_hpcp_and_chords(paths, stems, timing)
    energy_features = extract_energy_features(paths, timing)
    sections = segment_sections(paths, timing, harmonic, energy_features)
    symbolic = extract_symbolic_features(paths, stems, timing, sections)
    ui_outputs = build_ui_data(paths)
    energy = derive_energy_layer(paths, timing, energy_features, sections)
    patterns = extract_chord_patterns(paths, timing, harmonic)
    unified = assemble_music_feature_layers(paths, timing, harmonic, symbolic, energy, patterns, sections)
    lighting = generate_lighting_events(paths)
    lighting_score = generate_lighting_score(paths)

    info_payload = {
        "schema_version": SCHEMA_VERSION,
        **build_song_schema_fields(paths, bpm=timing["bpm"], duration=timing["duration"]),
        "song_path": str(paths.song_path),
        "artifacts": {
            "beats": str(paths.artifact("essentia", "beats.json")),
            "hpcp": str(paths.artifact("essentia", "hpcp.json")),
            "harmonic_layer": str(paths.artifact("layer_a_harmonic.json")),
            "symbolic_layer": str(paths.artifact("layer_b_symbolic.json")),
            "symbolic_validation": str(paths.artifact("symbolic_transcription", "validation.json")),
            "energy_features": str(paths.artifact("energy_summary", "features.json")),
            "energy_layer": str(paths.artifact("layer_c_energy.json")),
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
            "sections": ui_outputs["sections"],
            "lighting_score": str(paths.song_output_dir / "lighting_score.md"),
        },
    }
    write_json(paths.song_output_dir / "info.json", info_payload)

    report, exit_code = build_validation_report(
        paths=paths,
        compare_targets=config.compare_targets,
        beat_validation=beat_validation,
        beat_tolerance_seconds=config.beat_tolerance_seconds,
        tolerance_seconds=config.tolerance_seconds,
        chord_min_overlap=config.chord_min_overlap,
        fail_on_mismatch=config.fail_on_mismatch,
    )
    write_validation_report(report, config.report_json)
    if config.report_md is not None:
        write_validation_markdown(report, config.report_md)
    return exit_code
