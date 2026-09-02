"""Beat and downbeat grids from `beat-this` (Foscarin et al., ISMIR 2024).

The bar grid is load-bearing for a light show — a cue that lands on beat 3 of
the bar instead of beat 1 reads as a mistake — and the harness README already
measured the essentia downbeat phase disagreeing with the hand-placed impacts by
up to 0.9 s on three of seven. So the grid itself is treated as a hypothesis to
be tested, not as given.
"""
from __future__ import annotations

import numpy as np

from .common import audio_path, cache_file


def _load(device: str = "cuda", dbn: bool = True):
    from beat_this.inference import File2Beats

    return File2Beats(checkpoint_path="final0", device=device, dbn=dbn)


def compute(song: str, *, model=None, device: str = "cuda") -> dict[str, np.ndarray]:
    # `dbn=True` runs madmom's DBN over the model's frame activations. Without
    # it the tracker halves its tempo inside sparse passages (Armin's beat
    # count came out at 264 against essentia's 415), which makes any bar-level
    # claim meaningless.
    model = model or _load(device)
    beats, downbeats = model(str(audio_path(song)))
    return {"beats": np.asarray(beats, dtype=float),
            "downbeats": np.asarray(downbeats, dtype=float)}


def load(song: str, *, rebuild: bool = False, model=None) -> dict[str, np.ndarray]:
    path = cache_file("beatthis", song)
    if rebuild or not path.exists():
        data = compute(song, model=model)
        np.savez_compressed(path, **data)
        return data
    return dict(np.load(path))
