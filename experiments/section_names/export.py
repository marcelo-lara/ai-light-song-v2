"""Write `reference/proposals/section_names.json` — the "Section Names" lane input.

A proposal to audition, never ground truth, and never an input from
`reference/human/` (the operator's reviewed segments are the scoring reference,
read only by `score.py`). `blocks[]` tile the song. A song with no build->drop
unit gets its CURRENT `sections.json` rows back, attributed (`source:
"sections.json"`), `status: "kept_current"`.
"""
from __future__ import annotations

import json

from . import features, label, paths

SCHEMA_VERSION = "1.0"


def load_hint(song: str) -> dict | None:
    p = paths.structure_hint_path(song)
    return json.loads(p.read_text()) if p.exists() else None


def current_rows(song: str) -> list[dict]:
    rows = json.loads(paths.sections_path(song).read_text())["sections"]
    out = []
    for k, r in enumerate(rows):
        conf = r.get("function_confidence")
        out.append({
            "id": f"name-{k + 1:02d}", "start_s": round(float(r["start"]), 3), "end_s": round(float(r["end"]), 3),
            "label": r.get("function") or "unknown",
            "confidence": None if conf is None else round(float(conf), 3),
            "why": [f"kept: the current sections.json label (function_status {r.get('function_status')!r})"],
            "unit": None, "phrase_ids": [], "start_kind": "kept_current", "inherited_from": None,
            "source": "sections.json",
        })
    return out


def build(song: str, use_hint: bool = True) -> dict:
    cache = features.load_cache(song)
    phrases = json.loads(paths.phrases_path(song).read_text())["blocks"]
    hint = load_hint(song) if use_hint else None
    ctx = label.Ctx(cache)
    res = label.label_song(ctx, phrases, hint)
    if res["status"] == "named":
        blocks = res["blocks"]
        for b in blocks:
            b["source"] = "section_names"
    else:
        blocks = current_rows(song)
    return {**res, "blocks": blocks, "phrases_n": len(phrases)}


def export(song: str) -> dict:
    res = build(song, use_hint=True)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": song,
        "generated_from": {
            "experiment": "experiments/section_names",
            "engine": "drops = phrase starts where a kick or bass entry coincides with a hit "
                      "(gestures impact or the end of a near-silent gap); Pre-Drop / Fill / Build-Up / "
                      "Pre-Build before them, Intro / Breakdown / Outro by position, Fills closing phrases; "
                      "a drop that repeats an earlier one inherits its label; hint = prior only",
            "inputs": ["reference/proposals/phrases.json", "loudness.json", "beats.json (times + off_grid_spans only)",
                       "arrangement_state.json (vocals_phrase)", "song_event_timeline.json (impact rows only)",
                       "artifacts/essentia/fft_bands.drums.json", "artifacts/essentia/fft_bands.json",
                       "sections.json (current labels, kept only when no unit is found)",
                       "reference/pre-analysis/structure.json (prior only)"],
            "hint": res["prior"],
            "params": {k: getattr(label, k) for k in dir(label) if k.isupper() and not k.startswith("_")
                       and isinstance(getattr(label, k), (int, float))} | {
                "silence": {k: getattr(features, k) for k in dir(features) if k.startswith("SIL_")}},
        },
        "status": res["status"],
        "status_reason": res["status_reason"],
        "units": res["units"],
        "blocks": res["blocks"],
    }
    out = paths.proposals_path(song)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n")
    return payload


def export_all(songs: list[str]) -> None:
    for song in songs:
        p = export(song)
        names = [b["label"] for b in p["blocks"]]
        print(f"exported {song} — {p['status']}, {len(p['blocks'])} blocks, {len(p['units'])} units: "
              + (" > ".join(names) if p["status"] == "named" else p["status_reason"]))
