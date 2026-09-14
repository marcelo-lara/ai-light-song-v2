"""Write the combined voiceness score + bridged vocal-phrase blocks to
`reference/proposals/vocal_voiceness.json` via `voiceness_common.schema` — the
shared shape every voiceness candidate (items 4-7) writes, so they land on one
comparable timeline and score through one scorer.
"""
from __future__ import annotations

from experiments.voiceness_common.schema import (
    VocalPhrase,
    VoicenessFrame,
    VoicenessProposal,
)

from . import features, model, paths

EXPERIMENT = "experiments/vocal_voiceness"
ENGINE = (
    "vocal_voiceness.model (noisy-OR of vibrato/portamento/sibilance cues; "
    "vocal_phrases hysteresis + pitch-continuity sustained-note bridge)"
)


def export(song: str) -> dict:
    feat = features.load_features(song)
    voiceness, confidence = model.combine_voiceness(feat)
    derived = model.derive_vocal_phrases(song)

    frames = [
        VoicenessFrame(time_s=t, voiceness=v, confidence=c)
        for t, v, c in zip(feat.times, voiceness, confidence)
    ]
    phrases = [
        VocalPhrase(start=p["start"], end=p["end"], confidence=p["confidence"])
        for p in derived["vocal_phrases"]
    ]

    proposal = VoicenessProposal(
        song_name=song,
        experiment=EXPERIMENT,
        engine=ENGINE,
        frames=frames,
        vocal_phrase=phrases,
        generated_from_extra={
            "source_stem": str(paths.vocals_stem_path(song)),
            "source_fft_bands": str(paths.fft_bands_vocals_path(song)),
            "cue_weights": {
                "vibrato": model.WEIGHT_VIBRATO,
                "portamento": model.WEIGHT_PORTAMENTO,
                "sibilance": model.WEIGHT_SIBILANCE,
            },
            "params": derived["params"],
            "n_sustained_notes": len(derived["sustained_notes"]),
            "sustained_notes": derived["sustained_notes"],
            "n_bridged_gaps": len(derived["bridge_events"]),
            "bridge_events": derived["bridge_events"],
        },
        interval_ms=50,
    )
    return proposal.write(paths.proposal_path(song))


def export_all(songs: list[str]) -> None:
    for song in songs:
        export(song)
        print(f"exported {song}")
