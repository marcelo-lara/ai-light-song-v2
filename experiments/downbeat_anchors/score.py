"""Downbeat F1 @ +-70 ms against Moises downbeats — the analysis-definition "Downbeats" method.

Reproduced from `analyzer.stages.validation.beats.validate_beats` (imported as
a function; same greedy one-to-one nearest matching, same tolerance
`DOWNBEAT_F1_TOLERANCE_SECONDS`):

* reference = `reference/moises/beats.json` rows with `beatNum == 1`;
* the range is [first, last] `curr_beat_time` of `reference/moises/chords.json`;
  predictions outside it are dropped (reference downbeats are all inside);
* the incumbent's predictions are `beats.json` downbeats with a non-null
  confidence (an abstention is not a claim; it still costs recall).

Pooled = micro-average (sum of TP / predicted / reference over songs). Songs:
every song with `reference/moises/` (5; 4 gold songs + Queen of Kings).

Methods:
  incumbent        allin1 phase (`beats.json`), the 0.226 number
  modulo           baseline: every 4th beat from the first beat
  kick-phase       baseline: the one phase of four with most drums-stem sub+bass energy
  anchors-only     this experiment, no allin1 fill (abstains wherever no anchor reaches)
  anchors+allin1   this experiment as specified (allin1 where no anchor reaches)
  anchors+allin1 @2.5   sensitivity ONLY (see README): anchor score >= 2.5

Writes `out/score.txt`.
"""
from __future__ import annotations

import json

from analyzer.stages.validation.beats import DOWNBEAT_F1_TOLERANCE_SECONDS, _score_downbeats

from . import build, paths

METHODS = ("incumbent", "modulo", "kick-phase", "anchors-only", "anchors+allin1", "anchors+allin1 @2.5")


def reference(song: str) -> tuple[list[float], float, float]:
    rows = json.loads(paths.moises_beats_path(song).read_text())
    ref = [float(r["time"]) for r in rows if int(r.get("beatNum", 0)) == 1]
    chords = json.loads(paths.moises_chords_path(song).read_text())
    ts = sorted(float(r["curr_beat_time"]) for r in chords if "curr_beat_time" in r)
    return ref, ts[0], ts[-1]


def predictions(song: str) -> dict[str, list[float]]:
    return {
        "incumbent": build.allin1_downbeats(song),
        "modulo": build.modulo_downbeats(song),
        "kick-phase": build.kick_phase_downbeats(song),
        "anchors-only": [d["time"] for d in build.build(song, use_fallback=False)["downbeats"]],
        "anchors+allin1": [d["time"] for d in build.build(song)["downbeats"]],
        "anchors+allin1 @2.5": [d["time"] for d in build.build(song, min_score=2.5)["downbeats"]],
    }


def score_song(song: str) -> dict[str, dict]:
    ref, lo, hi = reference(song)
    out = {}
    for m, preds in predictions(song).items():
        inrange = [t for t in preds if lo <= t <= hi]
        r = _score_downbeats(inrange, ref, DOWNBEAT_F1_TOLERANCE_SECONDS) if ref and inrange else None
        out[m] = {"tp": r["downbeat_true_positives"] if r else 0, "pred": len(inrange), "ref": len(ref),
                  "f1": _f1(r["downbeat_true_positives"], len(inrange), len(ref)) if r else None}
    return out


def _f1(tp: int, pred: int, ref: int) -> float | None:
    if not pred or not ref:
        return None
    p, r = tp / pred, tp / ref
    return 2 * p * r / (p + r) if tp else 0.0


def fmt(x) -> str:
    return "  n/a" if x is None else f"{x:.3f}"


def run() -> None:
    songs = paths.scored_songs()
    per = {s: score_song(s) for s in songs}
    lines = [f"Downbeat F1 @ +-{int(DOWNBEAT_F1_TOLERANCE_SECONDS * 1000)} ms vs Moises downbeats; "
             f"{len(songs)} songs; pooled = micro", ""]
    w = max(len(s) for s in songs)
    lines.append(f"{'song'.ljust(w)}  " + "  ".join(f"{m:>20}" for m in METHODS))
    for s in songs:
        lines.append(f"{s.ljust(w)}  " + "  ".join(f"{fmt(per[s][m]['f1']):>20}" for m in METHODS))
    def pool(subset):
        out = {}
        for m in METHODS:
            tp = sum(per[s][m]["tp"] for s in subset)
            pr = sum(per[s][m]["pred"] for s in subset)
            rf = sum(per[s][m]["ref"] for s in subset)
            out[m] = (tp, pr, rf, _f1(tp, pr, rf))
        return out
    pooled = pool(songs)
    # the 385-downbeat benchmark behind the documented 0.226 (Queen of Kings was added after)
    four = pool([s for s in songs if not s.startswith("Queen of Kings")])
    lines.append(f"{'POOLED (5 songs)'.ljust(w)}  " + "  ".join(f"{fmt(pooled[m][3]):>20}" for m in METHODS))
    lines.append(f"{'POOLED (4, no Queen)'.ljust(w)}  " + "  ".join(f"{fmt(four[m][3]):>20}" for m in METHODS))
    macro = {m: sum((per[s][m]["f1"] or 0.0) for s in songs) / len(songs) for m in METHODS}
    lines.append(f"{'MACRO'.ljust(w)}  " + "  ".join(f"{fmt(macro[m]):>20}" for m in METHODS))
    lines += ["", "pooled (5 songs) tp / predicted / reference:"]
    lines += [f"  {m:<20} {pooled[m][0]:>4} / {pooled[m][1]:>4} / {pooled[m][2]:>4}" for m in METHODS]

    lines += ["", "anchor diagnostics (default threshold):"]
    for s in songs:
        r = build.build(s)
        sp = r["spans"]
        un = [x for x in sp if not x["resolved"]]
        src = {}
        for d in r["downbeats"]:
            src[d["source"]] = src.get(d["source"], 0) + 1
        lines.append(f"  {s.ljust(w)} anchors {len(r['anchors'])}/{r['n_phrase_edges']} edges, spans {len(sp)} "
                     f"(unresolved {len(un)}: {sum(x['reason']=='phase_disagree' for x in un)} phase, "
                     f"{sum(x['reason']=='off_grid' for x in un)} off-grid), downbeats by source {src}")
    paths.OUT_ROOT.mkdir(parents=True, exist_ok=True)
    text = "\n".join(lines) + "\n"
    (paths.OUT_ROOT / "score.txt").write_text(text)
    print(text)
