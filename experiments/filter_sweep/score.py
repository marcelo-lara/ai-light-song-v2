"""Score report — there is NO labelled ground truth for filter sweeps.

`human_hints.json` carries no sweep-typed hint on any song (the word "filtered"
appears only on vocal hints), so no precision / recall / F1 exists and none is
invented. What is measured instead, over every song with the inputs:

  1. sweeps per song, by stem and direction (the lane itself);
  2. distinctness from the incumbent `riser` (gestures.py `detect_ramps`,
     recomputed on the mix FFT): how many sweeps overlap a riser/downlifter
     span by >= 50 % of the sweep's length;
  3. the two ablation baselines — depth only (no monotonicity, no level gate)
     and depth + monotonicity (no level gate) — so the cost of each gate in
     sweeps-per-song is visible. A gate that removes nothing is not earning
     its keep; a gate that removes most candidates is the thing to listen to.

Writes `out/score.txt`. Review verdict (the operator names a heard sweep in
the lane) is the only acceptance test and has not been run.
"""
from __future__ import annotations

import json

import numpy as np

from analyzer.stages.gestures import detect_ramps

from . import detect, features, paths


def _risers(song: str) -> list[dict]:
    frames = json.loads(paths.mix_fft_path(song).read_text())["frames"]
    t = np.array([f["time"] for f in frames])
    lv = np.array([f["levels"] for f in frames])
    beats = json.loads(paths.beats_path(song).read_text())["beats"]
    return detect_ramps(lv, t, beats, kind="riser") + detect_ramps(lv, t, beats, kind="downlifter")


def _overlap(a: dict, spans: list[dict]) -> bool:
    length = a["end"] - a["start"]
    return any(min(a["end"], s["end"]) - max(a["start"], s["start"]) >= 0.5 * length for s in spans)


def run() -> None:
    songs = paths.all_songs()
    lines = [f"{'song':44s} {'sweeps':>6s} {'harm':>5s} {'bass':>5s} {'open':>5s} {'close':>5s} "
             f"{'riser-ovl':>9s} {'depth-only':>10s} {'+mono':>6s}"]
    tot = {k: 0 for k in ("n", "ovl", "d", "dm", "harm", "bass", "open", "close", "risers")}
    for song in songs:
        cache = features.load_cache(song)
        rows = detect.detect_song(cache)
        d_only = detect.detect_song(cache, gate_mono=False, gate_level=False)
        d_mono = detect.detect_song(cache, gate_level=False)
        risers = _risers(song)
        ovl = sum(_overlap(r, risers) for r in rows)
        h = sum(r["stem"] == "harmonic" for r in rows)
        o = sum(r["direction"] == "opening" for r in rows)
        lines.append(f"{song[:44]:44s} {len(rows):6d} {h:5d} {len(rows)-h:5d} {o:5d} {len(rows)-o:5d} "
                     f"{ovl:9d} {len(d_only):10d} {len(d_mono):6d}")
        for k, v in (("n", len(rows)), ("ovl", ovl), ("d", len(d_only)), ("dm", len(d_mono)),
                     ("harm", h), ("bass", len(rows) - h), ("open", o), ("close", len(rows) - o),
                     ("risers", len(risers))):
            tot[k] += v
    lines.append("")
    lines.append(f"{len(songs)} songs: {tot['n']} sweeps ({tot['harm']} harmonic / {tot['bass']} bass, "
                 f"{tot['open']} opening / {tot['close']} closing); "
                 f"{tot['ovl']} overlap an incumbent riser/downlifter span ({tot['risers']} such spans exist); "
                 f"baselines: depth-only {tot['d']}, depth+monotonic {tot['dm']}")
    lines.append("No sweep ground truth exists: no precision/recall reported.")
    text = "\n".join(lines) + "\n"
    paths.OUT_ROOT.mkdir(parents=True, exist_ok=True)
    (paths.OUT_ROOT / "score.txt").write_text(text)
    print(text)
