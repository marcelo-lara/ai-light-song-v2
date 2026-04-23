from pathlib import Path
import json
from analyzer.paths import SongPaths
from analyzer.stages.event_identifiers import infer_song_identifiers

song_name = "Cinderella - Ella Lee"
root = Path("/app")
paths = SongPaths(
    song_path=root / "data/songs" / f"{song_name}.mp3",
    artifacts_root=root / "data/artifacts",
    reference_root=root / "data/reference",
    output_root=root / "data/output",
    stems_root=root / "data/stems",
)

with open(paths.artifact("layer_c_energy.json")) as f:
    energy = json.load(f)

with open(paths.artifact("section_segmentation", "sections.json")) as f:
    sections = json.load(f)

res = infer_song_identifiers(paths, energy, sections)
print(f"Detected {len(res[events])} drops:")
for ev in res["events"]:
    print(f" - {ev[time_s]} (confidence: {ev[confidence]}) - sect: {ev[section_id]}")
