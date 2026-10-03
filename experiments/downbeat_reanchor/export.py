"""Write `reference/proposals/downbeat_reanchor.json` (a proposal, never ground truth).

`beats[]`: per beat `{index, time, bar, beat, type, downbeat_confidence}` — the labels that would replace
`beats.json`'s `bar`/`beat`/`type`/`downbeat_confidence` (times unchanged). `bars[]`: one row per bar
(`resolved` = its downbeat carries a confidence). `runs[]`: trusted runs with the chosen phase and its
source. `spans[]`: contiguous unresolved downbeats.
"""
from __future__ import annotations

import json

from . import anchors as A
from . import build, paths

SCHEMA_VERSION = "1.0"


def export(song: str) -> dict:
    res = build.build(song)
    times, labels = res["times"], res["beats"]
    beats = [{"index": i + 1, "time": round(t, 6), "bar": l["bar"], "beat": l["beat"],
              "type": "downbeat" if l["downbeat"] else "beat",
              "downbeat_confidence": l["confidence"]} for i, (t, l) in enumerate(zip(times, labels))]
    bars: list[dict] = []
    for i, l in enumerate(labels):
        if not bars or bars[-1]["bar"] != l["bar"]:
            bars.append({"bar": l["bar"], "start_s": times[i], "end_s": times[i], "beats_in_bar": 0,
                         "downbeat_confidence": None, "resolved": False})
        bars[-1]["beats_in_bar"] += 1
        bars[-1]["end_s"] = times[i + 1] if i + 1 < len(times) else times[i]
        if l["downbeat"]:
            bars[-1]["downbeat_confidence"] = l["confidence"]
            bars[-1]["resolved"] = l["confidence"] is not None
    for b in bars:
        b["irregular"] = b["beats_in_bar"] != A.BEATS_PER_BAR
    payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": song,
        "generated_from": {
            "experiment": "experiments/downbeat_reanchor",
            "engine": "beat times unchanged; one downbeat phase (residue of the beat index mod 4) per trusted run from "
                      "weighted anchor votes (kick-phase windows over item-29 kick attacks, impacts, bass/drums entries); "
                      "bars always 4 beats, the index relabelled never time warped; a downbeat with disagreeing local "
                      "votes -> downbeat_confidence null; no vote -> allin1's majority phase, unresolved",
            "inputs": ["reference/proposals/kick_attacks.json", "song_event_timeline.json", "arrangement_state.json",
                       "beats.json (times, off_grid_spans, allin1 phase as last resort)"],
            "params": {"kick_window_beats": A.KICK_WINDOW_BEATS, "kick_margin": A.KICK_MARGIN,
                       "kick_min_attacks": A.KICK_MIN_ATTACKS, "kick_weight": A.KICK_WEIGHT,
                       "snap_beat_frac": A.SNAP_BEAT_FRAC, "null_conf_weight": A.NULL_CONF_WEIGHT,
                       "local_beats": A.LOCAL_BEATS, "agree_min": A.AGREE_MIN, "evidence_min": A.EVIDENCE_MIN},
        },
        "runs": [{"start_s": times[r["lo"]], "end_s": times[r["hi"]], "phase": r["phase"], "source": r["source"]}
                 for r in res["runs"]],
        "spans": [{"start_s": s["start_s"], "end_s": s["end_s"], "resolved": False, "reason": s["reason"]}
                  for s in res["spans"]],
        "bars": bars,
        "beats": beats,
    }
    out = paths.proposals_path(song)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=1) + "\n")
    return payload


def export_all(songs: list[str]) -> None:
    for song in songs:
        p = export(song)
        un = sum(not b["resolved"] for b in p["bars"])
        irr = sum(b["irregular"] for b in p["bars"])
        print(f"exported {song} — {len(p['bars'])} bars ({un} unresolved, {irr} irregular incl. song edges)")
