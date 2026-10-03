"""Checks: agreement with omnizart `drum_events` kicks (+-50 ms) per song, and the Medicine bar
check (bars 9-18 `kick_present`, 19-22 not). Writes out/score.txt. Agreement is not accuracy:
omnizart over-labels (toms, snares) and misses soft kicks; it is a cross-check, not truth.
"""
from __future__ import annotations

import json

import numpy as np

from . import export, paths, present

TOL_S = 0.050
MEDICINE = "Medicine-MilkInc"
YES_BARS = range(9, 19)
NO_BARS = range(19, 23)


def _kicks(song: str) -> list[float]:
    ev = json.loads(paths.drum_events_path(song).read_text())["events"]
    return sorted(e["time"] for e in ev if e["event_type"] == "kick")


def _frac_within(a: np.ndarray, b: np.ndarray) -> float | None:
    if len(a) == 0:
        return None
    if len(b) == 0:
        return 0.0
    d = np.abs(a[:, None] - b[None, :]).min(axis=1)
    return float((d <= TOL_S).mean())


def agreement(song: str) -> dict:
    ev = [e for e in export.load_cache(song)["events"] if e["echo_of"] is None]
    mine = np.array([e["time"] for e in ev])
    om = np.array(_kicks(song))
    return {"mine": len(mine), "omnizart": len(om),
            "precision": _frac_within(mine, om), "recall": _frac_within(om, mine)}


def bar_check() -> list[str]:
    cache = export.load_cache(MEDICINE)
    beats = json.loads(paths.beats_path(MEDICINE).read_text())["beats"]
    bars: dict[int, list[float]] = {}
    for b in beats:
        bars.setdefault(b["bar"], []).append(b["time"])
    lines, bad = [], 0
    for bar in list(YES_BARS) + list(NO_BARS):
        s, e = min(bars[bar]), (min(bars[bar + 1]) if bar + 1 in bars else max(bars[bar]) + 0.4)
        n, pres = present.window_counts(cache["events"], s, e, min(present.BAR_MIN_ATTACKS, len(bars[bar])))
        want = bar in YES_BARS
        bad += pres != want
        lines.append(f"  bar {bar:2d} {s:7.2f}-{e:7.2f} kick_attacks {n:2d} kick_present {pres!s:5} expected {want!s:5}"
                     + ("" if pres == want else "  MISMATCH"))
    lines.append(f"  mismatches: {bad} of {len(lines)}")
    return lines


def run() -> None:
    lines = [f"kick_attacks vs omnizart kicks, +-{int(TOL_S * 1000)} ms (precision = my attacks with an omnizart kick; recall = omnizart kicks with an attack)"]
    rows = []
    for song in paths.all_songs():
        try:
            a = agreement(song)
        except FileNotFoundError:
            continue
        rows.append(a)
        f = lambda v: "  n/a" if v is None else f"{v:5.2f}"
        lines.append(f"  {song:45s} attacks {a['mine']:4d} omnizart {a['omnizart']:4d} precision {f(a['precision'])} recall {f(a['recall'])}")
    ps = [r["precision"] for r in rows if r["precision"] is not None]
    rs = [r["recall"] for r in rows if r["recall"] is not None]
    lines.append(f"  mean over {len(rows)} songs: precision {np.mean(ps):.2f} recall {np.mean(rs):.2f}")
    lines.append("")
    lines.append("Medicine-MilkInc kick_present per bar (bars 9-18 yes, 19-22 no)")
    lines += bar_check()
    paths.OUT_ROOT.mkdir(parents=True, exist_ok=True)
    (paths.OUT_ROOT / "score.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
