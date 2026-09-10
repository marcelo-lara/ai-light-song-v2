"""Agreement with the operator's own hints, split by `kind`, on the four gold
songs — phrase-grid fit vs the duration-only cheap baseline.

Also reproduces the `Queen of Kings` 6-of-16 edge-lock table (refinement doc
item 4) and the "phrase-grid prior beats chance by only 1.3-2.25x" figure.

Kill condition (docs/implementation-plan-v3.4.md item 8): the phrase-grid
classifier fails to beat the duration-only baseline (macro-F1 over the two
classes, pooled over the four gold songs). Recorded pass/fail regardless.
"""
from __future__ import annotations

import numpy as np

from . import features as feat_mod
from . import grid as grid_mod
from . import paths
from . import truth as truth_mod

CLASSES = ("structural", "micro")


def _grid_for(cache: dict) -> tuple[float, float, float]:
    db = cache["downbeats"]
    bar_len = grid_mod.bar_length(db)
    phase_s, phrase_len_s = grid_mod.fit_phrase_grid(
        cache["boundary_set"], db, paths.PHRASE_BARS
    )
    return phase_s, phrase_len_s, bar_len


def _rows_for_song(song: str) -> list[dict]:
    cache = feat_mod.load_cache(song)
    phase_s, phrase_len_s, bar_len = _grid_for(cache)
    starts = cache["block_starts"]
    ends = cache["block_ends"]
    titles = [str(t) for t in cache["block_titles"]]
    rows = []
    for s, e, title in zip(starts, ends, titles):
        s, e = float(s), float(e)
        pred_kind, fit_bars = grid_mod.classify_block(s, e, phase_s, phrase_len_s, bar_len)
        rows.append(
            {
                "title": title,
                "start_s": s,
                "end_s": e,
                "truth": truth_mod.truth_kind(title, s, e, bar_len),
                "grid_pred": pred_kind,
                "grid_fit_bars": fit_bars,
                "baseline_pred": grid_mod.baseline_kind(s, e, bar_len),
            }
        )
    return rows


def _prf(rows: list[dict], pred_key: str) -> dict[str, tuple]:
    """per-class (P, R, F1, support) + accuracy under key 'acc'."""
    out: dict[str, tuple] = {}
    n_correct = sum(1 for r in rows if r[pred_key] == r["truth"])
    for c in CLASSES:
        tp = sum(1 for r in rows if r[pred_key] == c and r["truth"] == c)
        fp = sum(1 for r in rows if r[pred_key] == c and r["truth"] != c)
        fn = sum(1 for r in rows if r[pred_key] != c and r["truth"] == c)
        sup = sum(1 for r in rows if r["truth"] == c)
        p = tp / (tp + fp) if (tp + fp) else 0.0
        rc = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * p * rc / (p + rc) if (p + rc) else 0.0
        out[c] = (p, rc, f1, sup)
    out["acc"] = (n_correct / len(rows) if rows else 0.0,)
    out["macro_f1"] = ((out["structural"][2] + out["micro"][2]) / 2,)
    return out


def _pooled_rows() -> list[dict]:
    rows: list[dict] = []
    for song in paths.GOLD_SONGS:
        rows += _rows_for_song(song)
    return rows


def _edge_lock_table() -> list[str]:
    song = "Queen of Kings - Alessandra"
    cache = feat_mod.load_cache(song)
    phase_s, phrase_len_s, bar_len = _grid_for(cache)
    starts = cache["block_starts"]
    ends = cache["block_ends"]
    titles = [str(t) for t in cache["block_titles"]]
    edges: list[tuple[float, str]] = []
    seen: list[float] = []
    for s, e, title in zip(starts, ends, titles):
        for val in (float(s), float(e)):
            if not any(abs(val - x) < 0.3 for x in seen):
                seen.append(val)
                edges.append((val, title))
    edges.sort()
    lines = [
        "QUEEN OF KINGS — operator edge vs the fitted 4-bar phrase grid",
        "=" * 70,
        f"  bar_len={bar_len:.3f}s  phrase_len={phrase_len_s:.3f}s  "
        f"grid phase={phase_s:.3f}s  (structural threshold "
        f"{grid_mod.STRUCTURAL_MAX_BARS} bars)",
        "",
        f"  {'edge (s)':>9}  {'fit (bars)':>10}  {'kind':>10}   context",
    ]
    n_lock = 0
    for val, title in edges:
        fb = grid_mod.grid_fit_bars(val, phase_s, phrase_len_s, bar_len)
        kind = "structural" if fb <= grid_mod.STRUCTURAL_MAX_BARS else "micro"
        n_lock += int(kind == "structural")
        lines.append(f"  {val:>9.2f}  {fb:>10.3f}  {kind:>10}   {title[:34]}")
    lines.append("")
    lines.append(f"  {n_lock} of {len(edges)} operator edges lock to the 4-bar grid")
    lines.append("")
    return lines


def _chance_line() -> list[str]:
    """Observed lock-rate over ALL operator edges vs the chance lock-rate
    (2 * threshold_bars / phrase_bars). Reproduces the refinement doc's
    'beats chance by only 1.3-2.25x' framing."""
    chance = 2 * grid_mod.STRUCTURAL_MAX_BARS / paths.PHRASE_BARS
    lines = ["PHRASE-GRID PRIOR vs CHANCE  (all operator edges, per song)", "-" * 70,
             f"  chance lock-rate = 2 * {grid_mod.STRUCTURAL_MAX_BARS} / {paths.PHRASE_BARS} "
             f"= {chance:.3f}", ""]
    ratios = []
    for song in paths.SONGS:
        cache = feat_mod.load_cache(song)
        phase_s, phrase_len_s, bar_len = _grid_for(cache)
        vals = list(cache["block_starts"]) + list(cache["block_ends"])
        if not vals or phrase_len_s <= 0:
            continue
        locked = sum(
            1
            for v in vals
            if grid_mod.grid_fit_bars(float(v), phase_s, phrase_len_s, bar_len)
            <= grid_mod.STRUCTURAL_MAX_BARS
        )
        rate = locked / len(vals)
        ratio = rate / chance if chance else 0.0
        ratios.append(ratio)
        lines.append(f"  {song:<34} lock-rate {rate:.3f}   x chance = {ratio:.2f}")
    if ratios:
        lines.append("")
        lines.append(
            f"  range: {min(ratios):.2f}x - {max(ratios):.2f}x  "
            f"(mean {np.mean(ratios):.2f}x) — a weak prior, not a precision filter"
        )
    lines.append("")
    return lines


def build_report() -> str:
    lines = ["STRUCTURAL vs MICRO — block-kind agreement with operator hints",
             "=" * 70, ""]

    for song in paths.GOLD_SONGS:
        rows = _rows_for_song(song)
        g = _prf(rows, "grid_pred")
        b = _prf(rows, "baseline_pred")
        lines.append(song)
        lines.append(
            f"  {'method':<18}{'acc':>6}{'macroF1':>9}"
            f"{'  struct P/R/F1':>20}{'  micro P/R/F1':>20}"
        )
        for label, m in (("phrase-grid", g), ("duration-only", b)):
            s_, mi_ = m["structural"], m["micro"]
            lines.append(
                f"  {label:<18}{m['acc'][0]:>6.2f}{m['macro_f1'][0]:>9.2f}"
                f"   {s_[0]:.2f}/{s_[1]:.2f}/{s_[2]:.2f}"
                f"       {mi_[0]:.2f}/{mi_[1]:.2f}/{mi_[2]:.2f}"
            )
        lines.append("")

    pooled = _pooled_rows()
    g = _prf(pooled, "grid_pred")
    b = _prf(pooled, "baseline_pred")
    lines.append("POOLED (4 gold songs)")
    lines.append(
        f"  {'method':<18}{'acc':>6}{'macroF1':>9}"
        f"{'  struct P/R/F1':>20}{'  micro P/R/F1':>20}   support s/m"
    )
    for label, m in (("phrase-grid", g), ("duration-only", b)):
        s_, mi_ = m["structural"], m["micro"]
        lines.append(
            f"  {label:<18}{m['acc'][0]:>6.2f}{m['macro_f1'][0]:>9.2f}"
            f"   {s_[0]:.2f}/{s_[1]:.2f}/{s_[2]:.2f}"
            f"       {mi_[0]:.2f}/{mi_[1]:.2f}/{mi_[2]:.2f}       {s_[3]}/{mi_[3]}"
        )
    lines.append("")

    grid_mf1 = g["macro_f1"][0]
    base_mf1 = b["macro_f1"][0]
    passed = grid_mf1 > base_mf1
    lines.append("KILL CONDITION — phrase-grid must beat the duration-only baseline "
                 "(pooled macro-F1)")
    lines.append(f"  phrase-grid macro-F1 = {grid_mf1:.3f}   "
                 f"duration-only macro-F1 = {base_mf1:.3f}")
    lines.append(
        f"  OUTCOME: {'PASS — phrase-grid beats the baseline' if passed else 'FAIL — does not beat the baseline; kept for one review pass, NOT tuned'}"
    )
    lines.append("")

    lines += _chance_line()
    lines += _edge_lock_table()
    return "\n".join(lines)


def write_report() -> None:
    paths.OUT_ROOT.mkdir(parents=True, exist_ok=True)
    text = build_report()
    (paths.OUT_ROOT / "score.txt").write_text(text + "\n")
    print(text)
