"""Word-onset transcription over the vocal stem — the second output of the
`whisperx` Compose service (v3.6 item 10, D10.1).

This is **not** whisperX's own ASR path (still unused — see `model.py`'s
docstring on why this module stays VAD-only for phrase detection). It reuses
the exact method `experiments/rhythm_vocal_onsets` validated in the ACE-Step
sandbox (`experiments/acestep_transcriber/whisper_baseline.py`):
`faster_whisper`'s `large-v3` model, `word_timestamps=True`, over
`artifacts/stems/vocals.wav`. Word `start` timestamps are syllable-onset
proxies — `section_clues.py` (phase 3) turns them into a dominant
inter-onset-interval ratio against the beat grid, the same subdivision
vocabulary `rhythm_drum_ioi` uses.

Promoted into this service (rather than staying in the ACE-Step sandbox)
because `whisperx==3.8.6` already pulls `faster-whisper`/`ctranslate2` as a
transitive dependency (see `Dockerfile`) — no new image, no new pip install.

**Offline, no download.** `large-v3`'s weights are pre-fetched and cached on
the host at `models/hf/hub/models--Systran--faster-whisper-large-v3` (the
same cache `acestep_transcriber`'s `run_in_container.sh` points `HF_HOME` at).
`docker-compose.yml`'s `whisperx` service sets `HF_HOME=/app/models/hf` (the
repo root is bind-mounted at `/app`, so the pre-fetched cache is visible
without copying it into the image) alongside the Dockerfile's own
`HF_HUB_OFFLINE=1` — offline mode plus a populated cache means this never
touches the network.

Determinism: `faster_whisper` with a fixed `beam_size` and
`condition_on_previous_text=False` on a fixed input is deterministic (no
sampling) — same stem + same pinned model ⇒ byte-identical word timestamps.
"""
from __future__ import annotations

import os

MODEL_ID = "large-v3"
#: LyricWhiz's prefix trick (experiments/acestep_transcriber/whisper_baseline.py)
#: — steers Whisper toward transcription rather than "[music playing]".
PROMPT = "lyrics:"


def _resolve_device() -> tuple[str, str]:
    want = os.environ.get("WHISPER_DEVICE", "auto")
    if want == "auto":
        try:
            import torch

            want = "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:  # noqa: BLE001
            want = "cpu"
    compute = os.environ.get(
        "WHISPER_COMPUTE", "int8_float16" if want == "cuda" else "int8"
    )
    return want, compute


def compute(vocals_stem_path) -> dict:
    """Runs `faster_whisper` over one song's vocal stem. Returns word onsets
    as `{"time": t, "confidence": word_probability}`, sorted by time. No
    silent fallback: raises if the stem is missing."""
    from faster_whisper import WhisperModel

    if not vocals_stem_path.exists():
        raise FileNotFoundError(f"expected vocal stem at {vocals_stem_path}")

    device, compute_type = _resolve_device()
    model = WhisperModel(MODEL_ID, device=device, compute_type=compute_type)
    segments, info = model.transcribe(
        str(vocals_stem_path),
        word_timestamps=True,
        initial_prompt=PROMPT,
        vad_filter=False,
        condition_on_previous_text=False,
        beam_size=5,
    )

    words: list[dict] = []
    for seg in segments:
        for w in seg.words or []:
            words.append({
                "time": round(w.start, 3),
                "word": w.word.strip(),
                "confidence": round(w.probability, 3),
            })
    words.sort(key=lambda w: w["time"])

    return {
        "model": f"whisper-{MODEL_ID}",
        "device": device,
        "compute_type": compute_type,
        "language": info.language,
        "language_confidence": round(info.language_probability, 3),
        "words": words,
    }
