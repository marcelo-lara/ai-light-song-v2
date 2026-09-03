"""Write one reviewable proposal file per song, for the debugger's allin1 lanes.

Output goes to `data/analysis/<song>/reference/proposals/allin1.json` —
constitution §3.2: an experiment's output is a *proposal*, so it never lands in
`artifacts/`, never joins the stable top-level contract, and never overwrites
`reference/human/`, which stays purely hand-authored ground truth.

The file is written for a person auditioning it against the song, so every
transition carries `matches_human_impact`: the lane can then mark what already
agrees with a hand-placed `drop impact` and leave the rest as open questions.
That flag is a review aid computed from existing labels — it is not evidence
that the transition is right on the eighteen songs that carry no labels at all.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import activations, features, model
from .paths import proposals_path

SCHEMA_VERSION = "1.0"

#: A transition counts as matching a hand-placed impact inside this window.
#: 0.5 s is the tolerance the drop survey scored at; the human marks themselves
#: sit a median 0.135 s off the nearest beat, so anything tighter measures the
#: mouse, not the music.
MATCH_TOLERANCE_S = 0.5

NOTE = (
    "allin1 (Kim & Nam 2023) functional segmentation, exported by experiments/allin1. "
    "Proposals for review, not deliverables: nothing in src/ reads this file. "
    "Audition the transitions against the Human Hints lane — a transition is where a "
    "cue belongs, and the label pair says what kind of change it is."
)


def _match(impacts: list[float], time: float) -> float | None:
    near = [i for i in impacts if abs(i - time) <= MATCH_TOLERANCE_S]
    return min(near, key=lambda i: abs(i - time)) if near else None


def _frame_labels(song: str, sections: list[dict]) -> dict | None:
    """What the frame-level posterior says that the segment list cannot.

    Present only when the activation cache exists (`run cache-activations`).
    Two things travel here, both of them "beyond the arrangement":

    * **confidence per section** — normalised entropy of the label posterior
      inside each committed section. A section the model was never sure about
      is a section whose *name* should not be trusted even where its boundary
      is right, and the segment list has no room to say so.
    * **shadow labels** — sustained posterior mass on a label the committed
      segmentation never used anywhere in the song. A `break` holding a fifth of
      the mass for ten seconds inside a stretch published as `inst` is a
      breakdown the 8-bar argmax could not express.
    """
    if not activations.cache_path(song).exists():
        return None
    data = activations.load(song)
    times = data["times"]
    ent = activations.entropy(data)
    labels, posterior = activations.posterior(data)

    per_section = []
    for section in sections:
        inside = (times >= section["start_s"]) & (times < section["end_s"])
        if not inside.any():
            continue
        mean_posterior = posterior[:, inside].mean(axis=1)
        order = mean_posterior.argsort()[::-1]
        per_section.append({
            "id": section["id"],
            "entropy": round(float(ent[inside].mean()), 3),
            "top_label": labels[int(order[0])],
            "top_share": round(float(mean_posterior[order[0]]), 3),
            "runner_up": labels[int(order[1])],
            "runner_up_share": round(float(mean_posterior[order[1]]), 3),
            # The published label and the frame-level argmax disagreeing is a
            # flag worth surfacing, not an error to hide.
            "agrees_with_segment": labels[int(order[0])] == section["function"],
        })

    return {
        "rate_hz": float(data["rate_hz"]),
        "mean_entropy": round(float(ent.mean()), 3),
        "note": ("Frame-level label posterior at 10 Hz, from allin1's own activations. "
                 "Entropy is 0 when the model is certain and 1 when it has no opinion; "
                 "shadow labels are labels with sustained posterior mass that the "
                 "committed 8-bar segmentation never used."),
        "per_section": per_section,
        "shadow_labels": activations.shadow_labels(data, sections),
    }


def export_song(song: str) -> Path:
    raw = model.load(song)
    derived = features.derive(song, raw)
    impacts = features.human_impacts(song)

    degenerate = derived["labelling"]["status"] != "ok"
    for section in derived["sections"]:
        # Honesty rule: where the model is out of distribution the *name* is not
        # trustworthy even though the boundary may be. Say so per row rather
        # than letting a reader assume every label carries the same weight.
        section["function_status"] = "unknown" if degenerate else "named"
    for transition in derived["transitions"]:
        transition["matches_human_impact"] = _match(impacts, transition["time_s"])
        transition["function_status"] = "unknown" if degenerate else "named"

    payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": song,
        "generated_from": {
            "engine": "experiments.allin1",
            "model": raw.get("source", {}).get("model", "allin1"),
            "raw_cache": f"experiments/allin1/cache/{song}.json",
        },
        "note": NOTE,
        "human_impacts": impacts,
        "match_tolerance_s": MATCH_TOLERANCE_S,
        **derived,
    }
    frames = _frame_labels(song, derived["sections"])
    if frames is not None:
        payload["frame_labels"] = frames
    path = proposals_path(song)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return path


def summary_line(song: str, path: Path) -> str:
    payload = json.loads(path.read_text())
    sections = payload["sections"]
    transitions = payload["transitions"]
    impacts = payload["human_impacts"]
    status = payload["labelling"]["status"]
    matched = sum(1 for t in transitions if t["matches_human_impact"] is not None)
    tag = f"{matched}/{len(impacts)} impacts" if impacts else "unlabelled"
    labels = " ".join(sorted({s["function"] for s in sections}))
    flag = "  DEGENERATE" if status != "ok" else ""
    return (f"  {song:<40} {len(sections):2d} sections  {len(transitions):2d} transitions  "
            f"({tag})  {labels}{flag}")
