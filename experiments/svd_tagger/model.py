"""PANNs (Kong et al., *"PANNs: Large-Scale Pretrained Audio Neural Networks
for Audio Pattern Recognition"*, <https://arxiv.org/abs/1912.10211>) — the
`Singing` head of its AudioSet-527 tagger, run on the vocal stem and on the
mix, both reported. D6.1 in `docs/implementation-plan-v3.5.md` resolved
PANNs over BEATs (smaller, stable checkpoint, narrower dependency footprint).

**Checkpoint.** `Cnn14_mAP=0.431.pth`
(<https://zenodo.org/records/3987831/files/Cnn14_mAP=0.431.pth>), fetched and
sha256-checksummed at image BUILD time by `Dockerfile` — never at analysis
time. See `Dockerfile` for the pinned hash.

**Class index.** PANNs' AudioSet-527 label set (`class_labels_indices.csv`,
<https://github.com/qiuqiangkong/audioset_tagging_cnn>) is 0-indexed;
`"Singing"` is index 27 (row 29 of that CSV, counting the header). Verified
directly against the CSV this session (sha256
`cdd1049833c4b86127c2773ac0d14a2754b6a6d0d1798002ed5c66e699708429`). This
index is stable for as long as the pinned checkpoint is — AudioSet's 527-class
ordering does not change underneath a fixed model.

**Grid.** No frame-level PANNs variant is used here (that would need the
`Cnn14_DecisionLevelMax` checkpoint — a second pin, not built). Instead this
mirrors `experiments/clap/model.py`'s own sliding-window pattern: clip-level
`AudioTagging.inference()` over a 5 s window / 1 s hop, one forward pass per
window. `interval_ms` in the exported proposal is 1000 for exactly this
reason (CLAUDE.md: say so rather than snapping and implying a precision that
isn't there).

Runs in the `ai-light-song-v2-svd-research:dev` sandbox; see
`run_in_container.sh`.
"""
from __future__ import annotations

import numpy as np

from . import paths

SR = 32_000  # PANNs' own training sample rate
WINDOW_S = 5.0
HOP_S = 1.0
BATCH = 8

#: AudioSet-527 class index of "Singing" — see module docstring.
SINGING_CLASS_INDEX = 27

#: Merge phrase runs separated by no more than one hop.
GAP_MERGE_S = 1.0
#: A 5s window is not sharp enough to time anything shorter as a real phrase.
MIN_PHRASE_S = 2.0


def _load(device: str = "cpu"):
    from panns_inference import AudioTagging

    checkpoint_path = "/opt/panns/Cnn14_mAP=0.431.pth"
    tagger = AudioTagging(checkpoint_path=checkpoint_path, device=device)
    return tagger


def _load_audio(path) -> np.ndarray:
    import librosa

    if not path.exists():
        raise FileNotFoundError(f"expected audio at {path}")
    wave, _ = librosa.load(str(path), sr=SR, mono=True)
    return wave.astype(np.float32)


def _windowed_singing_scores(tagger, wave: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """One PANNs clip-level forward pass per 5s/1s-hop window; returns
    `(times, singing_prob)` — `times` labelled at each window's centre, same
    convention as `experiments/clap/model.py`."""
    win = int(WINDOW_S * SR)
    hop = int(HOP_S * SR)
    starts = np.arange(0, max(1, len(wave) - win + hop), hop)
    centres = starts / SR + WINDOW_S / 2.0

    scores = []
    for i in range(0, len(starts), BATCH):
        batch = []
        for s in starts[i:i + BATCH]:
            seg = wave[s:s + win]
            if len(seg) < win:
                seg = np.pad(seg, (0, win - len(seg)))
            batch.append(seg)
        batch_arr = np.stack(batch, axis=0)
        clipwise_output, _ = tagger.inference(batch_arr)
        scores.append(np.asarray(clipwise_output)[:, SINGING_CLASS_INDEX])
    singing = np.concatenate(scores).astype(np.float32) if scores else np.zeros(0, dtype=np.float32)
    return centres.astype(np.float32), singing


def compute(song: str, *, device: str = "cpu", tagger=None) -> dict:
    """One PANNs forward pass per window, on BOTH the vocal stem and the
    mix. `tagger` is accepted so a caller processing many songs loads the
    checkpoint once."""
    tagger = tagger or _load(device)

    stem_wave = _load_audio(paths.vocals_stem_path(song))
    mix_wave = _load_audio(paths.mix_audio_path(song))

    stem_times, stem_voiceness = _windowed_singing_scores(tagger, stem_wave)
    mix_times, mix_voiceness = _windowed_singing_scores(tagger, mix_wave)

    return {
        "stem_times": stem_times,
        "stem_voiceness": stem_voiceness,
        "mix_times": mix_times,
        "mix_voiceness": mix_voiceness,
        "window_s": np.array(WINDOW_S, dtype=np.float32),
        "hop_s": np.array(HOP_S, dtype=np.float32),
        "class_index": np.array(SINGING_CLASS_INDEX, dtype=np.int32),
        "checkpoint": np.array("Cnn14_mAP=0.431.pth"),
    }


def save(song: str, data: dict) -> None:
    paths.CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(paths.cache_path(song), **data)


def load(song: str, *, rebuild: bool = False, device: str = "cpu", tagger=None) -> dict:
    """Cached `compute`. Reading a cache needs neither `torch` nor
    `panns_inference` — only `export`/`score` should ever hit this path
    without `rebuild`."""
    path = paths.cache_path(song)
    if rebuild or not path.exists():
        data = compute(song, device=device, tagger=tagger)
        save(song, data)
        return data
    return dict(np.load(path, allow_pickle=False))


def cached_songs(songs: list[str]) -> list[str]:
    return [song for song in songs if paths.cache_path(song).exists()]


def derive_vocal_phrases(times: np.ndarray, voiceness: np.ndarray) -> list[dict]:
    """Threshold (>=0.5) + short-gap merge + minimum-duration filter over
    the ~1Hz PANNs window grid — same shape as
    `experiments/clap_voiceness/model.py::derive_vocal_phrases`.

    Exported for the timeline and for `scorer.py`'s boundary bookkeeping —
    a 5s analysis window cannot time an edge to the 0.25/0.5/1.0s tolerances
    the shared scorer uses, so boundary F1 is reported, never scored, for
    this candidate (see README/score.py)."""
    times = np.asarray(times, dtype=float)
    voiceness = np.asarray(voiceness, dtype=float)
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
            "confidence": round(float(np.mean(voiceness[s:e + 1])), 3),
        })
    return phrases
