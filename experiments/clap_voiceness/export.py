"""Write the CLAP contrastive differential to
`reference/proposals/clap_voiceness.json` via `voiceness_common.schema` — the
shared shape every voiceness candidate (items 4-7) writes, so they land on
one comparable timeline and score through one scorer.

`vocal_phrase` spans are exported for the timeline and so `scorer.py` has
something to compute boundary edges against, but that boundary-F1 number is
never a scored comparison for this candidate — see `score.py` and the
README's framing up front: this is an independent second opinion on the
frame-level call, not a boundary competitor.
"""
from __future__ import annotations

from experiments.voiceness_common.schema import (
    VocalPhrase,
    VoicenessFrame,
    VoicenessProposal,
)

from . import model, paths

EXPERIMENT = "experiments/clap_voiceness"
ENGINE = (
    'clap_voiceness.model (CLAP audio-text contrastive differential: '
    '"a person singing" vs "a flute, a synth lead"; two centrings + sigmoid)'
)


def export(song: str) -> dict:
    data = model.load(song)
    times = data["times"]
    voiceness = data["voiceness"]
    confidence = data["confidence"]

    frames = [
        VoicenessFrame(time_s=float(t), voiceness=float(v), confidence=float(c))
        for t, v, c in zip(times, voiceness, confidence)
    ]
    phrase_dicts = model.derive_vocal_phrases(times, voiceness, confidence)
    phrases = [
        VocalPhrase(start=p["start"], end=p["end"], confidence=p["confidence"])
        for p in phrase_dicts
    ]

    proposal = VoicenessProposal(
        song_name=song,
        experiment=EXPERIMENT,
        engine=ENGINE,
        frames=frames,
        vocal_phrase=phrases,
        generated_from_extra={
            "pair": list(model.PAIR),
            "model_id": str(data["model_id"]),
            "window_s": float(data["window_s"]),
            "hop_s": float(data["hop_s"]),
            # explicit, not a schema field — CLAUDE.md "no silent fallbacks":
            # a reader of this JSON must not infer boundary-F1 comparability
            # from the mere presence of vocal_phrase spans.
            "boundary_f1_scored": False,
            "boundary_f1_reason": (
                "a 5s CLAP analysis window cannot time a phrase edge to the "
                "0.25/0.5/1.0s tolerances voiceness_common.scorer uses; "
                "vocal_phrase spans are exported for the timeline and for "
                "boundary bookkeeping only"
            ),
        },
        interval_ms=int(round(float(data["hop_s"]) * 1000)),
    )
    return proposal.write(paths.proposal_path(song))


def export_all(songs: list[str]) -> None:
    for song in songs:
        export(song)
        print(f"exported {song}")
