"""Validation gate: hits on the operator-described light changes, points per minute, baseline.

Truth (docs/product-refinement-v3.12.md, bars on the *current* beats.json): Medicine bars 8 fill,
9 groove_in, 16 build, 19 break, 23 drop, none in the steady bars 10-14; Armin bars 55 build,
59 gap, 60 drop. A hit is a point within one beat (the song's median beat interval) of the target
bar's start; the role is checked separately. Baselines: `loudness-only` (mix-loudness |z| >= 3 on the
same walk) and a rate-matched loudness-only. `no_novelty` is the same detector without the
texture_novelty channel.
"""
from __future__ import annotations

import numpy as np

from . import detect, features, paths

TARGETS = {
    "Medicine-MilkInc": [(8, "fill"), (9, "groove_in"), (16, "build"), (19, "break"), (23, "drop")],
    "Armin - Revolution": [(55, "build"), (59, "gap"), (60, "drop")],
}
STEADY = {"Medicine-MilkInc": (10, 14)}
OPERATOR_SPAN = {"Medicine-MilkInc": (9, 17), "Armin - Revolution": (56, 59)}
REPORT_ONLY = ("ayuni", "Charli-VonDutch")


def beat_s(bars: list[dict]) -> float:
    return float(np.median([b["end_s"] - b["start_s"] for b in bars if not b["irregular"]])) / 4.0


def score_song(song: str, points: list[dict], bars: list[dict]) -> list[dict]:
    by_bar = {b["bar"]: b for b in bars}
    tol = beat_s(bars)
    rows = []
    for bar, role in TARGETS[song]:
        t = by_bar[bar]["start_s"]
        near = min(points, key=lambda p: abs(p["time_s"] - t), default=None)
        dt = None if near is None else near["time_s"] - t
        hit = near is not None and abs(dt) <= tol + 1e-6
        rows.append({"bar": bar, "role": role, "t": t, "hit": hit, "got_bar": near["bar"] if near else None,
                     "dt": dt, "got_role": near.get("role") if near else None})
    return rows


def duration_min(bars: list[dict]) -> float:
    return (bars[-1]["end_s"] - bars[0]["start_s"]) / 60.0


def corpus(songs: list[str], texture: bool = True, threshold: float = detect.S_THRESHOLD) -> dict:
    out = {}
    for s in songs:
        bars = features.load_bars(s)
        tex = features.load_cache(s, bars)["texture_novelty"] if texture else None
        out[s] = (bars, detect.detect(bars, tex, threshold=threshold))
    return out


def hits(points_by_song: dict, bars_by_song: dict) -> int:
    return sum(r["hit"] for song in TARGETS for r in score_song(song, points_by_song[song], bars_by_song[song]))


def steady(points_by_song: dict) -> int:
    lo, hi = STEADY["Medicine-MilkInc"]
    return sum(1 for p in points_by_song["Medicine-MilkInc"] if lo <= p["bar"] <= hi)


def baseline_points(songs: list[str], z: float) -> dict:
    return {s: detect.detect_loudness_only(features.load_bars(s), z) for s in songs}


def rate(points_by_song: dict, bars_by_song: dict) -> tuple[float, float, float]:
    """(corpus points/min, median per-song points/min, max per-song)."""
    per = [len(points_by_song[s]) / duration_min(bars_by_song[s]) for s in points_by_song]
    total = sum(len(p) for p in points_by_song.values()) / sum(duration_min(bars_by_song[s]) for s in points_by_song)
    return total, float(np.median(per)), float(max(per))


def _fmt_rows(rows: list[dict]) -> list[str]:
    out = []
    for r in rows:
        if r["got_bar"] is None:
            out.append(f"  bar {r['bar']:>3} {r['role']:<9} MISS (no points)")
            continue
        out.append(f"  bar {r['bar']:>3} {r['role']:<9} {'HIT ' if r['hit'] else 'MISS'}  nearest point bar {r['got_bar']:>3} "
                   f"({r['dt']:+.2f} s)  role {r['got_role'] or '-':<9} {'role ok' if r['got_role'] == r['role'] else 'role differs'}")
    return out


def run() -> None:
    songs = paths.all_songs()
    full = corpus(songs)
    bars = {s: v[0] for s, v in full.items()}
    pts = {s: v[1] for s, v in full.items()}
    no_nov = {s: v[1] for s, v in corpus(songs, texture=False).items()}
    lines = ["# light_changes score", ""]
    r_full, r_med, r_max = rate(pts, bars)
    lines.append(f"## corpus rate ({len(songs)} songs)")
    lines.append(f"light_changes        {r_full:5.2f} points/min   per-song median {r_med:5.2f}  max {r_max:5.2f}")
    r_nn = rate(no_nov, bars)
    lines.append(f"no texture_novelty   {r_nn[0]:5.2f} points/min   per-song median {r_nn[1]:5.2f}  max {r_nn[2]:5.2f}")
    base3 = baseline_points(songs, 3.0)
    rb = rate(base3, bars)
    lines.append(f"loudness-only |z|>=3 {rb[0]:5.2f} points/min   per-song median {rb[1]:5.2f}  max {rb[2]:5.2f}")
    matched_z, matched = 3.0, base3
    best = abs(rb[0] - r_full)
    for z in np.arange(1.5, 12.01, 0.25):
        cand = baseline_points(songs, float(z))
        gap = abs(rate(cand, bars)[0] - r_full)
        if gap < best:
            best, matched_z, matched = gap, float(z), cand
    rm = rate(matched, bars)
    lines.append(f"loudness-only rate-matched (|z|>={matched_z:.2f}) {rm[0]:5.2f} points/min   per-song median {rm[1]:5.2f}  max {rm[2]:5.2f}")
    lines.append("")
    tot = {"full": [0, 0], "no_novelty": [0, 0], "base3": [0, 0], "matched": [0, 0]}
    for song, targets in TARGETS.items():
        lines.append(f"## {song} (operator span bars {OPERATOR_SPAN[song][0]}-{OPERATOR_SPAN[song][1]})")
        b = bars[song]
        variants = {"full": pts[song], "no_novelty": no_nov[song],
                    "base3": base3[song], "matched": matched[song]}
        labels = {"full": "light_changes", "no_novelty": "no texture_novelty",
                  "base3": "loudness-only |z|>=3", "matched": f"loudness-only rate-matched |z|>={matched_z:.2f}"}
        for k, v in variants.items():
            rows = score_song(song, v, b)
            tot[k][0] += sum(r["hit"] for r in rows)
            tot[k][1] += len(rows)
            lines.append(f"{labels[k]}: {sum(r['hit'] for r in rows)}/{len(rows)} hit, {len(v)} points")
            if k in ("full", "base3"):
                lines += _fmt_rows(rows)
        if song in STEADY:
            lo, hi = STEADY[song]
            for k, v in variants.items():
                inside = [p["bar"] for p in v if lo <= p["bar"] <= hi]
                lines.append(f"  steady bars {lo}-{hi}, {labels[k]}: {len(inside)} points {inside}")
        lines.append("  all points ({}): ".format(labels["full"]) + ", ".join(f"{p['bar']}:{p['role']}" for p in pts[song]
                                                                       if OPERATOR_SPAN[song][0] - 4 <= p["bar"] <= OPERATOR_SPAN[song][1] + 6))
        lines.append("")
    lines.append("## threshold sweep: targets hit (of 8) vs corpus points/min (full detector vs loudness-only)")
    lines.append("full detector, pooled-score threshold:")
    for th in (5.0, 6.0, 7.0, 8.0, 9.0, 11.0, 13.0):
        c = corpus(songs, threshold=th)
        p = {s: v[1] for s, v in c.items()}
        lines.append(f"  S>={th:>4}: {rate(p, bars)[0]:5.2f}/min  {hits(p, bars)}/8 hit  steady-bar points {steady(p)}")
    lines.append("loudness-only, |z| threshold:")
    for z in (3.0, 2.5, 2.0, 1.75, 1.5):
        p = baseline_points(songs, z)
        lines.append(f"  |z|>={z:>4}: {rate(p, bars)[0]:5.2f}/min  {hits(p, bars)}/8 hit  steady-bar points {steady(p)}")
    lines.append("")
    lines.append("## targets hit, both songs (8 targets)")
    for k in tot:
        lines.append(f"{k:<11} {tot[k][0]}/{tot[k][1]}")
    lines.append("")
    for song in REPORT_ONLY:
        b = bars[song]
        lines.append(f"## {song} — no bar-level truth ({len(pts[song])} points, {len(pts[song]) / duration_min(b):.2f}/min)")
        lines.append("  " + ", ".join(f"{p['bar']}:{p['role']}" for p in pts[song]))
        lines.append("")
    text = "\n".join(lines) + "\n"
    paths.OUT_ROOT.mkdir(parents=True, exist_ok=True)
    (paths.OUT_ROOT / "score.txt").write_text(text)
    print(text)
