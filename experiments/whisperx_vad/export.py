"""Write whisperX's VAD front-end's continuous activation curve and
`Binarize`d phrase spans to `reference/proposals/whisperx_vad.json` via
`voiceness_common.schema` — the shared shape every voiceness candidate
(items 4-7) writes.

Single producer, single channel (the vocal stem only) — same shape as
`vocal_voiceness` (item 4) and `clap_voiceness` (item 5); unlike `svd_tagger`
(item 6) there is no `channel` axis to fuse, since diarization (the only
other producer this item could have added) was not attempted — see
`README.md`.
"""
from __future__ import annotations

from experiments.voiceness_common.schema import (
    VocalPhrase,
    VoicenessFrame,
    VoicenessProposal,
)

from . import model, paths

EXPERIMENT = "experiments/whisperx_vad"
ENGINE = (
    "whisperx_vad.model (whisperX 3.8.6's Pyannote VAD front-end, bundled "
    "segmentation checkpoint, hysteresis-binarized at library-default "
    "onset=0.500/offset=0.363, resampled onto the shared 50ms grid)"
)


def export(song: str) -> dict:
    data = model.load(song)

    times = data["times"]
    voiceness = data["voiceness"]
    frames = [
        VoicenessFrame(time_s=float(t), voiceness=float(v), confidence=None)
        for t, v in zip(times, voiceness)
    ]
    phrases = [
        VocalPhrase(start=p["start"], end=p["end"], confidence=p["confidence"])
        for p in model.vocal_phrases(data)
    ]

    proposal = VoicenessProposal(
        song_name=song,
        experiment=EXPERIMENT,
        engine=ENGINE,
        frames=frames,
        vocal_phrase=phrases,
        generated_from_extra={
            "checkpoint": "whisperx VAD segmentation (pytorch_model.bin)",
            "checkpoint_sha256": str(data["checkpoint_sha256"]),
            "vad_onset": float(data["vad_onset"]),
            "vad_offset": float(data["vad_offset"]),
            "diarization_attempted": False,
            "diarization_reason": (
                "pyannote/speaker-diarization-3.1 is a gated Hugging Face "
                "checkpoint requiring a live HF_TOKEN; no token is available "
                "in this environment, and CLAUDE.md/the item's own kill "
                "condition rule out anything that needs a live token at "
                "analysis time regardless of score, so diarization was not "
                "attempted rather than built and disqualified after the "
                "fact"
            ),
        },
        interval_ms=int(round(model.FRAME_INTERVAL_S * 1000)),
    )
    return proposal.write(paths.proposal_path(song))


def export_all(songs: list[str]) -> None:
    for song in songs:
        export(song)
        print(f"exported {song}")
