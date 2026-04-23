import json
from pathlib import Path
from analyzer.paths import SongPaths

song_name = 'Cinderella - Ella Lee'
root = Path('.')
paths = SongPaths(
    song_path=root / f'data/songs/{song_name}.mp3',
    artifacts_root=root / 'data/artifacts',
    reference_root=root / 'data/reference',
    output_root=root / 'data/output',
    stems_root=root / 'data/stems',
)
with open(paths.artifact('layer_c_energy.json')) as f: energy = json.load(f)

for b in energy['beat_energy']:
    t = float(b['time'])
    if abs(t - 283.82) < 1.0:
        l = b.get('loudness_avg', 0)
        o = b.get('onset_density', 0)
        c = b.get('centroid_avg', 0)
        e = b.get('energy_score', 0)
        print(f'{t:.2f} | Ld: {l:.3f} | Od: {o:.3f} | Cd: {c:.0f} | En: {e:.3f}')
