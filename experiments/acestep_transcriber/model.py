"""Run ACE-Step Transcriber and cache its raw output, one JSON per song.

ACE-Step Transcriber (<https://huggingface.co/ACE-Step/acestep-transcriber>) is
a Qwen2.5-Omni fine-tune the ACE-Step team built as their own training-data
annotator. `config.json` is `Qwen2_5OmniForConditionalGeneration`; `args.json`
shows a GRPO fine-tune on ~4M audio-lyric pairs with a `qwen2_5_omni` chat
template, a 16 384-token context and a 512-token response cap.

For transcription only the **thinker** is needed, so this module disables the
talker and asks for text (no audio synthesis). Input: an audio file + the
prompt `"Transcribe this audio in detail"`. Output: structured text —

    # Languages
    en

    # Lyrics
    [Intro - Acoustic Guitar]
    [Verse 1]
    <line>
    [Chorus]
    ...

We feed it the **mix**, not the vocal stem — it is trained on full songs and
uses the backing track for the structure tags.

Device / precision resolve from the environment (this repo's dev box is a 4 GB
card, so the 7B-class thinker runs on CPU in fp16):

    ACESTEP_DEVICE=cuda|cpu|auto   (default auto)
    ACESTEP_DTYPE=bfloat16|float16 (default bfloat16 — CPU matmul support)
    ACESTEP_MAX_NEW_TOKENS=512

Runs in `ai-light-song-v2-acestep:dev`; see `run_in_container.sh`.
"""
from __future__ import annotations

import json
import os
import re

from .paths import audio_path, raw_cache_path

MODEL_ID = "ACE-Step/acestep-transcriber"
PROMPT = "Transcribe this audio in detail"

_TAG = re.compile(r"^\[(?P<tag>[^\]]+)\]\s*$")


def _resolve() -> tuple[str, str, int]:
    want = os.environ.get("ACESTEP_DEVICE", "auto")
    if want == "auto":
        try:
            import torch

            want = "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:  # noqa: BLE001
            want = "cpu"
    dtype = os.environ.get("ACESTEP_DTYPE", "bfloat16")
    max_new = int(os.environ.get("ACESTEP_MAX_NEW_TOKENS", "512"))
    return want, dtype, max_new


def parse(text: str) -> dict:
    """Structured ACE-Step output -> {languages, sections}."""
    languages: list[str] = []
    sections: list[dict] = []
    mode = None
    cur = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        low = line.lower()
        if low.startswith("# language"):
            mode = "lang"
            continue
        if low.startswith("# lyric"):
            mode = "lyrics"
            continue
        if mode == "lang":
            languages.extend(p.strip() for p in re.split(r"[,\s]+", line) if p.strip())
            continue
        m = _TAG.match(line)
        if m:
            inner = m.group("tag")
            tag, _, instr = inner.partition(" - ")
            cur = {"tag": tag.strip(), "instruments": instr.strip() or None, "lines": []}
            sections.append(cur)
            continue
        if cur is None:
            cur = {"tag": "unknown", "instruments": None, "lines": []}
            sections.append(cur)
        cur["lines"].append(line)
    return {"languages": languages, "sections": sections}


def _load_model(device: str, dtype: str):
    """Thinker only if the class can peel it off the omni checkpoint; else the
    full model with the talker + vocoder disabled straight after load."""
    import torch
    from transformers import Qwen2_5OmniProcessor

    torch_dtype = getattr(torch, dtype)
    kw = dict(torch_dtype=torch_dtype, low_cpu_mem_usage=True,
              device_map=device if device == "cuda" else None)

    model = None
    try:
        from transformers import Qwen2_5OmniThinkerForConditionalGeneration

        model = Qwen2_5OmniThinkerForConditionalGeneration.from_pretrained(MODEL_ID, **kw)
        print("  loaded thinker-only", flush=True)
    except Exception as exc:  # noqa: BLE001
        print(f"  thinker-only load failed ({type(exc).__name__}); loading full omni", flush=True)

    if model is None:
        from transformers import Qwen2_5OmniForConditionalGeneration

        model = Qwen2_5OmniForConditionalGeneration.from_pretrained(MODEL_ID, **kw)
        if hasattr(model, "disable_talker"):
            model.disable_talker()

    if device != "cuda":
        model = model.to(device)
    model.eval()
    processor = Qwen2_5OmniProcessor.from_pretrained(MODEL_ID)
    thinker_only = model.__class__.__name__.startswith("Qwen2_5OmniThinker")
    return model, processor, thinker_only


def compute(song: str) -> dict:
    import torch
    from qwen_omni_utils import process_mm_info

    device, dtype, max_new = _resolve()
    model, processor, thinker_only = _load_model(device, dtype)

    conversation = [
        {"role": "system", "content": [{"type": "text", "text": "You are a helpful assistant."}]},
        {"role": "user", "content": [
            {"type": "audio", "audio": str(audio_path(song))},
            {"type": "text", "text": PROMPT},
        ]},
    ]
    prompt_text = processor.apply_chat_template(
        conversation, add_generation_prompt=True, tokenize=False,
    )
    audios, images, videos = process_mm_info(conversation, use_audio_in_video=False)
    inputs = processor(
        text=prompt_text, audio=audios, images=images, videos=videos,
        return_tensors="pt", padding=True, use_audio_in_video=False,
    ).to(model.device).to(model.dtype if hasattr(model, "dtype") else None)

    gen_kw = dict(max_new_tokens=max_new, do_sample=False)
    # The full omni model needs return_audio=False to skip the talker; the
    # thinker-only class rejects that kwarg.
    if not thinker_only:
        gen_kw["return_audio"] = False
        gen_kw["use_audio_in_video"] = False
    with torch.no_grad():
        out = model.generate(**inputs, **gen_kw)
    raw = processor.batch_decode(
        out[:, inputs["input_ids"].shape[1]:],
        skip_special_tokens=True, clean_up_tokenization_spaces=False,
    )[0].strip()

    return {"model": MODEL_ID, "device": device, "dtype": dtype,
            "prompt": PROMPT, "raw": raw, **parse(raw)}


def load(song: str, *, rebuild: bool = False) -> dict:
    path = raw_cache_path(song)
    if rebuild or not path.exists():
        data = compute(song)
        path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
        return data
    return json.loads(path.read_text())


def cached_songs(songs: list[str]) -> list[str]:
    return [s for s in songs if raw_cache_path(s).exists()]
