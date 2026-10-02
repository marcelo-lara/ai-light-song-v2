"""Label accuracy and boundary moves on the operator-reviewed songs.

Truth: `reference/human/segments.json` (the 10 reviewed songs) — a scoring
reference, never an input to the proposal. Methods, same truth:

  section_names  this experiment, WITH the structure hint (what is exported)
  no-hint        the same run with the hint ignored
  allin1         incumbent: `artifacts/allin1/raw.json` segments, labels mapped to the
                 vocabulary by `analyzer.section_vocabulary.HARMONIX_TO_VOCABULARY`
                 (the production mapping)
  majority       cheap baseline: the one label with the most reviewed time, everywhere

Label accuracy = share of the truth's time (0.1 s grid, first start to last end)
where the predicted label equals the reviewed one. Three equivalence levels:
exact; `coarse` (Build = Build-Up, Break = Breakdown, Chorus (Inst) = Chorus,
Extended Drop = Drop); `peak` (Drop / Chorus / Post-Chorus / Extended Drop /
Chorus (Inst) / Drop Break vs. everything else — does it find the payoff at
all, whatever it is called). Songs where section_names keeps the current labels
(`kept_current`) are NOT scored (they would trivially equal the truth where the
current labels are the reviewed ones); they are listed. Boundary F1 is +-1.0 s,
`truth_common.structure`'s scorer. Every reviewed label / boundary the shipped
proposal would override is listed in `out/overrides.txt`.

Writes `out/score.txt` and `out/overrides.txt`.
"""
from __future__ import annotations

import json
from collections import Counter

from analyzer.section_vocabulary import HARMONIX_TO_VOCABULARY
from experiments.truth_common import structure

from . import export as export_mod, paths

TOL = 1.0
STEP = 0.1
COARSE = {"build": "build-up", "break": "breakdown", "chorus (inst)": "chorus", "extended drop": "drop"}
PEAK = {"drop", "chorus", "post-chorus", "extended drop", "chorus (inst)", "drop break"}
STAGE_SEQUENCE = ["Intro", "Pre-Build", "Build-Up", "Fill|Pre-Drop", "Drop|Chorus", "Breakdown",
                  "Build-Up", "Fill|Pre-Drop", "Drop|Chorus", "Outro"]
FOCUS = ("Rapture - Nadia Ali", "Armin - Revolution", "Medicine-MilkInc")


def norm(label: str | None) -> str:
    return (label or "").strip().lower()


def coarse(label: str | None) -> str:
    return COARSE.get(norm(label), norm(label))


def peak(label: str | None) -> str:
    return "peak" if norm(label) in PEAK else "other"


def truth_rows(song: str) -> list[dict] | None:
    p = paths.human_segments_path(song)
    if not p.exists():
        return None
    rows = json.loads(p.read_text())
    return rows if len(rows) >= 2 else None


def allin1_rows(song: str) -> list[dict]:
    segs = json.loads(paths.allin1_raw_path(song).read_text())["segments"]
    return [{"start": float(s["start"]), "end": float(s["end"]), "label": HARMONIX_TO_VOCABULARY[s["label"]]}
            for s in segs if s["label"] in HARMONIX_TO_VOCABULARY]


def named_rows(song: str, use_hint: bool) -> tuple[str, list[dict]]:
    res = export_mod.build(song, use_hint=use_hint)
    return res["status"], [{"start": b["start_s"], "end": b["end_s"], "label": b["label"],
                            "confidence": b.get("confidence")} for b in res["blocks"]]


def label_at(rows: list[dict], t: float) -> str | None:
    for r in rows:
        if r["start"] <= t < r["end"]:
            return r["label"]
    return None


def accuracy(truth: list[dict], pred: list[dict], fn) -> tuple[int, int]:
    t, hit, tot = float(truth[0]["start"]), 0, 0
    end = float(truth[-1]["end"])
    while t < end:
        tl = label_at(truth, t)
        if tl is not None:
            tot += 1
            hit += fn(label_at(pred, t)) == fn(tl)
        t += STEP
    return hit, tot


def majority_label(songs: list[str]) -> str:
    c: Counter = Counter()
    for s in songs:
        for r in truth_rows(s):
            c[r["label"]] += float(r["end"]) - float(r["start"])
    return c.most_common(1)[0][0]


def boundary_score(song: str, pred: list[dict], truth: list[dict], vocab) -> structure.StructureScore:
    tb = [structure.TruthBoundary(float(r["start"]), str(r["label"])) for r in truth[1:]]
    pb = [{"time": r["start"], "label": r["label"]} for r in pred[1:] if r["start"] > 0.0]
    return structure.score_structure(song, pb, truth=tb, tolerance=TOL, vocabulary=vocab)


def _micro(rows: list[structure.StructureScore]) -> dict:
    m, p, t = (sum(r.matched for r in rows), sum(r.n_predicted for r in rows), sum(r.n_truth for r in rows))
    prec, rec = (m / p if p else None), (m / t if t else None)
    f1 = 2 * prec * rec / (prec + rec) if prec and rec else 0.0
    return {"P": prec, "R": rec, "F1": f1, "pred": p, "truth": t, "matched": m}


def _f(x) -> str:
    return " -  " if x is None else f"{x:.3f}"


def sequence_check(labels: list[str]) -> tuple[int, list[str]]:
    """Greedy ordered match of STAGE_SEQUENCE against the label sequence; returns
    (stages matched, stages missing)."""
    pos, matched, missing = 0, 0, []
    for stage in STAGE_SEQUENCE:
        alts = stage.split("|")
        j = next((k for k in range(pos, len(labels)) if labels[k] in alts), None)
        if j is None:
            missing.append(stage)
        else:
            matched += 1
            pos = j + 1
    return matched, missing


def overrides(song: str, truth: list[dict], pred: list[dict]) -> dict:
    """Reviewed labels and boundaries the proposal would replace."""
    lab, bnd_moved, bnd_dropped, added = [], [], [], []
    for r in truth:
        a, b = float(r["start"]), float(r["end"])
        ov: Counter = Counter()
        for p in pred:
            x = min(b, p["end"]) - max(a, p["start"])
            if x > 0:
                ov[p["label"]] += x
        top, share = (ov.most_common(1)[0] if ov else (None, 0.0))
        if norm(top) != norm(r["label"]):
            lab.append((a, b, r["label"], top, share / (b - a) if b > a else 0.0))
    pb = [p["start"] for p in pred[1:]]
    tb = [float(r["start"]) for r in truth[1:]]
    for t in tb:
        d = min((p - t for p in pb), key=abs, default=None)
        if d is None or abs(d) > 4.0:
            bnd_dropped.append((t, d))
        elif abs(d) > TOL:
            bnd_moved.append((t, d))
    for p in pb:
        if not tb or min(abs(p - t) for t in tb) > TOL:
            added.append(p)
    return {"labels": lab, "moved": bnd_moved, "dropped": bnd_dropped, "added": added,
            "n_truth": len(truth), "n_boundaries": len(tb)}


def run() -> None:
    songs = [s for s in paths.all_songs() if truth_rows(s) and paths.cache_path(s).exists()]
    vocab = structure.load_label_vocabulary()
    maj = majority_label(songs)
    methods = ("section_names", "no-hint", "allin1", "majority")
    acc = {m: {k: [0, 0] for k in ("exact", "coarse", "peak")} for m in methods}
    bscore: dict[str, list[structure.StructureScore]] = {m: [] for m in methods[:3]}
    lines = ["Section Names — label accuracy and boundary moves on the reviewed songs", "=" * 100, "",
             f"truth = reference/human/segments.json ({len(songs)} songs); majority baseline label = {maj!r}", ""]
    kept, named_songs = [], []
    per_song_lines, ov_lines = [], ["Reviewed labels and boundaries the proposal would override", "=" * 100, ""]
    ov_tot = Counter()
    seq_lines = []
    for song in sorted(set(songs) | set(FOCUS)):
        status, pred = named_rows(song, True)
        seq = [r["label"] for r in pred]
        m, miss = sequence_check(seq)
        tag = "reviewed" if song in songs else "not reviewed"
        seq_lines.append(f"  {song:34s} {status:13s} {tag:12s} stages {m}/{len(STAGE_SEQUENCE)}"
                         + (f"  missing: {', '.join(miss)}" if miss else "  (full)")
                         + f"\n      {' > '.join(seq)}")
    for song in songs:
        truth = truth_rows(song)
        status, pred = named_rows(song, True)
        status_nh, pred_nh = named_rows(song, False)
        if status != "named":
            kept.append((song, status_nh))
            continue
        named_songs.append(song)
        a1 = allin1_rows(song)
        rows = {"section_names": pred, "no-hint": pred_nh, "allin1": a1,
                "majority": [{"start": float(truth[0]["start"]), "end": float(truth[-1]["end"]), "label": maj}]}
        cells = []
        for mth in methods:
            for k, fn in (("exact", norm), ("coarse", coarse), ("peak", peak)):
                h, t = accuracy(truth, rows[mth], fn)
                acc[mth][k][0] += h
                acc[mth][k][1] += t
            h, t = accuracy(truth, rows[mth], norm)
            if mth in bscore:
                s = boundary_score(song, rows[mth], truth, vocab)
                bscore[mth].append(s)
                cells.append(f"{h / t:.3f}/F1 {s.f1:.3f}")
            else:
                cells.append(f"{h / t:.3f}")
        per_song_lines.append(f"  {song[:34]:34s} " + "  ".join(f"{c:>16s}" for c in cells))
        ov = overrides(song, truth, pred)
        for k in ("labels", "moved", "dropped", "added"):
            ov_tot[k] += len(ov[k])
        ov_tot["truth_sections"] += ov["n_truth"]
        ov_tot["truth_boundaries"] += ov["n_boundaries"]
        ov_lines.append(f"## {song}  ({ov['n_truth']} reviewed sections, {ov['n_boundaries']} boundaries)")
        for a, b, tl, pl, sh in ov["labels"]:
            ov_lines.append(f"  label    {a:7.1f}-{b:7.1f}  reviewed {tl!r:16s} -> {pl!r} ({sh:.0%} of the section)")
        for t, d in ov["moved"]:
            ov_lines.append(f"  moved    reviewed boundary {t:7.1f} -> nearest proposal boundary {d:+.1f} s away")
        for t, d in ov["dropped"]:
            ov_lines.append(f"  dropped  reviewed boundary {t:7.1f} -> no proposal boundary within 4 s"
                            + ("" if d is None else f" (nearest {d:+.1f} s)"))
        for p in ov["added"]:
            ov_lines.append(f"  added    proposal boundary {p:7.1f} has no reviewed boundary within {TOL:.1f} s")
        ov_lines.append("")
    lines += ["## Per song (exact label accuracy / boundary F1 @ +-1.0 s)", "",
              f"  {'song':34s} " + "  ".join(f"{m:>16s}" for m in methods)]
    lines += per_song_lines
    lines += ["", f"## Pooled over the {len(named_songs)} songs where section_names names the sections", ""]
    for k in ("exact", "coarse", "peak"):
        lines.append(f"  label accuracy ({k}): " + "   ".join(
            f"{m} {acc[m][k][0] / acc[m][k][1]:.3f}" for m in methods))
    for m in methods[:3]:
        u = _micro(bscore[m])
        lines.append(f"  boundaries {m:14s} P={_f(u['P'])} R={_f(u['R'])} F1={u['F1']:.3f}  "
                     f"pred={u['pred']} truth={u['truth']} matched={u['matched']}")
    lines += ["", "## Songs kept on their current labels (not scored)", ""]
    for song, _ in kept:
        lines.append(f"  {song}")
    lines += ["", f"## Stage sequence ({' > '.join(STAGE_SEQUENCE)})", ""] + seq_lines
    lines += ["", "## Reviewed labels / boundaries the proposal would override (detail: out/overrides.txt)", "",
              f"  songs compared: {len(named_songs)}; reviewed sections {ov_tot['truth_sections']}, "
              f"reviewed boundaries {ov_tot['truth_boundaries']}",
              f"  labels overridden: {ov_tot['labels']}   boundaries moved >{TOL:.0f} s (<=4 s): {ov_tot['moved']}   "
              f"reviewed boundaries dropped (no proposal boundary within 4 s): {ov_tot['dropped']}   "
              f"proposal boundaries with no reviewed counterpart: {ov_tot['added']}"]
    text = "\n".join(lines) + "\n"
    paths.OUT_ROOT.mkdir(parents=True, exist_ok=True)
    (paths.OUT_ROOT / "score.txt").write_text(text)
    (paths.OUT_ROOT / "overrides.txt").write_text("\n".join(ov_lines) + "\n")
    print(text)
