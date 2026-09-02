"""MERT (m-a-p/MERT-v1-95M) frame embeddings, cached per song.

MERT is a self-supervised music audio encoder: 24 kHz in, 75 Hz frames out,
13 hidden layers of 768 dims. Different layers specialise (low layers acoustic,
middle layers musical), so every layer is kept at beat resolution and a
mid-layer mean is kept at 25 Hz for sub-beat work.

Why this model and not a hand-built feature: the existing detector's evidence
channels are all one-dimensional level statistics, so "the arrangement changed
character" is only expressible as "something got louder". A learned frame
representation makes texture change measurable directly.
"""
from __future__ import annotations

import numpy as np
import torch

from .common import cache_file, essentia_grid, load_audio

MODEL_ID = "m-a-p/MERT-v1-95M"
SR = 24000
FPS = 75.0
CHUNK_S = 20.0          # forward-pass window
OVERLAP_S = 2.0         # trimmed from each side of an interior chunk
MID_LAYERS = (4, 5, 6, 7, 8, 9)
COARSE_FPS = 25.0


def _load_model(device: str = "cuda"):
    from transformers import AutoModel

    model = AutoModel.from_pretrained(MODEL_ID, trust_remote_code=True)
    _restore_weight_norm(model)
    # fp32 on purpose: in fp16 the convolutional feature extractor overflows and
    # every hidden state comes back NaN on this GPU (checked on all 13 layers).
    return model.to(device).eval().float()


def _restore_weight_norm(model) -> None:
    """Re-attach the positional conv's weight-norm tensors.

    The checkpoint stores `encoder.pos_conv_embed.conv.weight_{g,v}` (the
    pre-torch-2.1 spelling). MERT ships its own modeling file through
    `trust_remote_code`, so it misses the rename transformers applies to
    in-library Wav2Vec2 checkpoints, and the parametrised weights come out
    *randomly initialised* with only a warning. Loading a music encoder with a
    random positional embedding silently degrades everything downstream, so it
    is repaired explicitly and asserted.
    """
    from huggingface_hub import hf_hub_download
    from huggingface_hub.utils import EntryNotFoundError

    conv = model.encoder.pos_conv_embed.conv
    if not hasattr(conv, "parametrizations"):
        return
    try:
        from safetensors.torch import load_file

        state = load_file(hf_hub_download(MODEL_ID, "model.safetensors"))
    except EntryNotFoundError:
        state = torch.load(hf_hub_download(MODEL_ID, "pytorch_model.bin"), map_location="cpu")
    g = state["encoder.pos_conv_embed.conv.weight_g"]
    v = state["encoder.pos_conv_embed.conv.weight_v"]
    with torch.no_grad():
        conv.parametrizations.weight.original0.copy_(g.to(conv.parametrizations.weight.original0.dtype))
        conv.parametrizations.weight.original1.copy_(v.to(conv.parametrizations.weight.original1.dtype))


def _forward(model, wave: np.ndarray, device: str) -> np.ndarray:
    """(n_layers, T, D) float32 at 75 Hz for the whole song, chunked."""
    chunk = int(CHUNK_S * SR)
    keep = int(OVERLAP_S * SR)
    hop = chunk - 2 * keep
    pieces: list[np.ndarray] = []
    pos = 0
    while pos < len(wave):
        start = max(0, pos - keep)
        stop = min(len(wave), pos + hop + keep)
        seg = wave[start:stop]
        if len(seg) < SR // 2:
            break
        with torch.no_grad():
            x = torch.from_numpy(seg)[None].to(device).float()
            out = model(x, output_hidden_states=True)
        hs = torch.stack(out.hidden_states)[:, 0].float().cpu().numpy()   # (L, t, D)
        lo = int(round((pos - start) / SR * FPS))
        hi = lo + int(round(min(hop, len(wave) - pos) / SR * FPS))
        pieces.append(hs[:, lo:hi])
        pos += hop
    return np.concatenate(pieces, axis=1)


def _beat_sync(emb: np.ndarray, times: np.ndarray, beats: np.ndarray) -> np.ndarray:
    """Median-pool frames inside each beat interval -> (L, n_beats, D)."""
    edges = np.concatenate([beats, [beats[-1] + np.median(np.diff(beats))]])
    n_frames = emb.shape[1]
    # Beats can run past the last frame (the essentia grid is extrapolated to
    # the tail); clamping keeps the pool non-empty instead of emitting NaN.
    idx = np.clip(np.searchsorted(times, edges), 0, n_frames - 1)
    out = np.zeros((emb.shape[0], len(beats), emb.shape[2]), dtype=np.float32)
    for i in range(len(beats)):
        lo = idx[i]
        hi = max(lo + 1, min(idx[i + 1], n_frames))
        out[:, i] = np.median(emb[:, lo:hi], axis=1)
    return out


def compute(song: str, *, device: str = "cuda", model=None) -> dict[str, np.ndarray]:
    wave = load_audio(song, SR)
    model = model or _load_model(device)
    emb = _forward(model, wave, device)
    times = np.arange(emb.shape[1]) / FPS

    grid = essentia_grid(song)
    beat_emb = _beat_sync(emb, times, grid.beats)

    factor = int(round(FPS / COARSE_FPS))
    trim = (emb.shape[1] // factor) * factor
    coarse = emb[MID_LAYERS, :trim].mean(axis=0).reshape(-1, factor, emb.shape[2]).mean(axis=1)

    return {
        "beat_emb": beat_emb.astype(np.float16),
        "beats": grid.beats,
        "coarse_emb": coarse.astype(np.float16),
        "coarse_times": (np.arange(coarse.shape[0]) + 0.5) / COARSE_FPS,
    }


def load(song: str, *, rebuild: bool = False, model=None) -> dict[str, np.ndarray]:
    path = cache_file("mert", song)
    if rebuild or not path.exists():
        data = compute(song, model=model)
        np.savez_compressed(path, **data)
        return data
    return dict(np.load(path))
