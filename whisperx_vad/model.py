"""whisperX's VAD front-end (Max Bain et al., <https://github.com/m-bain/whisperX>,
<https://arxiv.org/abs/2303.00747>) — pinned `whisperx==3.8.6` — run over the
vocal stem only.

**VAD only. Diarization was not attempted** — gated `pyannote/speaker-
diarization-3.1` checkpoint, no live HF token in this environment, and
lead-plus-backing vocals are simultaneous rather than turn-taking, which
defeats the diarization premise regardless. See
`docs/archive/experiments_promoted.md` "WhisperX VAD" for the full record.

**Checkpoint.** whisperX ships its own VAD segmentation checkpoint
(`pyannote/segmentation`-shaped, distinct from the gated
`pyannote/speaker-diarization-3.1` diarization checkpoint) bundled directly
inside the `whisperx` PyPI package at `whisperx/assets/pytorch_model.bin`. It
is **not** a gated Hugging Face download and needs no token, ever —
`whisperx.vads.pyannote.load_vad_model()`'s default `model_fp` is that
bundled local file path, loaded via
`pyannote.audio.Model.from_pretrained(local_path, token=None)`, which never
touches the network for a local path.

This module pins the checkpoint explicitly and independently: the file was
downloaded from the `v3.8.6` git tag
(<https://raw.githubusercontent.com/m-bain/whisperX/v3.8.6/whisperx/assets/pytorch_model.bin>)
on the HOST, sha256-verified there
(`0b5b3216d60a2d32fc086b47ea8c67589aaeb26b7e07fcbe620d6d0b83e209ea`,
17,719,103 bytes), and `Dockerfile` `COPY`s that pre-fetched, host-verified
file into the image rather than curling it during the build. **No download
of any kind happens at image build time or at analysis time.**

**Method.** `whisperx.vads.pyannote.Pyannote` wraps a `pyannote.audio`
`VoiceActivityDetection`-family pipeline (`VoiceActivitySegmentation`) around
the checkpoint. Its raw per-frame activation (`SlidingWindowFeature`, one
score per ~17ms frame at the segmentation model's native rate) is what this
module reports as the continuous `voiceness` curve. `vocal_phrase` spans are
then derived by whisperX's own `Binarize` hysteresis binarizer at its
**library default** thresholds (`vad_onset=0.500`, `vad_offset=0.363`,
`min_duration_on=0.1s`, `min_duration_off=0.1s` — never swept; sweeping
degrades boundary F1 monotonically, per the promotion record).

This module deliberately does **not** call whisperX's `merge_chunks` (the
outer ~30s regrouping `whisperx.asr.FasterWhisperPipeline.transcribe`
performs to build ASR feeding windows) — that step exists only to batch
audio for the Whisper decoder, which this module never runs. Using
`Binarize`'s own hysteresis output directly gives the actual VAD phrase
boundaries at their real onset/offset resolution.

**Frame grid.** Resampled onto a 50ms grid — VAD's own segmentation frames
are already sub-second (~17ms native), so 50ms loses essentially nothing and
keeps `vocal_phrase` boundaries genuinely scoreable, not a clip-window
approximation.

Runs in the `whisperx` Compose service (its own image — `whisperx_vad/
Dockerfile`, `torch~=2.8.0`, incompatible with the `app` image's pinned
`torch==2.1.2`).
"""
from __future__ import annotations

import numpy as np

SR = 16_000  # whisperx.audio.SAMPLE_RATE — the VAD model's own input rate
FRAME_INTERVAL_S = 0.05  # shared 50ms grid, see module docstring

VAD_ONSET = 0.500
VAD_OFFSET = 0.363
MIN_DURATION_ON = 0.1
MIN_DURATION_OFF = 0.1

CHECKPOINT_PATH = "/models/whisperx_vad/pytorch_model.bin"
CHECKPOINT_SHA256 = "0b5b3216d60a2d32fc086b47ea8c67589aaeb26b7e07fcbe620d6d0b83e209ea"


def load_vad(device: str = "cpu"):
    import torch
    from whisperx.vads.pyannote import Pyannote

    return Pyannote(
        torch.device(device),
        token=None,
        model_fp=CHECKPOINT_PATH,
        vad_onset=VAD_ONSET,
        vad_offset=VAD_OFFSET,
    )


def _load_audio(path) -> np.ndarray:
    from whisperx.audio import load_audio

    if not path.exists():
        raise FileNotFoundError(f"expected vocal stem at {path}")
    return load_audio(str(path))  # float32, mono, 16kHz — whisperx's own ffmpeg-backed loader


def _raw_scores(vad_model, wave: np.ndarray):
    """`(times, activation)` at the segmentation model's own native frame
    rate — the un-binarized per-frame probability, before any hysteresis."""
    from whisperx.vads.pyannote import Pyannote

    waveform = Pyannote.preprocess_audio(wave)
    scores = vad_model({"waveform": waveform, "sample_rate": SR})
    num_frames = scores.data.shape[0]
    frames = scores.sliding_window
    times = np.array([frames[i].middle for i in range(num_frames)], dtype=np.float32)
    # class-agnostic "is anyone audible" reading — max over whatever classes
    # the checkpoint's output head carries (a plain single-class VAD
    # checkpoint has exactly one).
    activation = np.max(np.asarray(scores.data), axis=1).astype(np.float32)
    return times, activation, scores


def _binarized_spans(scores) -> list[tuple[float, float]]:
    from whisperx.vads.pyannote import Binarize

    binarize = Binarize(
        onset=VAD_ONSET,
        offset=VAD_OFFSET,
        min_duration_on=MIN_DURATION_ON,
        min_duration_off=MIN_DURATION_OFF,
    )
    annotation = binarize(scores)
    return sorted((seg.start, seg.end) for seg in annotation.get_timeline())


def _resample_to_grid(times: np.ndarray, activation: np.ndarray, duration_s: float) -> tuple[np.ndarray, np.ndarray]:
    if len(times) == 0:
        return np.zeros(0, dtype=np.float32), np.zeros(0, dtype=np.float32)
    grid = np.arange(0.0, max(duration_s, times[-1]), FRAME_INTERVAL_S, dtype=np.float32)
    resampled = np.interp(grid, times, activation).astype(np.float32)
    return grid, resampled


def compute(vocals_stem_path, *, device: str = "cpu", vad_model=None) -> dict:
    """Runs the VAD front-end over one song's vocal stem. Deterministic:
    same stem + same pinned checkpoint + same device class ⇒ byte-identical
    `times`/`voiceness`/phrase spans (no randomness anywhere in this path)."""
    vad_model = vad_model or load_vad(device)
    wave = _load_audio(vocals_stem_path)
    duration_s = len(wave) / SR

    native_times, native_activation, scores = _raw_scores(vad_model, wave)
    grid_times, grid_activation = _resample_to_grid(native_times, native_activation, duration_s)
    spans = _binarized_spans(scores)

    return {
        "times": grid_times,
        "voiceness": grid_activation,
        "phrase_starts": np.array([s for s, _ in spans], dtype=np.float32),
        "phrase_ends": np.array([e for _, e in spans], dtype=np.float32),
        "duration_s": float(duration_s),
        "checkpoint_sha256": CHECKPOINT_SHA256,
        "vad_onset": VAD_ONSET,
        "vad_offset": VAD_OFFSET,
    }


def vocal_phrases(data: dict) -> list[dict]:
    """The `Binarize`d spans as `{start, end, confidence}` dicts.
    `confidence` is the mean raw activation over the span — an honest
    average of the same curve `voiceness` reports, not a separate guess."""
    times = data["times"]
    voiceness = data["voiceness"]
    out = []
    for s, e in zip(data["phrase_starts"], data["phrase_ends"]):
        mask = (times >= s) & (times <= e)
        conf = float(np.mean(voiceness[mask])) if mask.any() else None
        out.append({"start": round(float(s), 3), "end": round(float(e), 3), "confidence": None if conf is None else round(conf, 3)})
    return out
