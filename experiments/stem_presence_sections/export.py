"""Write `reference/proposals/stem_presence_sections.json` — the timeline
lane input.

Pipeline: `features.py` (per-bar levels) -> `state_machine.py` (classify,
hysteresis, group into runs) -> `onset.py` (move each boundary from the bar
edge to the nearer physical stem onset). A proposal to audition against Human
Hints / the hand `segments.seed.json`, never ground truth, and never scored on
its own output (see `score.py`'s use of `truth_common.structure`).
"""
from __future__ import annotations

import datetime
import json

from . import features as feat_mod
from . import onset as onset_mod
from . import paths
from . import state_machine as sm

SCHEMA_VERSION = "1.0"

_PRESENCE = {
    "full": (True, True),
    "bass_only": (True, False),
    "drums_only": (False, True),
    "stripped": (False, False),
}


def _changed_stems(label_before: str, label_after: str) -> list[str]:
    bass_before, drums_before = _PRESENCE[label_before]
    bass_after, drums_after = _PRESENCE[label_after]
    changed = []
    if bass_before != bass_after:
        changed.append("bass")
    if drums_before != drums_after:
        changed.append("drums")
    return changed


def _drums_detail(classifications: list[sm.BarClassification], indices: tuple[int, ...]) -> str:
    """Majority `drums_state` (full/sparse/off) inside a block — the coarse
    `state` label only distinguishes drums-present-or-not; this keeps the
    full/sparse split for reviewers without letting it cut a boundary."""
    counts: dict[str, int] = {}
    for i in indices:
        s = classifications[i].drums_state
        counts[s] = counts.get(s, 0) + 1
    return max(counts, key=counts.get)


def build_sections(song: str) -> tuple[list[sm.Section], list[sm.BarClassification], dict]:
    cache = feat_mod.load_or_compute_cache(song)
    bar_rows = cache["bars"]
    thr = cache["thresholds"]

    classifications = [
        sm.classify_bar(
            row["level_bass"], row["level_drums"], row["level_vocals"],
            thr["bass_p95"], thr["drums_p95"], thr["vocals_p95"],
        )
        for row in bar_rows
    ]
    raw_states = [(c.bass_state, c.drums_state) for c in classifications]
    smoothed = sm.apply_hysteresis(raw_states, sm.MIN_SECTION_BARS)
    sections = sm.group_into_sections(smoothed, bar_rows)
    return sections, classifications, cache


def export(song: str) -> dict:
    sections, classifications, cache = build_sections(song)
    bar_rows = cache["bars"]
    duration = cache["duration"]
    frames = onset_mod.load_frames(song)

    refined: list[onset_mod.RefinedBoundary] = []
    for k in range(1, len(sections)):
        prev, nxt = sections[k - 1], sections[k]
        changed = _changed_stems(prev.label, nxt.label)
        last_prev_bar = bar_rows[prev.bar_indices[-1]]
        first_next_bar = bar_rows[nxt.bar_indices[0]]
        level_before = {"bass": last_prev_bar["level_bass"], "drums": last_prev_bar["level_drums"]}
        level_after = {"bass": first_next_bar["level_bass"], "drums": first_next_bar["level_drums"]}
        window_s = max(
            last_prev_bar["end"] - last_prev_bar["start"],
            first_next_bar["end"] - first_next_bar["start"],
        )
        refined.append(
            onset_mod.refine_boundary(
                frames, nxt.start_s, changed, level_before, level_after, window_s
            )
        )

    edges = [0.0] + [r.time for r in refined] + [duration]

    blocks = []
    for i, sec in enumerate(sections):
        n = len(sec.bar_indices)
        confidence = sum(classifications[j].confidence for j in sec.bar_indices) / n
        vocals_frac = sum(1 for j in sec.bar_indices if classifications[j].vocals_present) / n
        blocks.append({
            "start_s": round(edges[i], 3),
            "end_s": round(edges[i + 1], 3),
            "bar_start": sec.bar_start,
            "bar_end": sec.bar_end,
            "state": sec.label,
            "drums_detail": _drums_detail(classifications, sec.bar_indices),
            "vocals_present_fraction": round(vocals_frac, 4),
            "confidence": round(confidence, 4),
            "boundary_resolved": None if i == 0 else refined[i - 1].resolved,
        })

    payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": song,
        "generated_from": {
            "experiment": "experiments/stem_presence_sections",
            "engine": "per-bar bass on/off + drums full/sparse/off state machine, "
                      "hysteresis-merged, boundaries moved to the nearest 20 ms "
                      "loudness-frame stem onset",
            "bar_grid": "beats.json downbeats",
            "params": {
                "min_section_bars": sm.MIN_SECTION_BARS,
                "bass_on_frac_of_p95": sm.BASS_ON_FRAC,
                "drums_full_frac_of_p95": sm.DRUMS_FULL_FRAC,
                "drums_sparse_frac_of_p95": sm.DRUMS_SPARSE_FRAC,
                "vocals_on_frac_of_p95": sm.VOCALS_ON_FRAC,
            },
            "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        },
        "blocks": blocks,
    }
    out_path = paths.proposals_path(song)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2) + "\n")
    return payload


def export_all(songs: list[str]) -> None:
    for song in songs:
        payload = export(song)
        print(f"exported {song} — {len(payload['blocks'])} blocks")
