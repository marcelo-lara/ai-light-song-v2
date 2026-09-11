"""CLAP contrastive differential — *"a person singing"* vs *"a flute, a synth
lead"*, read relative to the rest of the song, after the two centrings
`experiments/clap/probes.py` established as mandatory (survey Measurement 5):
never a single absolute-sentence reading, always a pair, always both
centrings, in order.

**Reuse, not reinvention.** The audio tower forward pass is
`experiments.clap.model.compute` called verbatim (same `MODEL_ID`,
`WINDOW_S=5.0`, `HOP_S=1.0`) — no new GPU code, no new pin. The text tower and
the two-centring formula below are the same shapes as
`experiments/clap/probes.py`'s `text_embeddings`/`axes`, generalised from that
module's six built-in pairs down to this one custom pair; the formula itself
is copied verbatim from `axes()` rather than imported, because `axes()` is
wired to the six-pair module-level `PAIRS` dict and this experiment needs a
different, single pair — duplicating four lines of arithmetic was judged
cheaper than reshaping the sibling module's API for one caller (see the
implementation report's design-decision list).

**Grid.** CLAP's own `HOP_S` is 1.0s — the frames below stay on that native
grid rather than being resampled onto a fake finer interval. Upsampling to
50ms would imply a timing precision a 5s analysis window does not have
(CLAUDE.md: say so rather than snapping). `interval_ms` in the exported
proposal is set from `hop_s` for exactly this reason.
"""
from __future__ import annotations

import numpy as np

from experiments.clap import model as clap_model

from . import paths

#: The contrastive pair. Positive = more singing-like than flute/synth-like,
#: relative to the rest of this song — never in absolute terms.
PAIR: tuple[str, str] = ("a person singing", "a flute, a synth lead")
SENTENCES = list(PAIR)

#: A CLAP window is 5s wide — a "phrase" shorter than this is grid noise, not
#: a real span. Not corpus-tuned; a documented judgement call (see README).
MIN_PHRASE_S = 2.0
#: Merge phrase runs separated by no more than one hop — the grid itself is
#: 1s, so a 1-frame dropout below threshold is not a real gap.
GAP_MERGE_S = 1.0


def text_embeddings(device: str = "cpu") -> np.ndarray:
    """One forward pass of the text tower over `PAIR` — same model/call shape
    as `experiments/clap/probes.py`'s `text_embeddings`, two sentences
    instead of twelve. CPU by default, same rationale as the sibling module:
    a couple of short sentences, and the GPU is busy with the audio side."""
    import torch
    from transformers import ClapModel, ClapProcessor

    model = ClapModel.from_pretrained(clap_model.MODEL_ID).to(device).eval()
    processor = ClapProcessor.from_pretrained(clap_model.MODEL_ID)
    with torch.no_grad():
        inputs = processor(text=SENTENCES, return_tensors="pt", padding=True).to(device)
        emb = torch.nn.functional.normalize(model.get_text_features(**inputs), dim=-1)
    return emb.cpu().numpy().astype(np.float32)


def differential(audio_emb: np.ndarray, text_emb: np.ndarray) -> np.ndarray:
    """The z-scored differential between the pair's two sentences, via the
    exact two-centring formula `experiments/clap/probes.py`'s `axes()` uses
    for each of its six pairs:

    1. centre across sentences within a window (cancels the per-window offset
       every sentence rides on together);
    2. centre across time within a sentence, i.e. per-song z-score (cancels
       the per-sentence offset that makes an absolute reading unusable).
    """
    sim = audio_emb @ text_emb.T
    sim = sim - sim.mean(axis=1, keepdims=True)
    sim = (sim - sim.mean(axis=0, keepdims=True)) / (sim.std(axis=0, keepdims=True) + 1e-8)
    raw = sim[:, 0] - sim[:, 1]
    return ((raw - raw.mean()) / (raw.std() + 1e-8)).astype(np.float32)


def _sigmoid(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-z))


def compute(song: str, *, device: str = "cuda", bundle=None, text_emb: np.ndarray | None = None) -> dict:
    """One CLAP audio forward pass (`experiments.clap.model.compute`) + one
    text forward pass (cheap, CPU), then the differential. `bundle`/
    `text_emb` are accepted so a caller processing many songs (`run.py`'s
    `compute` command) loads each model once, not once per song."""
    audio = clap_model.compute(song, device=device, bundle=bundle)
    if text_emb is None:
        text_emb = text_embeddings(device="cpu")
    z = differential(clap_model.unit(audio["emb"]), text_emb)
    voiceness = _sigmoid(z)
    confidence = np.clip(np.abs(voiceness - 0.5) * 2.0, 0.0, 1.0)
    return {
        "times": audio["times"].astype(np.float32),
        "z": z.astype(np.float32),
        "voiceness": voiceness.astype(np.float32),
        "confidence": confidence.astype(np.float32),
        "window_s": np.array(audio["window_s"], dtype=np.float32),
        "hop_s": np.array(audio["hop_s"], dtype=np.float32),
        "model_id": np.array(str(audio["model_id"])),
    }


def save(song: str, data: dict) -> None:
    paths.CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(paths.cache_path(song), **data)


def load(song: str, *, rebuild: bool = False, device: str = "cuda", bundle=None, text_emb: np.ndarray | None = None) -> dict:
    """Cached `compute`. Reading a cache needs neither a GPU nor
    `transformers` — only `export`/`score` should ever hit this path without
    `rebuild`."""
    path = paths.cache_path(song)
    if rebuild or not path.exists():
        data = compute(song, device=device, bundle=bundle, text_emb=text_emb)
        save(song, data)
        return data
    return dict(np.load(path, allow_pickle=False))


def cached_songs(songs: list[str]) -> list[str]:
    return [song for song in songs if paths.cache_path(song).exists()]


def derive_vocal_phrases(times: np.ndarray, voiceness: np.ndarray, confidence: np.ndarray) -> list[dict]:
    """Threshold (>=0.5) + short-gap merge + minimum-duration filter over the
    native ~1Hz CLAP grid.

    **Exported for the timeline and for `scorer.py`'s boundary bookkeeping —
    never a scored boundary-F1 comparison** (see `score.py`, README): a 5s
    analysis window cannot time an edge to the 0.25/0.5/1.0s tolerances the
    shared scorer uses.
    """
    times = np.asarray(times, dtype=float)
    voiceness = np.asarray(voiceness, dtype=float)
    confidence = np.asarray(confidence, dtype=float)
    if len(times) == 0:
        return []

    active = voiceness >= 0.5
    spans: list[tuple[int, int]] = []
    start = None
    for i, a in enumerate(active):
        if a and start is None:
            start = i
        elif not a and start is not None:
            spans.append((start, i - 1))
            start = None
    if start is not None:
        spans.append((start, len(active) - 1))

    merged: list[tuple[int, int]] = []
    for s, e in spans:
        if merged and times[s] - times[merged[-1][1]] <= GAP_MERGE_S:
            merged[-1] = (merged[-1][0], e)
        else:
            merged.append((s, e))

    phrases: list[dict] = []
    for s, e in merged:
        if times[e] - times[s] < MIN_PHRASE_S:
            continue
        phrases.append({
            "start": round(float(times[s]), 3),
            "end": round(float(times[e]), 3),
            "confidence": round(float(np.mean(confidence[s:e + 1])), 3),
        })
    return phrases
