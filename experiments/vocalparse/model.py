"""Run VocalParse and cache its raw output, one JSON per song.

VocalParse (<https://huggingface.co/pymaster/VocalParse>) is a Qwen3-ASR-1.7B
fine-tune for singing-voice transcription. It takes 16 kHz mono audio and emits
an interleaved token stream:

    感 <P_68> <NOTE_4> 受 <P_60> <NOTE_8> ... <BPM_89>

lyric tokens spliced with pitch (`<P_#>`, MIDI number), note value (`<NOTE_#>`,
log2 of a whole note) and one global tempo token at the end. It predicts **no
per-token timestamp**, and it is trained primarily on Mandarin Chinese singing.

This module owns exactly one job: get the model's raw string onto disk,
unmodified, plus a parse of it into structured syllables. Everything time-bearing
happens in `align.py`.

Runs in `ai-light-song-v2-vocalparse:dev`; see `run_in_container.sh`.

NOTE (unverified until first run): the exact `vocalparse` import surface and the
CoT flag are taken from the model card. Confirm `transcribe_one` /
`VocalParseTranscriber` signatures against the installed package and adjust here
only.
"""
from __future__ import annotations

import json
import os
import re

import numpy as np

from .paths import raw_cache_path, vocal_stem_path

CHECKPOINT = "pymaster/VocalParse"
SR = 16_000


def _checkpoint_dir() -> str:
    """VocalParse's `load_model` wants a local directory with `config.json`, not
    an HF repo id — so fetch the checkpoint to the repo-local cache first. The
    Qwen3-ASR-1.7B base model it also needs is resolved (and downloaded) by
    VocalParse itself from `config.json`'s hidden size."""
    import os

    from huggingface_hub import snapshot_download

    if os.path.isdir(CHECKPOINT):
        return CHECKPOINT
    return snapshot_download(CHECKPOINT)


def _resolve_device() -> str:
    want = os.environ.get("VOCALPARSE_DEVICE", "auto")
    if want != "auto":
        return want
    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:  # noqa: BLE001
        return "cpu"

_P = re.compile(r"<P_(\d+)>")
_NOTE = re.compile(r"<NOTE_(\d+)>")
_BPM = re.compile(r"<BPM_(\d+)>")


def _audio(song: str) -> np.ndarray:
    import librosa

    stem = vocal_stem_path(song)
    if not stem.exists():
        raise FileNotFoundError(f"{song}: no vocal stem at {stem} — run the pipeline first")
    wave, _ = librosa.load(str(stem), sr=SR, mono=True)
    return wave.astype(np.float32)


def parse(text: str) -> dict:
    """VocalParse output -> {language, lyrics, syllables, bpm, melody_status}.

    The model emits, in order:
      `language English<asr_text>WORDS<|file_sep|>SYL <P_#> <NOTE_#> SYL ... <BPM_#>`
    The `<asr_text>` span before `<|file_sep|>` is a plain lyric transcription
    (the CoT step); the interleaved span after it carries the melody. On this
    box (CPU, and a mostly out-of-distribution corpus) the melody span reliably
    collapses into a run of `<P_0>` and junk tokens, so lyrics are taken from
    the `<asr_text>` span and the melody is kept only when it looks sane.
    """
    language = None
    lang_match = re.match(r"\s*language\s+([A-Za-z ]+?)\s*(?:<|$)", text)
    if lang_match:
        language = lang_match.group(1).strip()

    asr_lyrics = ""
    m = re.search(r"<asr_text>(.*?)(?:<\|file_sep\|>|</asr_text>|$)", text, re.S)
    if m:
        asr_lyrics = re.sub(r"<[^>]+>", " ", m.group(1))
        asr_lyrics = re.sub(r"\s+", " ", asr_lyrics).strip()

    bpm_match = _BPM.search(text)
    bpm = int(bpm_match.group(1)) if bpm_match else None
    body = _BPM.sub("", text)
    if "<|file_sep|>" in body:
        body = body.split("<|file_sep|>", 1)[1]
    elif "<asr_text>" in body:
        body = body.split("<asr_text>", 1)[1]

    syllables: list[dict] = []
    pending_text = ""
    for tok in re.split(r"(<[^>]+>)", body):
        tok = tok.strip()
        if not tok:
            continue
        if tok.startswith("<P_"):
            syllables.append({"text": pending_text.strip(), "midi": int(_P.match(tok).group(1)),
                              "note_value": None})
            pending_text = ""
        elif tok.startswith("<NOTE_"):
            if syllables:
                syllables[-1]["note_value"] = int(_NOTE.match(tok).group(1))
        elif not tok.startswith("<"):
            pending_text += tok
    if pending_text.strip():
        syllables.append({"text": pending_text.strip(), "midi": None, "note_value": None})

    interleaved_lyrics = "".join(s["text"] for s in syllables).strip()
    pitches = [s["midi"] for s in syllables if s["midi"] is not None]
    zero_frac = pitches.count(0) / len(pitches) if pitches else 1.0
    distinct = len(set(pitches))
    melody_status = "ok"
    if not pitches:
        melody_status = "empty"
    elif zero_frac > 0.5 or distinct <= 2:
        melody_status = "degenerate"

    return {
        "language": language,
        "lyrics": asr_lyrics or interleaved_lyrics,
        "lyrics_source": "asr_text" if asr_lyrics else "interleaved",
        "interleaved_lyrics": interleaved_lyrics,
        "syllables": syllables if melody_status == "ok" else [],
        "melody_status": melody_status,
        "melody_zero_fraction": round(zero_frac, 3),
        "melody_distinct_pitches": distinct,
        "bpm": bpm,
    }


def compute(song: str, *, device: str | None = None) -> dict:
    # `transcribe_one` picks the device itself (cuda if visible, else cpu); this
    # box's 4 GB card can't hold it, so the container runs without `--gpus`.
    from vocalparse import transcribe_one

    device = device or _resolve_device()
    wave = _audio(song)
    raw = transcribe_one(
        audio=wave, checkpoint=_checkpoint_dir(), sr=SR,
        max_new_tokens=int(os.environ.get("VOCALPARSE_MAX_NEW_TOKENS", "768")),
        attn_implementation="sdpa",
    )
    lib_parsed = _library_parse(raw)
    parsed = parse(raw)
    if lib_parsed:
        parsed["library_parse"] = lib_parsed
    return {
        "model": CHECKPOINT,
        "device": device,
        "sr": SR,
        "raw": raw,
        **parsed,
    }


def _library_parse(text: str) -> dict | None:
    try:
        from vocalparse.evaluation import parse_transcription_text

        out = parse_transcription_text(text)
        return out if isinstance(out, dict) else {"result": out}
    except Exception:  # noqa: BLE001 — our own parser is the fallback
        return None


def load(song: str, *, rebuild: bool = False) -> dict:
    path = raw_cache_path(song)
    if rebuild or not path.exists():
        data = compute(song)
        path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
        return data
    return json.loads(path.read_text())


def cached_songs(songs: list[str]) -> list[str]:
    return [s for s in songs if raw_cache_path(s).exists()]
