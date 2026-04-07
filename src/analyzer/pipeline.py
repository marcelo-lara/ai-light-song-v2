from __future__ import annotations

from analyzer.config import ValidationConfig
from analyzer.io import ensure_directory, write_json
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
from analyzer.stages.timing import extract_timing_grid
from analyzer.stages.unified import assemble_music_feature_layers
from analyzer.stages.validation import (
    build_validation_report,
    write_validation_markdown,
    write_validation_report,
)


def run_phase_1(paths: SongPaths, config: ValidationConfig) -> int:
    ensure_directory(paths.song_artifacts_dir)
    stems = ensure_stems(paths)
    timing = extract_timing_grid(paths)
    _, harmonic = extract_hpcp_and_chords(paths, stems, timing)
    energy_features = extract_energy_features(paths, timing)
    sections = segment_sections(paths, timing, harmonic, energy_features)
    symbolic = extract_symbolic_features(paths, stems, timing, sections)
    energy = derive_energy_layer(paths, timing, energy_features, sections)
    patterns = extract_chord_patterns(paths, timing, harmonic)
    unified = assemble_music_feature_layers(paths, timing, harmonic, symbolic, energy, patterns, sections)
    lighting = generate_lighting_events(paths)
    lighting_score = generate_lighting_score(paths)

    info_payload = {
        "schema_version": "1.0",
        "song_id": paths.song_id,
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
            "lighting_score": str(paths.song_output_dir / "lighting_score.md"),
        },
    }
    write_json(paths.artifact("info.json"), info_payload)

    report, exit_code = build_validation_report(
        paths=paths,
        compare_targets=config.compare_targets,
        tolerance_seconds=config.tolerance_seconds,
        chord_min_overlap=config.chord_min_overlap,
        fail_on_mismatch=config.fail_on_mismatch,
    )
    write_validation_report(report, config.report_json)
    if config.report_md is not None:
        write_validation_markdown(report, config.report_md)
    return exit_code
