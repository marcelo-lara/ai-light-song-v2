import numpy as np
from experiments.drop_detection import features, groundtruth
from experiments.drop_detection.candidates import _smooth, _win
from experiments.drop_detection.paths import GOLD_SONGS

for song in GOLD_SONGS:
    gt = groundtruth.impacts(song)
    feat = features.load(song)
    t = feat.t
    flux_norm = float(np.percentile(feat.flux, 99))
    sm = [_smooth(r, 0.35) for r in feat.stem_db] + [_smooth(feat.mix_db, 0.35)]
    names = ["bass", "drums", "harm", "voc", "mix"]
    for g in gt:
        print(f"\n--- {song}  gt impact {g:.2f}")
        print(f"{'beat':>8} {'err':>7} {'flux':>6} {'fluxRAW':>8} | " + " ".join(f"{n:>7}" for n in names))
        for b in feat.beats[(feat.beats >= g - 2.6) & (feat.beats <= g + 2.6)]:
            tr = _win(t, feat.flux, b, -0.08, 0.30, np.max)
            deltas = [_win(t, x, b, 0.10, 2.00) - _win(t, x, b, -2.00, -0.10) for x in sm]
            mark = " <<<" if abs(b - g) < 0.30 else ""
            print(f"{b:8.2f} {b-g:+7.2f} {tr/flux_norm:6.2f} {tr:8.2f} | "
                  + " ".join(f"{d:+7.1f}" for d in deltas) + mark)
