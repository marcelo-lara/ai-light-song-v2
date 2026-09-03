"""allin1's frame-level outputs — everything the committed segmentation throws away.

`allin1.analyze(..., include_activations=True)` returns four curves at 100 Hz,
not just the 8-bar segment list:

    beat      (T,)     per-frame beat activation
    downbeat  (T,)     per-frame downbeat activation
    segment   (T,)     per-frame boundary novelty
    label     (10, T)  a posterior over
                       start end intro outro break bridge inst solo verse chorus

The published `segments` list is an argmax of the last of these, quantised to an
8-bar phrase. That discards two things a light show could use:

* **where inside a section the character changes** — the posterior moves
  continuously, the segment list does not;
* **the labels that lost.** A `break` posterior peaking inside a stretch the
  segmentation called `inst` is the model saying "there is a breakdown here"
  and then being overruled by the phrase grid.

Cached at 10 Hz rather than 100: nothing here resolves finer than a bar, and
100 Hz x 10 labels x 21 songs is 16 MB of float32 to carry for no gain.

Runs in the `ai-light-song-v2-allin1:dev` sandbox only.
"""
from __future__ import annotations

import numpy as np

from .model import DEMIX_DIR, SPEC_DIR, _seed_demix
from .paths import CACHE_ROOT, audio_path

#: allin1's own label order, from `allin1.typings`. `start` and `end` are
#: sentinels the model emits at the very edges, not musical categories.
LABELS = ("start", "end", "intro", "outro", "break", "bridge",
          "inst", "solo", "verse", "chorus")
MUSICAL = ("intro", "outro", "break", "bridge", "inst", "solo", "verse", "chorus")

SOURCE_RATE = 100.0
CACHE_RATE = 10.0


def cache_path(song: str):
    return CACHE_ROOT / "activations" / f"{song.replace('/', '_')}.npz"


def _decimate(curve: np.ndarray, factor: int) -> np.ndarray:
    """Mean over each block of `factor` frames — a posterior must be averaged,
    not sampled, or a one-frame spike survives and its neighbourhood does not."""
    usable = (curve.shape[-1] // factor) * factor
    trimmed = curve[..., :usable]
    return trimmed.reshape(*trimmed.shape[:-1], usable // factor, factor).mean(axis=-1)


def compute(song: str, *, device: str = "cuda") -> dict:
    import allin1

    _seed_demix(song)
    result = allin1.analyze(
        str(audio_path(song)), device=device,
        demix_dir=str(DEMIX_DIR), spec_dir=SPEC_DIR,
        include_activations=True, keep_byproducts=True,
    )
    acts = result.activations
    factor = int(SOURCE_RATE / CACHE_RATE)
    label = _decimate(np.asarray(acts["label"], dtype=np.float32), factor)
    return {
        "times": (np.arange(label.shape[1]) / CACHE_RATE).astype(np.float32),
        "label": label.astype(np.float32),
        "beat": _decimate(np.asarray(acts["beat"], dtype=np.float32), factor),
        "downbeat": _decimate(np.asarray(acts["downbeat"], dtype=np.float32), factor),
        "segment": _decimate(np.asarray(acts["segment"], dtype=np.float32), factor),
        "labels": np.array(LABELS),
        "rate_hz": np.array(CACHE_RATE, dtype=np.float32),
    }


def load(song: str, *, rebuild: bool = False) -> dict:
    path = cache_path(song)
    if rebuild or not path.exists():
        data = compute(song)
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(path, **data)
        return data
    return dict(np.load(path, allow_pickle=False))


def cached_songs(songs: list[str]) -> list[str]:
    return [song for song in songs if cache_path(song).exists()]


# ------------------------------------------------------------------ derived --


def posterior(data: dict, *, musical_only: bool = True) -> tuple[list[str], np.ndarray]:
    """Renormalised label posterior, sentinels optionally dropped.

    The raw activations do not sum to 1 — they are per-label sigmoids — so
    anything that reads them as a distribution has to renormalise first.
    """
    labels = [str(l) for l in data["labels"]]
    matrix = np.asarray(data["label"], dtype=np.float32)
    if musical_only:
        keep = [i for i, l in enumerate(labels) if l in MUSICAL]
        labels = [labels[i] for i in keep]
        matrix = matrix[keep]
    return labels, matrix / (matrix.sum(axis=0, keepdims=True) + 1e-9)


def entropy(data: dict) -> np.ndarray:
    """Normalised entropy of the per-frame posterior, 0 (certain) to 1 (flat).

    This is the honest confidence signal the segment list has no room for. High
    entropy means the model has no opinion here, and any character read taken
    from the posterior at that instant is noise.
    """
    labels, p = posterior(data)
    return (-(p * np.log(p + 1e-9)).sum(axis=0) / np.log(len(labels))).astype(np.float32)


def shadow_labels(data: dict, sections: list[dict], *,
                  min_share: float = 0.18, min_duration_s: float = 4.0) -> list[dict]:
    """Runs where a label the committed segmentation never used holds real mass.

    The segment list is an argmax quantised to 8 bars. A `break` posterior that
    holds 20 % of the mass for ten seconds inside a stretch labelled `inst` is
    the model saying something the published list cannot express — which is
    exactly the "beyond the arrangement" signal this module exists to surface.

    Only labels absent from the whole song's committed segmentation are
    considered, so this never re-reports the arrangement back at itself.
    """
    labels, p = posterior(data)
    times = np.asarray(data["times"], dtype=np.float32)
    committed = {s.get("function") for s in sections}
    step = 1.0 / float(data["rate_hz"])

    out = []
    for index, label in enumerate(labels):
        if label in committed:
            continue
        active = p[index] >= min_share
        start = None
        for i, on in enumerate(active):
            if on and start is None:
                start = i
            elif not on and start is not None:
                out.append((label, start, i))
                start = None
        if start is not None:
            out.append((label, start, len(active)))

    rows = []
    for label, i, j in out:
        if (j - i) * step < min_duration_s:
            continue
        rows.append({
            "label": label,
            "start_s": round(float(times[i]), 2),
            "end_s": round(float(times[min(j, len(times) - 1)]), 2),
            "peak_share": round(float(p[labels.index(label)][i:j].max()), 3),
            "mean_share": round(float(p[labels.index(label)][i:j].mean()), 3),
        })
    rows.sort(key=lambda r: r["start_s"])
    return rows
