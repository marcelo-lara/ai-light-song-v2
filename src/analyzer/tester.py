from analyzer.paths import SongPaths
from analyzer.io import read_json
from analyzer.stages.event_rules import generate_rule_candidates
from analyzer.stages.event_machine import generate_machine_events
from analyzer.stages.event_benchmark import benchmark_event_outputs
from pathlib import Path

def test_song(song_name: str):
    song_path = Path("/data/songs") / f"{song_name}.mp3"
    paths = SongPaths(song_path, Path("/data/artifacts"), Path("/data/reference"), Path("/data/output"), Path("/data/stems"))
    
    event_features = read_json(paths.artifact("event_inference", "features.json"))
    sections_payload = read_json(paths.artifact("section_segmentation", "sections.json"))
    genre_result = read_json(paths.artifact("genre.json"))
    human_hints_path = paths.reference("human", "human_hints.json")
    
    if not event_features.get("features"):
        print(f"[{song_name}] Missing event_features")
        return
        
    rules_payload = generate_rule_candidates(paths, event_features, sections_payload, genre_result)
    
    # We need symbolic and identifier payloads for generate_machine_events
    try:
        symbolic_payload = read_json(paths.artifact("layer_b_symbolic.json"))
        identifier_payload = read_json(paths.artifact("event_inference", "identifiers.json"))
    except Exception:
        symbolic_payload = {"events": []}
        identifier_payload = {"identifiers": []}

    machine_payload = generate_machine_events(paths, event_features, rules_payload, identifier_payload, symbolic_payload, sections_payload)
    
    # Run benchmark
    benchmark_payload = benchmark_event_outputs(paths, machine_payload, genre_result)
    
    if benchmark_payload and benchmark_payload.get("status") != "skipped":
        matched = benchmark_payload.get("matched", 0)
        missed = benchmark_payload.get("missed", 0)
        fp = benchmark_payload.get("false_positives", 0)
        print(f"[{song_name}] Benchmark Results - Matched: {matched}, Missed: {missed}, False Positives: {fp}")
    else:
        print(f"[{song_name}] Benchmark skipped: {benchmark_payload.get('reason', 'Missing score/skipped')}")
        
    print(f"[{song_name}] Generated {len(rules_payload.get('events', []))} rule candidates")
    print(f"[{song_name}] Generated {len(machine_payload.get('events', []))} machine events")

if __name__ == '__main__':
    test_song("What a Feeling - Courtney Storm")
    test_song("ayuni")
