"""Writes `data/analysis/{song}/artifacts/whisperx-vad/whisperx_vad.json` —
the per-50ms-frame `voiceness` curve plus `Binarize`d `vocal_phrase` spans
`model.compute` produces.

Promoted shape: the same fields the pre-promotion
`reference/proposals/whisperx_vad.json` carried, minus `generated_from.
generated_at` and `generated_from.experiment` — this is now a pipeline
artifact, not a research proposal, and determinism (CLAUDE.md) forbids a
wall-clock timestamp in a generated file. `generated_from`'s shape otherwise
follows the convention other `artifacts/<producer>/*.json` files use (see
`src/analyzer/stages/drums.py`'s `drum_events.json`): `source_song_path`,
`engine`, `dependencies`.
"""
from __future__ import annotations

from analyzer.io import write_json
from analyzer.models import SCHEMA_VERSION
from analyzer.paths import SongPaths

from . import model, paths

ENGINE = (
    "whisperx_vad.model (whisperX 3.8.6's Pyannote VAD front-end, bundled "
    "segmentation checkpoint, hysteresis-binarized at library-default "
    "onset=0.500/offset=0.363, resampled onto a 50ms grid)"
)


def export(song_paths: SongPaths, *, device: str = "cpu", vad_model=None) -> dict:
    vocals_stem = paths.vocals_stem_path(song_paths)
    data = model.compute(vocals_stem, device=device, vad_model=vad_model)

    times = data["times"]
    voiceness = data["voiceness"]
    frames = [
        {"time": round(float(t), 3), "voiceness": round(float(v), 4), "confidence": None}
        for t, v in zip(times, voiceness)
    ]
    vocal_phrase = model.vocal_phrases(data)

    payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": song_paths.song_name,
        "generated_from": {
            "source_song_path": str(song_paths.song_path),
            "engine": ENGINE,
            "dependencies": {
                "vocals_stem": str(vocals_stem),
                "checkpoint": "whisperx VAD segmentation (pytorch_model.bin)",
                "checkpoint_sha256": data["checkpoint_sha256"],
            },
            "vad_onset": data["vad_onset"],
            "vad_offset": data["vad_offset"],
            "diarization_attempted": False,
            "diarization_reason": (
                "pyannote/speaker-diarization-3.1 is a gated Hugging Face "
                "checkpoint requiring a live HF_TOKEN; no token is available "
                "in this environment, and lead-plus-backing vocals are "
                "simultaneous rather than turn-taking, which defeats the "
                "diarization premise regardless"
            ),
        },
        "metadata": {
            "interval_ms": int(round(model.FRAME_INTERVAL_S * 1000)),
            "total_frames": len(frames),
        },
        "frames": frames,
        "vocal_phrase": vocal_phrase,
    }

    out_path = paths.output_path(song_paths)
    write_json(out_path, payload)
    return payload
