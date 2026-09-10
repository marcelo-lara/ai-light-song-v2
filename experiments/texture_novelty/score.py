"""Boundary F1 @ +-1.0 s vs human-hint block edges, on the four gold songs.

Tabulated against the incumbents the refinement doc names: `sections.json` and
`arrangement_state.json`. Cheap baselines: mix-RMS delta, MFCC novelty.

Kill condition (docs/implementation-plan-v3.4.md item 6): a feature set passes
only if it lifts **precision > 0.5 at recall >= 0.8**. Evaluated pooled over the
four gold songs and also per song. Recorded pass/fail regardless.
"""
from __future__ import annotations

import numpy as np

from . import features as feat_mod
from . import novelty as nov
from . import paths

TOL = 1.0
FEATURE_SET_LABELS = {
    1: "feat 1 — raw 7-band MIX vector (measured baseline)",
    2: "feat 2 — chroma(MIX) + percussive-band weight",
    3: "feat 3 — per-stem band weight (28-dim)",
}


def _pred_for_feature_set(cache: dict, fs: int) -> np.ndarray:
    m = feat_mod.feature_matrix(cache, fs)
    curve = nov.novelty_curve(m)
    return nov.pick_boundaries(cache["times"], curve)


def _pred_mfcc(cache: dict) -> np.ndarray:
    curve = nov.novelty_curve(feat_mod._l2(cache["mfcc_mix"]))
    return nov.pick_boundaries(cache["times"], curve)


def _method_predictions(cache: dict) -> dict[str, np.ndarray]:
    return {
        FEATURE_SET_LABELS[1]: _pred_for_feature_set(cache, 1),
        FEATURE_SET_LABELS[2]: _pred_for_feature_set(cache, 2),
        FEATURE_SET_LABELS[3]: _pred_for_feature_set(cache, 3),
        "baseline — mix-RMS delta": nov.rms_delta_boundaries(cache["times"], cache["mix_rms"]),
        "baseline — MFCC novelty": _pred_mfcc(cache),
        "incumbent — sections.json": cache["edges_sections"],
        "incumbent — arrangement_state.json": cache["edges_arrangement"],
    }


def _accumulate() -> tuple[dict, dict]:
    per_song: dict[str, dict[str, tuple]] = {}
    pooled: dict[str, list[int]] = {}  # method -> [tp, n_pred, n_ref]
    for song in paths.GOLD_SONGS:
        cache = feat_mod.load_cache(song)
        ref = cache["edges_hint"]
        per_song[song] = {}
        for method, pred in _method_predictions(cache).items():
            p, r, f1, tp, npred, nref = nov.boundary_f1(np.asarray(pred, dtype=float), ref, TOL)
            per_song[song][method] = (p, r, f1, tp, npred, nref)
            acc = pooled.setdefault(method, [0, 0, 0])
            acc[0] += tp
            acc[1] += npred
            acc[2] += nref
    return per_song, pooled


def _pooled_prf(acc: list[int]) -> tuple[float, float, float]:
    tp, npred, nref = acc
    p = tp / npred if npred else 0.0
    r = tp / nref if nref else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) else 0.0
    return p, r, f1


def build_report() -> str:
    per_song, pooled = _accumulate()
    methods = list(next(iter(per_song.values())).keys())
    lines: list[str] = ["Texture Novelty — boundary F1 @ +-1.0 s vs human-hint block edges",
                        "=" * 74, ""]

    for song in paths.GOLD_SONGS:
        lines.append(song)
        lines.append(f"  {'method':<44}{'P':>6}{'R':>6}{'F1':>6}{'tp':>5}{'pred':>6}{'ref':>5}")
        for m in methods:
            p, r, f1, tp, npred, nref = per_song[song][m]
            lines.append(f"  {m:<44}{p:>6.2f}{r:>6.2f}{f1:>6.2f}{tp:>5}{npred:>6}{nref:>5}")
        lines.append("")

    lines.append("POOLED (4 gold songs)")
    lines.append(f"  {'method':<44}{'P':>6}{'R':>6}{'F1':>6}{'tp':>5}{'pred':>6}{'ref':>5}")
    for m in methods:
        tp, npred, nref = pooled[m]
        p, r, f1 = _pooled_prf(pooled[m])
        lines.append(f"  {m:<44}{p:>6.2f}{r:>6.2f}{f1:>6.2f}{tp:>5}{npred:>6}{nref:>5}")
    lines.append("")

    lines.append("KILL CONDITION — a feature set passes iff precision > 0.5 at recall >= 0.8")
    any_pass = False
    for fs, label in FEATURE_SET_LABELS.items():
        p, r, f1 = _pooled_prf(pooled[label])
        pooled_pass = p > 0.5 and r >= 0.8
        song_pass = [
            s for s in paths.GOLD_SONGS
            if per_song[s][label][0] > 0.5 and per_song[s][label][1] >= 0.8
        ]
        any_pass = any_pass or pooled_pass
        verdict = "PASS" if pooled_pass else "fail"
        extra = f"  (per-song pass: {', '.join(song_pass)})" if song_pass else ""
        lines.append(f"  {label:<44} pooled P={p:.2f} R={r:.2f} -> {verdict}{extra}")
    lines.append("")
    lines.append(f"  OUTCOME: {'PASS — at least one feature set clears the bar' if any_pass else 'FAIL — no feature set clears the bar; kill candidate'}")
    lines.append("")
    return "\n".join(lines)


def write_report() -> None:
    paths.OUT_ROOT.mkdir(parents=True, exist_ok=True)
    text = build_report()
    (paths.OUT_ROOT / "score.txt").write_text(text)
    print(text)
