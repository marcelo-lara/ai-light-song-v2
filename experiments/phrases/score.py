"""Boundary precision / recall / F1 @ +-1.0 s, phrases vs the incumbent and the baseline.

Truth, two sets (both operator-reviewed; neither is ever the published
`sections.json`, which on reviewed songs is rebuilt from them):

  segments  `reference/human/segments.json` starts[1:] — coarse (section) boundaries.
            Only songs whose file is non-empty.
  hints     `reference/human/human_hints.json` rows of `type: "review"` — the
            operator's finer, stem-level review. Boundaries = hint starts > 0.5 s
            plus hint ends before the last 0.5 s, de-duplicated within 0.3 s.
            Only songs with at least one review hint.

Methods, same truth, same tolerance:
  phrases            this experiment (edges, recomputed from the cache)
  phrases-resolved   the same edges with no conflict flag
  allin1             incumbent — `artifacts/allin1/raw.json` segment starts
  stem-presence      baseline — `reference/proposals/stem_presence_sections.json`

Groups: `edm` = `reference/pre-analysis/structure.json` genre.family == "edm"
(the structure hints, item 13), reported apart from every other song. Pooled
figures are micro-averages over boundaries. Precision against *segments* is
capped by construction: phrases are finer than sections.

Writes `out/score.txt`.
"""
from __future__ import annotations

import json

from experiments.truth_common import structure

from . import build, export as export_mod, features, paths

TOL = 1.0
METHODS = ("phrases", "phrases-resolved", "allin1", "stem-presence")
FOCUS = ("Rapture - Nadia Ali", "Charli-VonDutch")


def family(song: str) -> str:
    p = paths.structure_hint_path(song)
    if not p.exists():
        return "unknown"
    return json.loads(p.read_text()).get("genre", {}).get("family") or "unknown"


def truth_segments(song: str) -> list[structure.TruthBoundary] | None:
    p = paths.human_segments_path(song)
    if not p.exists():
        return None
    rows = json.loads(p.read_text())
    if len(rows) < 2:
        return None
    return [structure.TruthBoundary(float(r["start"]), str(r.get("label", ""))) for r in rows[1:]]


def truth_hints(song: str, duration: float) -> list[structure.TruthBoundary] | None:
    p = paths.human_hints_path(song)
    if not p.exists():
        return None
    rows = [h for h in json.loads(p.read_text())["human_hints"] if h.get("type") == "review"]
    if not rows:
        return None
    ts = sorted([float(h["start_time"]) for h in rows if float(h["start_time"]) > 0.5]
                + [float(h["end_time"]) for h in rows if float(h["end_time"]) < duration - 0.5])
    out: list[float] = []
    for t in ts:
        if not out or t - out[-1] > 0.3:
            out.append(t)
    return [structure.TruthBoundary(t, "") for t in out]


def predictions(song: str) -> dict[str, list[dict]]:
    cache = features.load_cache(song)
    phrases = export_mod.build_blocks(song, cache)
    edges = [(p["start_s"], p["start_edge"]) for p in phrases[1:]]
    out = {
        "phrases": [{"time": t, "label": None} for t, _ in edges],
        "phrases-resolved": [{"time": t, "label": None} for t, e in edges if not e["conflicts"]],
        "allin1": [{"time": float(s["start"]), "label": None}
                   for s in json.loads(paths.allin1_raw_path(song).read_text())["segments"][1:]],
    }
    sp = paths.stem_presence_path(song)
    out["stem-presence"] = ([{"time": float(b["start_s"]), "label": None}
                             for b in json.loads(sp.read_text())["blocks"][1:]] if sp.exists() else None)
    return out


def _micro(rows: list[structure.StructureScore]) -> dict:
    m = sum(r.matched for r in rows)
    p = sum(r.n_predicted for r in rows)
    t = sum(r.n_truth for r in rows)
    prec = m / p if p else None
    rec = m / t if t else None
    f1 = 2 * prec * rec / (prec + rec) if prec and rec else 0.0
    return {"P": prec, "R": rec, "F1": f1, "pred": p, "truth": t, "matched": m, "n_songs": len(rows)}


def _fmt(x) -> str:
    return "  -  " if x is None else f"{x:.3f}"


def run() -> None:
    songs = paths.all_songs()
    vocab = structure.load_label_vocabulary()
    results: dict[str, dict[str, dict[str, structure.StructureScore]]] = {"segments": {}, "hints": {}}
    notes: list[str] = []
    for song in songs:
        if not paths.cache_path(song).exists():
            notes.append(f"{song}: no cache (run compute) — not scored")
            continue
        duration = float(json.loads(paths.info_path(song).read_text())["duration"])
        truths = {"segments": truth_segments(song), "hints": truth_hints(song, duration)}
        if all(v is None for v in truths.values()):
            continue
        preds = predictions(song)
        for tname, truth in truths.items():
            if truth is None:
                continue
            for m in METHODS:
                if preds[m] is None:
                    notes.append(f"{song}: {m} unavailable (no proposal file) — omitted from {tname}")
                    continue
                results[tname].setdefault(song, {})[m] = structure.score_structure(
                    song, preds[m], truth=truth, tolerance=TOL, vocabulary=vocab)

    lines = ["Phrases — boundary P / R / F1 @ +-1.0 s", "=" * 100]
    for tname, desc in (("segments", "reviewed segments (coarse)"), ("hints", "reviewed hints (fine)")):
        per_song = results[tname]
        lines += ["", f"## truth: {desc} — {len(per_song)} songs", ""]
        lines.append(f"{'song':40s} {'fam':8s} {'truth':>5s}  " + "  ".join(f"{m:>22s}" for m in METHODS))
        for song in sorted(per_song):
            r = per_song[song]
            nt = next(iter(r.values())).n_truth
            cells = []
            for m in METHODS:
                s = r.get(m)
                cells.append(f"{'n/a':>22s}" if s is None else
                             f"{_fmt(s.precision)}/{_fmt(s.recall)}/{s.f1:.3f} n={s.n_predicted:<3d}")
            lines.append(f"{song[:40]:40s} {family(song):8s} {nt:5d}  " + "  ".join(cells))
        for gname, pick in (("edm", lambda f: f == "edm"), ("non-edm", lambda f: f != "edm"),
                            ("all", lambda f: True)):
            sel = [s for s in per_song if pick(family(s))]
            lines += ["", f"  pooled, {gname} ({len(sel)} songs)"]
            for m in METHODS:
                rows = [per_song[s][m] for s in sel if m in per_song[s]]
                if rows:
                    u = _micro(rows)
                    lines.append(f"    {m:18s} P={_fmt(u['P'])} R={_fmt(u['R'])} F1={u['F1']:.3f}  "
                                 f"pred={u['pred']} truth={u['truth']} matched={u['matched']}")
    lines += ["", "## Rapture and Charli-VonDutch vs stem-presence (F1; 'match or beat' check)", ""]
    for song in FOCUS:
        for tname in ("segments", "hints"):
            r = results[tname].get(song)
            if not r or "stem-presence" not in r:
                lines.append(f"  {song:24s} {tname:9s} no truth / no stem-presence")
                continue
            a, b = r["phrases"], r["stem-presence"]
            verdict = "MATCH-OR-BEAT" if a.f1 >= b.f1 - 1e-9 else "BELOW"
            lines.append(f"  {song:24s} {tname:9s} phrases F1={a.f1:.3f} (P={_fmt(a.precision)} R={_fmt(a.recall)}) "
                         f"vs stem-presence F1={b.f1:.3f} (P={_fmt(b.precision)} R={_fmt(b.recall)})  {verdict}")
    lines += ["", "## Output sanity (all songs with a cache)", ""]
    tot = res = 0
    for song in songs:
        if not paths.cache_path(song).exists():
            continue
        ph = export_mod.build_blocks(song)
        tot += len(ph)
        res += sum(not p["resolved"] for p in ph)
        lines.append(f"  {song[:44]:44s} {family(song):8s} phrases={len(ph):3d} unresolved={sum(not p['resolved'] for p in ph):3d}")
    lines.append(f"  total phrases {tot}, unresolved {res}")
    lines += [""] + notes
    text = "\n".join(lines) + "\n"
    paths.OUT_ROOT.mkdir(parents=True, exist_ok=True)
    (paths.OUT_ROOT / "score.txt").write_text(text)
    print(text)
