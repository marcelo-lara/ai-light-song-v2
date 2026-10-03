"""Item 31 checks, read from the exported proposals. Writes out/score.txt."""
from __future__ import annotations

import json

from . import paths

ARMIN = "Armin - Revolution"
MEDICINE = "Medicine-MilkInc"
LISTED = ("ayuni", "Charli-VonDutch")


def _load(song: str) -> dict:
    return json.loads(paths.proposals_path(song).read_text())


def _states(p: dict, lo: int, hi: int) -> list:
    return [(b["bar"], b["state"]) for b in p["bars"] if lo <= b["bar"] <= hi]


def run() -> None:
    lines = []
    for song, lo, hi in ((ARMIN, 53, 62), (MEDICINE, 7, 19)):
        p = _load(song)
        lines.append(f"{song}: bar states {lo}-{hi}: " + " ".join(f"{b}:{(s or '-')[:3]}" for b, s in _states(p, lo, hi)))
        for b in p["blocks"]:
            lines.append(f"  block {b['direction']} bars {b['start_bar']}-{b['end_bar']} end {b['end_time']:.2f}s "
                         f"{b['end_kind']} aftermath={b['aftermath']} conf={b['confidence']}")
    lines.append("")
    for song in LISTED:
        p = _load(song)
        lines.append(f"{song}: {len(p['blocks'])} sweeps (filter_sweep v1: 0)")
        for b in p["blocks"]:
            lines.append(f"  {b['direction']} {b['start_s']:.1f}-{b['end_s']:.1f}s bars {b['start_bar']}-{b['end_bar']} "
                         f"hl {b['hl_change_db']} dB roll {b['roll_change_oct']} oct aftermath={b['aftermath']} conf={b['confidence']}")
    lines.append("")
    tot, per, none = 0, [], 0
    for song in paths.all_songs():
        bl = _load(song)["blocks"]
        tot += len(bl)
        none += sum(b["aftermath"] == "none" for b in bl)
        per.append(f"{song[:14]}={len(bl)}")
    lines.append(f"corpus: {tot} sweeps over {len(per)} songs, {none} with aftermath none")
    lines.append(" ".join(per))
    paths.OUT_ROOT.mkdir(parents=True, exist_ok=True)
    (paths.OUT_ROOT / "score.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
