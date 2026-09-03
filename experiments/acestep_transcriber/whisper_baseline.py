"""The cheap baseline every lyric claim has to beat: Whisper on the vocal stem.

LyricWhiz (2306.17103) is built on the observation that Whisper is a strong
"ear" for sung lyrics once the prompt nudges it toward transcription rather than
music description, and once it is fed voice rather than a full mix. We already
have the isolated vocal stem, so the baseline is small: `whisper-large-v3` with
`word_timestamps=True` over `artifacts/stems/vocals.wav`.

This is also where the *timing* in this experiment comes from — VocalParse and
ACE-Step do not emit reliable per-word seconds, so both align their text onto
this word timeline (see `align.py`).

Device / precision resolve from the environment so the same code runs on a
4 GB card (`int8`) or CPU:

    WHISPER_DEVICE=cuda|cpu|auto   (default auto)
    WHISPER_COMPUTE=int8|int8_float16|float16   (default int8_float16 on cuda, int8 on cpu)

Runs in `ai-light-song-v2-acestep:dev`.
"""
from __future__ import annotations

import json
import os

from .paths import vocal_stem_path, whisper_cache_path

MODEL_ID = "large-v3"
#: LyricWhiz's prefix trick — steer Whisper to lyrics, not "[music playing]".
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


def compute(song: str) -> dict:
    from faster_whisper import WhisperModel

    stem = vocal_stem_path(song)
    if not stem.exists():
        raise FileNotFoundError(f"{song}: no vocal stem at {stem} — run the pipeline first")

    device, compute_type = _resolve_device()
    model = WhisperModel(MODEL_ID, device=device, compute_type=compute_type)
    segments, info = model.transcribe(
        str(stem),
        word_timestamps=True,
        initial_prompt=PROMPT,
        vad_filter=os.environ.get("WHISPER_VAD", "0") == "1",
        condition_on_previous_text=False,
        beam_size=5,
    )

    lines = []
    for seg in segments:
        words = [
            {"t": round(w.start, 3), "d": round(w.end - w.start, 3),
             "w": w.word.strip(), "p": round(w.probability, 3)}
            for w in (seg.words or [])
        ]
        lines.append({
            "id": f"w{len(lines) + 1:03d}",
            "start_s": round(seg.start, 3),
            "end_s": round(seg.end, 3),
            "text": seg.text.strip(),
            "words": words,
            "confidence": round(seg.avg_logprob, 3),
        })

    return {
        "model": f"whisper-{MODEL_ID} (baseline, vocal stem)",
        "kind": "baseline",
        "device": device,
        "compute_type": compute_type,
        "language": info.language,
        "language_confidence": round(info.language_probability, 3),
        "word_timestamps": True,
        "lines": lines,
    }


def load(song: str, *, rebuild: bool = False) -> dict:
    path = whisper_cache_path(song)
    if rebuild or not path.exists():
        data = compute(song)
        path.write_text(json.dumps(data, indent=1) + "\n")
        return data
    return json.loads(path.read_text())


def cached_songs(songs: list[str]) -> list[str]:
    return [s for s in songs if whisper_cache_path(s).exists()]
