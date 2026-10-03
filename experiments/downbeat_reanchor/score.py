"""Downbeat F1 @ +-70 ms against Moises downbeats (same method as experiments/downbeat_anchors/score.py,
`analyzer.stages.validation.beats._score_downbeats`), plus the irregular-bar count corpus-wide.

Methods:
  incumbent        allin1 phase (`beats.json`), confidence-bearing downbeats only
  reanchor         this experiment, confidence-bearing downbeats only (an abstention is not a claim)
  reanchor-all     this experiment, every downbeat including `confidence: null` ones
  kick-only / events-only   ablations of the anchor kinds (confidence-bearing)

Writes `out/score.txt`.
"""
from __future__ import annotations

import json

from analyzer.stages.validation.beats import DOWNBEAT_F1_TOLERANCE_SECONDS, _score_downbeats

from . import build, paths

METHODS = ("incumbent", "reanchor", "reanchor-all", "kick-only", "events-only")
INCUMBENT_F1 = 0.343
ANCHORS_F1 = 0.301


def reference(song: str) -> tuple[list[float], float, float]:
    rows = json.loads(paths.moises_beats_path(song).read_text())
    ref = [float(r["time"]) for r in rows if int(r.get("beatNum", 0)) == 1]
    chords = json.loads(paths.moises_chords_path(song).read_text())
    ts = sorted(float(r["curr_beat_time"]) for r in chords if "curr_beat_time" in r)
    return ref, ts[0], ts[-1]


def _times(res: dict, only_conf: bool) -> list[float]:
    return [t for t, l in zip(res["times"], res["beats"])
            if l["downbeat"] and (l["confidence"] is not None or not only_conf)]


def predictions(song: str) -> dict[str, list[float]]:
    full = build.build(song)
    return {
        "incumbent": build.allin1_downbeats(song),
        "reanchor": _times(full, True),
        "reanchor-all": _times(full, False),
        "kick-only": _times(build.build(song, ("kick",)), True),
        "events-only": _times(build.build(song, ("impact", "entry")), True),
    }


def _f1(tp: int, pred: int, ref: int) -> float | None:
    if not pred or not ref:
        return None
    p, r = tp / pred, tp / ref
    return 2 * p * r / (p + r) if tp else 0.0


def score_song(song: str) -> dict[str, dict]:
    ref, lo, hi = reference(song)
    out = {}
    for m, preds in predictions(song).items():
        inrange = [t for t in preds if lo <= t <= hi]
        r = _score_downbeats(inrange, ref, DOWNBEAT_F1_TOLERANCE_SECONDS) if ref and inrange else None
        tp = r["downbeat_true_positives"] if r else 0
        out[m] = {"tp": tp, "pred": len(inrange), "ref": len(ref), "f1": _f1(tp, len(inrange), len(ref))}
    return out


def fmt(x) -> str:
    return "  n/a" if x is None else f"{x:.3f}"


def run() -> None:
    songs = paths.scored_songs()
    per = {s: score_song(s) for s in songs}
    w = max(len(s) for s in songs)
    lines = [f"Downbeat F1 @ +-{int(DOWNBEAT_F1_TOLERANCE_SECONDS * 1000)} ms vs Moises downbeats; "
             f"{len(songs)} songs; pooled = micro", "",
             f"{'song'.ljust(w)}  " + "  ".join(f"{m:>13}" for m in METHODS)]
    for s in songs:
        lines.append(f"{s.ljust(w)}  " + "  ".join(f"{fmt(per[s][m]['f1']):>13}" for m in METHODS))
    pooled = {}
    for m in METHODS:
        tp = sum(per[s][m]["tp"] for s in songs)
        pr = sum(per[s][m]["pred"] for s in songs)
        rf = sum(per[s][m]["ref"] for s in songs)
        pooled[m] = (tp, pr, rf, _f1(tp, pr, rf))
    lines.append(f"{'POOLED (5 songs)'.ljust(w)}  " + "  ".join(f"{fmt(pooled[m][3]):>13}" for m in METHODS))
    lines += ["", "pooled tp / predicted / reference:"]
    lines += [f"  {m:<14} {pooled[m][0]:>4} / {pooled[m][1]:>4} / {pooled[m][2]:>4}" for m in METHODS]
    lines += ["", f"gate: reanchor pooled F1 {fmt(pooled['reanchor'][3])} vs allin1 {INCUMBENT_F1} "
                  f"(downbeat_anchors {ANCHORS_F1})", "",
              "irregular bars (bar != 4 beats), corpus-wide. strict = every bar; outside = skips bars holding an "
              "off_grid beat and the two song-edge partials",
              f"{'song'.ljust(w)}  bars  strict  outside  old_outside  runs(phase source)  unresolved_spans  downbeats(conf/all)"]
    tot = {"strict": 0, "outside": 0, "old": 0}
    for s in paths.all_songs():
        r = build.build(s)
        ir, old = r["irregular"], r["old_irregular"]
        tot["strict"] += ir["strict"]
        tot["outside"] += ir["outside"]
        tot["old"] += old["outside"]
        src = {}
        for x in r["runs"]:
            src[x["source"]] = src.get(x["source"], 0) + 1
        nd = sum(l["downbeat"] for l in r["beats"])
        nc = sum(l["downbeat"] and l["confidence"] is not None for l in r["beats"])
        lines.append(f"{s.ljust(w)}  {ir['n_bars']:>4}  {ir['strict']:>6}  {ir['outside']:>7}  {old['outside']:>11}  "
                     f"{str(src):<18}  {len(r['spans']):>16}  {nc}/{nd}")
    lines.append(f"{'TOTAL'.ljust(w)}        {tot['strict']:>6}  {tot['outside']:>7}  {tot['old']:>11}")
    paths.OUT_ROOT.mkdir(parents=True, exist_ok=True)
    text = "\n".join(lines) + "\n"
    (paths.OUT_ROOT / "score.txt").write_text(text)
    print(text)
