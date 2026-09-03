"""Compute and cache CLAP audio embeddings on a sliding window, per song.

CLAP (LAION, <https://github.com/LAION-AI/CLAP>) embeds audio and free text into
one 512-dimensional space. The sibling drop survey used the *text* side of that
and mostly found what CLAP cannot be asked
(`../drop_detection/README.md` "Measurement 5"). This experiment uses the
**audio side only** — the embedding as a representation, which is what the
"512-dimensional audio vectors for similarity search" framing is about — and
never scores a sentence.

Only the audio tower is expensive, and this module is the only thing that runs
it. Everything derived from the embeddings lives in `features.py`, so a change
of method never costs another GPU pass.

Runs in the `ai-light-song-v2-research:dev` sandbox; see `run_in_container.sh`.
"""
from __future__ import annotations

import numpy as np

from .paths import audio_path, cache_path

MODEL_ID = "laion/larger_clap_music"
SR = 48_000

#: 5 s at a 1 s hop. The survey ran 10 s windows, which is fine for a curve but
#: smears a section boundary by five seconds in each direction — half the window
#: of any pooled section shorter than 20 s is contaminated by its neighbours.
#: 5 s is the shortest window that still gives CLAP a musical phrase to look at.
WINDOW_S = 5.0
HOP_S = 1.0

BATCH = 8


def _load(device: str = "cuda"):
    import torch
    from transformers import ClapModel, ClapProcessor

    model = ClapModel.from_pretrained(MODEL_ID).to(device).eval()
    processor = ClapProcessor.from_pretrained(MODEL_ID)
    return model, processor, torch


def _audio(song: str) -> np.ndarray:
    import librosa

    wave, _ = librosa.load(str(audio_path(song)), sr=SR, mono=True)
    return wave.astype(np.float32)


def compute(song: str, *, device: str = "cuda", bundle=None,
            window_s: float = WINDOW_S, hop_s: float = HOP_S) -> dict:
    model, processor, torch = bundle or _load(device)
    wave = _audio(song)

    win = int(window_s * SR)
    hop = int(hop_s * SR)
    starts = np.arange(0, max(1, len(wave) - win + hop), hop)
    # Each embedding is labelled with the centre of the window it saw, so a
    # caller can guard by window_s/2 and know exactly what is inside.
    centres = starts / SR + window_s / 2.0

    chunks = []
    with torch.no_grad():
        for i in range(0, len(starts), BATCH):
            batch = []
            for s in starts[i:i + BATCH]:
                seg = wave[s:s + win]
                if len(seg) < win:
                    seg = np.pad(seg, (0, win - len(seg)))
                batch.append(seg)
            inputs = processor(audios=batch, sampling_rate=SR, return_tensors="pt").to(model.device)
            emb = model.get_audio_features(**inputs)
            chunks.append(torch.nn.functional.normalize(emb, dim=-1).cpu())
    emb = torch.cat(chunks).numpy().astype(np.float16)

    return {
        "times": centres.astype(np.float32),
        "emb": emb,
        "window_s": np.array(window_s, dtype=np.float32),
        "hop_s": np.array(hop_s, dtype=np.float32),
        "model_id": np.array(MODEL_ID),
        "duration_s": np.array(len(wave) / SR, dtype=np.float32),
    }


def load(song: str, *, rebuild: bool = False, bundle=None) -> dict:
    """Cached `compute`. Reading a cache needs neither a GPU nor transformers."""
    path = cache_path(song)
    if rebuild or not path.exists():
        data = compute(song, bundle=bundle)
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(path, **data)
        return data
    return dict(np.load(path, allow_pickle=False))


def cached_songs(songs: list[str]) -> list[str]:
    return [song for song in songs if cache_path(song).exists()]


def unit(emb: np.ndarray) -> np.ndarray:
    """float16 cache -> L2-normalised float32, the only form anything should use."""
    out = emb.astype(np.float32)
    return out / (np.linalg.norm(out, axis=-1, keepdims=True) + 1e-8)
