"""Write PANNs' `Singing` head, run on both channels, to
`reference/proposals/svd_tagger.json` via `voiceness_common.schema` — the
shared shape every voiceness candidate (items 4-7) writes.

**Both channels land in ONE proposal file, tagged per row.** The stem and
the mix are genuinely different producers of the same "is someone singing
right now" signal (see `paths.py::mix_audio_path` and the pinned-memory rule
this repo runs on: "published files are fused from many producers, and say
which one won") — so every `VoicenessFrame`/`VocalPhrase` this module writes
carries `channel: "stem" | "mix"`, not a silent pick of one. The file-level
`generated_from.channels` list documents which channels exist at all; the
per-row `channel` field is the per-row attribution.
"""
from __future__ import annotations

from experiments.voiceness_common.schema import (
    VocalPhrase,
    VoicenessFrame,
    VoicenessProposal,
)

from . import model, paths

EXPERIMENT = "experiments/svd_tagger"
ENGINE = (
    'svd_tagger.model (PANNs Cnn14, AudioSet-527 "Singing" class index 27, '
    "5s window / 1s hop clip-level inference, run on both the vocal stem "
    "and the mix)"
)


def _channel_confidence(voiceness: float) -> float:
    """Same decision-margin heuristic `vocal_voiceness`/`clap_voiceness` use
    — an honest heuristic, not a calibrated probability."""
    return max(0.0, min(1.0, abs(voiceness - 0.5) * 2.0))


def export(song: str) -> dict:
    data = model.load(song)

    frames: list[VoicenessFrame] = []
    phrases: list[VocalPhrase] = []
    for channel, times_key, voiceness_key in (
        ("stem", "stem_times", "stem_voiceness"),
        ("mix", "mix_times", "mix_voiceness"),
    ):
        times = data[times_key]
        voiceness = data[voiceness_key]
        for t, v in zip(times, voiceness):
            frames.append(
                VoicenessFrame(
                    time_s=float(t),
                    voiceness=float(v),
                    confidence=_channel_confidence(float(v)),
                    channel=channel,
                )
            )
        for p in model.derive_vocal_phrases(times, voiceness):
            phrases.append(
                VocalPhrase(start=p["start"], end=p["end"], confidence=p["confidence"], channel=channel)
            )

    frames.sort(key=lambda f: (f.time_s, f.channel or ""))
    phrases.sort(key=lambda p: (p.start, p.channel or ""))

    proposal = VoicenessProposal(
        song_name=song,
        experiment=EXPERIMENT,
        engine=ENGINE,
        frames=frames,
        vocal_phrase=phrases,
        generated_from_extra={
            "channels": ["stem", "mix"],
            "class_label": "Singing",
            "class_index": int(data["class_index"]),
            "checkpoint": str(data["checkpoint"]),
            "window_s": float(data["window_s"]),
            "hop_s": float(data["hop_s"]),
            # explicit, not a schema field — CLAUDE.md "no silent fallbacks":
            # a reader must not infer boundary-F1 comparability from the
            # mere presence of vocal_phrase spans.
            "boundary_f1_scored": False,
            "boundary_f1_reason": (
                "a 5s PANNs analysis window cannot time a phrase edge to the "
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
