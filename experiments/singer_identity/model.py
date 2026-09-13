"""ECAPA-TDNN speaker embeddings (`speechbrain/spkrec-ecapa-voxceleb`, pinned
checkpoint) over the vocal stem, gated by `whisperx_vad`'s cached activation.
`docs/experiments.md` "Singer Identity" — implemented with Sonnet, smoke
test on `_test_song` only.

**Checkpoint.** Not gated — unauthenticated HTTP against
`huggingface.co/speechbrain/spkrec-ecapa-voxceleb/resolve/main/...` succeeds
with no `HF_TOKEN` (verified first-hand this session; `pyannote/speaker-
diarization-3.1` is the one that needs a token and is explicitly excluded by
the spec). All five files the model needs (`hyperparams.yaml`,
`embedding_model.ckpt`, `mean_var_norm_emb.ckpt`, `classifier.ckpt`,
`label_encoder.txt` — `classifier.ckpt`/`label_encoder.txt` are unused by
embedding extraction but declared as `loadables` in `hyperparams.yaml`'s own
`Pretrainer`, so they must be present for `EncoderClassifier.from_hparams` to
load at all) were downloaded on the HOST, sha256-verified there (see
`README.md`), and are **not committed to git** (`.gitignore`, matching
`experiments/whisperx_vad/vad_pytorch_model.bin`'s precedent). `Dockerfile`
`COPY`s the pre-fetched, host-verified directory into the image and
re-checksums every file at build time. **No download of any kind happens at
image build time (the network fetch itself ran on the host, before `docker
build`) or at analysis time.**

`speechbrain.utils.fetching.guess_source` returns `FetchFrom.LOCAL` for any
`source` that is an existing local directory (verified against speechbrain
1.1.1's own source — see `README.md`) — but `source`/`savedir` alone only
control where `hyperparams.yaml` itself is fetched from. Each loadable
file's own path is resolved from `hyperparams.yaml`'s baked-in
`pretrained_path: speechbrain/spkrec-ecapa-voxceleb` (an HF repo id, since
the yaml was fetched verbatim from the Hub), so `_load_encoder` additionally
passes `overrides={"pretrained_path": <local dir>}` — without it,
`Pretrainer.collect_files` resolves every checkpoint file against the HF repo
id regardless of `source`/`savedir`, and does reach the network. See
`_load_encoder`'s own docstring for the exact call chain.

**Windowing.** 1.5s windows, 0.25s hop, over `artifacts/stems/vocals.wav`
resampled to the model's required 16kHz mono. For each window, the mean of
`whisperx_vad`'s cached per-frame activation (its own 50ms grid, read from
`experiments/whisperx_vad/cache/<song>.npz` — never recomputed here) over the
window's span decides whether it is a genuine embedding candidate:

    mean_activation <  VAD_GATE (0.2)  -> not embedded. `voiceness` for this
                                           window is reported as 0.0 by
                                           construction (the gate itself IS
                                           the claim "no voice here" reusing
                                           whisperx_vad's own call) —
                                           `confidence: None`, since no
                                           embedding-based measurement was
                                           made, only the gate's inherited
                                           claim.
    mean_activation >= VAD_GATE        -> embedded. This is the case that
                                           matters for beating whisperx_vad's
                                           false_vocal_rate: a loud
                                           instrumental false positive still
                                           clears the VAD gate, but its
                                           embedding should sit far from every
                                           voice cluster centroid, so
                                           `voice_similarity` (reported in the
                                           shared `voiceness` field) reads low
                                           even though the VAD gate itself
                                           fired.

**No silent fallbacks.** A window that clears the VAD gate but whose
embedding step itself fails (a decode error, a tail segment shorter than
`MIN_SEGMENT_S`) is never assigned a guessed value — its frame is omitted
from the exported series entirely (the schema's `voiceness` field is not
`Optional`, so "null" is represented here as "no frame emitted for this
time", not a fabricated number), and the reason is recorded in
`generated_from_extra["embedding_failures"]`. This is distinct from — and
must not be confused with — the below-gate case above, which is an honest,
documented design decision, not a failure.

**Clustering.** Agglomerative, cosine affinity, average linkage, over the
embedded windows only. k in {2, 3, 4} scored by `silhouette_score` (cosine
metric) when there are enough embedded windows; the k with the highest score
wins. **k=1 is then reachable only via an explicit collapse test** (see
`MERGE_SIMILARITY`/`SILHOUETTE_FLOOR` below) — silhouette itself is undefined
for a single cluster (`sklearn.metrics.silhouette_score` requires 2 <= k <=
n-1), so a seed of "k=1, score=0.0" compared with `>` can never be beaten by a
real silhouette score (which is essentially always > 0) and k=1 could never
be chosen this way. That was the defect fixed 2026-09-13: the corpus-wide k
distribution under the old code was {2: 19, 3: 3, 4: 1} — k=1 was never
selected once, including on songs with a single lead vocalist throughout.

The fix does not touch the silhouette search above (it still only ever picks
among k in {2, 3, 4}); it adds a second pass that can override that pick down
to k=1:

1. The winning silhouette must clear `SILHOUETTE_FLOOR`. Below it, the
   k>=2 split is not supported by the geometry and the collapse to k=1
   applies unconditionally (no centroid comparison needed).
2. Otherwise, iteratively merge the closest pair of centroids (by cosine
   similarity, recomputed after each merge) while their similarity exceeds
   `MERGE_SIMILARITY` — i.e. while the two "clusters" are close enough in
   embedding space to be the same voice rather than different voices. The
   number of clusters left standing when no pair still exceeds the
   threshold is the final k; if every centroid merges into one, k=1.

`voice_similarity` is each window's cosine similarity to its **nearest**
cluster centroid (not necessarily its assigned one, though they agree under
this linkage in practice) — the "distance to the nearest voice centroid" the
spec's output 1 asks for.

**`singer_change`** fires between consecutive embedded windows whose nearest-
centroid cluster differs; `confidence` is the lower of the two windows'
individual nearest-centroid similarities (an honest, computed number — how
weakly *either side* of the change belongs to its own cluster — never a
fabricated score).

Runs in the `ai-light-song-v2-singer-identity-research:dev` sandbox; see
`run_in_container.sh`.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from . import paths

SR = 16_000  # ECAPA-TDNN's required input rate

WINDOW_S = 1.5
HOP_S = 0.25
VAD_GATE = 0.2
MIN_SEGMENT_S = 0.20  # shorter than this and Fbank/ECAPA-TDNN have nothing to work with

K_CANDIDATES = (1, 2, 3, 4)

# --- k=1 collapse test (2026-09-13) ---------------------------------------
# Silhouette alone can never select k=1 (undefined for a single cluster), so
# a k>=2 silhouette winner is collapsed back to k=1 unless the clusters it
# found are actually different voices. Both constants are a starting point
# for ECAPA-TDNN/voxceleb cosine space, NOT hand-tuned against this corpus —
# `score.py`'s calibration report (declared `lead_voices` vs predicted k) is
# what justifies keeping or moving them; see README.md "Method" step 4/5.

#: Two cluster centroids whose cosine similarity is above this are the same
#: voice, not two different ones — voxceleb-trained ECAPA-TDNN embeddings of
#: the same speaker typically land well above 0.5 cosine similarity, and
#: different speakers well below it (common same/different-speaker verification
#: threshold on this checkpoint family). Centroids are cluster means of
#: multiple windows, so they are less noisy than a single pairwise trial —
#: 0.5 is a starting, not a fitted, threshold.
MERGE_SIMILARITY = 0.5

#: The winning k>=2 silhouette must clear this floor before the merge test
#: even runs; below it the split itself is not supported by the clustering
#: geometry (a weak or negative silhouette means points are about as close to
#: a neighboring cluster as their own) and k=1 stands unconditionally.
#: silhouette_score's range is [-1, 1]; 0.1 is a low bar deliberately, since
#: the merge test above is the primary k=1 gate — this floor only catches
#: the case where the search could not find any real structure at all.
SILHOUETTE_FLOOR = 0.1

CHECKPOINT_DIR = Path("/models/singer_identity/ecapa_checkpoint")
CHECKPOINT_FILES = (
    "hyperparams.yaml",
    "embedding_model.ckpt",
    "mean_var_norm_emb.ckpt",
    "classifier.ckpt",
    "label_encoder.txt",
)
# sha256 of each file as fetched from huggingface.co/speechbrain/spkrec-ecapa-voxceleb
# (main, commit 0f99f2d0ebe89ac095bcc5903c4dd8f72b367286) and verified first-hand
# this session — see README.md "Checkpoint".
CHECKPOINT_SHA256 = {
    "hyperparams.yaml": "6f78854fa04ba59e761437b76a2575d3aba5e5016de3e9b69f0c9a5077fb1a41",
    "embedding_model.ckpt": "0575cb64845e6b9a10db9bcb74d5ac32b326b8dc90352671d345e2ee3d0126a2",
    "mean_var_norm_emb.ckpt": "cd70225b05b37be64fc5a95e24395d804231d43f74b2e1e5a513db7b69b34c33",
    "classifier.ckpt": "fd9e3634fe68bd0a427c95e354c0c677374f62b3f434e45b78599950d860d535",
    "label_encoder.txt": "e13c3a167bb4112685670ee896d20e2b565af16b3a4ceeaa8689fa4d22adb8b9",
}


def _load_encoder(device: str = "cpu"):
    """`hyperparams.yaml` (fetched verbatim from the HF repo, see README.md)
    hardcodes `pretrained_path: speechbrain/spkrec-ecapa-voxceleb` — an HF
    repo id, not a path relative to wherever the yaml itself came from.
    `Pretrainer.collect_files` resolves every loadable's path from that
    baked-in string directly (`speechbrain/utils/parameter_transfer.py`,
    verified against 1.1.1's own source this session), so passing a local
    `source`/`savedir` to `from_hparams` alone is not enough to keep the
    checkpoint fetch offline — `pretrained_path` itself must be overridden to
    the local baked-in directory via `overrides`, which is exactly what makes
    `guess_source` resolve every loadable file locally (`FetchFrom.LOCAL`)
    instead of hitting the Hub."""
    from speechbrain.inference.classifiers import EncoderClassifier

    return EncoderClassifier.from_hparams(
        source=str(CHECKPOINT_DIR),
        savedir=str(CHECKPOINT_DIR),
        overrides={"pretrained_path": str(CHECKPOINT_DIR)},
        run_opts={"device": device},
    )


def _load_audio(path: Path) -> np.ndarray:
    import librosa

    if not path.exists():
        raise FileNotFoundError(f"expected audio at {path}")
    wave, _ = librosa.load(str(path), sr=SR, mono=True)
    return wave.astype(np.float32)


def _load_vad(song: str) -> tuple[np.ndarray, np.ndarray]:
    """`whisperx_vad`'s cached activation curve — read, never recomputed."""
    cache_path = paths.whisperx_vad_cache_path(song)
    if not cache_path.exists():
        raise FileNotFoundError(
            f"experiments/whisperx_vad has no cache for {song!r} at {cache_path} "
            "— run `whisperx_vad`'s own `compute` first; this experiment never "
            "recomputes VAD itself"
        )
    data = np.load(cache_path, allow_pickle=False)
    return data["times"], data["voiceness"]


def _mean_activation(vad_times: np.ndarray, vad_activation: np.ndarray, start: float, end: float) -> float:
    if len(vad_times) == 0:
        return 0.0
    mask = (vad_times >= start) & (vad_times < end)
    if not mask.any():
        # window narrower than the VAD grid step, or past its last sample —
        # fall back to the single nearest sample rather than an empty mean.
        idx = int(np.argmin(np.abs(vad_times - (start + end) / 2.0)))
        return float(vad_activation[idx])
    return float(np.mean(vad_activation[mask]))


def _window_starts(duration_s: float) -> list[float]:
    if duration_s <= WINDOW_S:
        return [0.0]
    last_start = duration_s - WINDOW_S
    n = int(np.floor(last_start / HOP_S + 1e-9)) + 1
    return [round(i * HOP_S, 3) for i in range(n)]


def _pairwise_cosine(centroids: np.ndarray) -> np.ndarray:
    """`(k, k)` cosine similarity matrix of already unit-normalized
    centroids — plain dot product."""
    if len(centroids) == 0:
        return np.zeros((0, 0), dtype=np.float32)
    return (centroids @ centroids.T).astype(np.float32)


def _collapse_by_similarity(
    matrix: np.ndarray, labels: np.ndarray, k: int
) -> tuple[int, np.ndarray, np.ndarray]:
    """Iteratively merge the closest pair of centroids while their cosine
    similarity exceeds `MERGE_SIMILARITY`, recomputing centroids after every
    merge (a merge changes membership, which changes the remaining
    centroids — a one-shot pairwise pass over the original centroids would
    not reflect that). Returns `(k, labels, centroids)` with `labels`
    relabeled into a contiguous `0..k-1` range."""
    # group_id -> list of original label ids folded into that group so far
    groups: dict[int, list[int]] = {c: [c] for c in range(k)}

    def group_centroid(member_labels: list[int]) -> np.ndarray:
        members = matrix[np.isin(labels, member_labels)]
        mean = members.mean(axis=0)
        norm = np.linalg.norm(mean)
        return mean / norm if norm > 0 else mean

    while len(groups) > 1:
        ids = sorted(groups.keys())
        cents = np.stack([group_centroid(groups[i]) for i in ids])
        sim = _pairwise_cosine(cents)
        np.fill_diagonal(sim, -np.inf)
        a, b = np.unravel_index(np.argmax(sim), sim.shape)
        if sim[a, b] <= MERGE_SIMILARITY:
            break
        id_a, id_b = ids[a], ids[b]
        groups[id_a].extend(groups[id_b])
        del groups[id_b]

    final_ids = sorted(groups.keys())
    remap = {old: new for new, old in enumerate(final_ids)}
    owner = {orig: remap[gid] for gid, members in groups.items() for orig in members}
    new_labels = np.array([owner[label] for label in labels], dtype=int)
    new_k = len(final_ids)
    new_centroids = _centroids(matrix, new_labels, new_k)
    return new_k, new_labels, new_centroids


def _cluster(matrix: np.ndarray) -> tuple[int, np.ndarray, np.ndarray, float, np.ndarray]:
    """Agglomerative cosine clustering: k in {2, 3, 4} chosen by silhouette,
    then collapsed to k=1 unless `SILHOUETTE_FLOOR` and `MERGE_SIMILARITY`
    (see their module-level docstrings) say the split is real. Returns
    `(k, labels, centroids, silhouette, centroid_similarity)` —
    `centroid_similarity` is the final `(k, k)` pairwise cosine similarity
    matrix and `silhouette` is the winning k>=2 score before collapse, or
    `nan` when no k>=2 was evaluable at all (fewer than 3 embedded windows)."""
    from sklearn.cluster import AgglomerativeClustering
    from sklearn.metrics import silhouette_score

    n = matrix.shape[0]
    best_k, best_score, best_labels = None, -1.0, None

    for k in K_CANDIDATES:
        if k == 1:
            continue
        if k >= n:
            break  # silhouette needs 2 <= k <= n-1
        model = AgglomerativeClustering(n_clusters=k, metric="cosine", linkage="average")
        labels = model.fit_predict(matrix)
        try:
            score = float(silhouette_score(matrix, labels, metric="cosine"))
        except ValueError:
            continue
        if score > best_score:
            best_k, best_score, best_labels = k, score, labels

    if best_k is None:
        # No k>=2 was even evaluable (n < 3 embedded windows) — there is no
        # silhouette score to report and nothing to collapse; k=1 by
        # construction, not by the collapse test.
        labels = np.zeros(n, dtype=int)
        centroids = _centroids(matrix, labels, 1)
        return 1, labels, centroids, float("nan"), _pairwise_cosine(centroids)

    if best_score < SILHOUETTE_FLOOR:
        # The split itself is not supported by the clustering geometry —
        # collapse unconditionally, no centroid comparison needed.
        labels = np.zeros(n, dtype=int)
        centroids = _centroids(matrix, labels, 1)
        return 1, labels, centroids, best_score, _pairwise_cosine(centroids)

    k, labels, centroids = _collapse_by_similarity(matrix, best_labels, best_k)
    return k, labels, centroids, best_score, _pairwise_cosine(centroids)


def _centroids(matrix: np.ndarray, labels: np.ndarray, k: int) -> np.ndarray:
    dim = matrix.shape[1]
    centroids = np.zeros((k, dim), dtype=np.float32)
    for c in range(k):
        members = matrix[labels == c]
        if len(members) == 0:
            continue
        mean = members.mean(axis=0)
        norm = np.linalg.norm(mean)
        centroids[c] = mean / norm if norm > 0 else mean
    return centroids


def _cosine_to_all(vec: np.ndarray, centroids: np.ndarray) -> np.ndarray:
    v_norm = np.linalg.norm(vec)
    if v_norm == 0 or len(centroids) == 0:
        return np.zeros(len(centroids), dtype=np.float32)
    v_unit = vec / v_norm
    return centroids @ v_unit


def compute(song: str, *, device: str = "cpu", encoder=None) -> dict:
    import torch

    encoder = encoder or _load_encoder(device)
    wave = _load_audio(paths.vocals_stem_path(song))
    duration_s = len(wave) / SR
    vad_times, vad_activation = _load_vad(song)

    starts = _window_starts(duration_s)
    ends = [round(min(s + WINDOW_S, duration_s), 3) for s in starts]
    gate_activation = [
        _mean_activation(vad_times, vad_activation, s, e) for s, e in zip(starts, ends)
    ]

    embeddings: list[np.ndarray | None] = []
    failures: list[dict] = []
    for s, e, act in zip(starts, ends, gate_activation):
        if act < VAD_GATE:
            embeddings.append(None)
            continue
        seg = wave[int(round(s * SR)) : int(round(e * SR))]
        if len(seg) < int(MIN_SEGMENT_S * SR):
            embeddings.append(None)
            failures.append({"start": s, "end": e, "reason": f"segment shorter than {MIN_SEGMENT_S}s minimum"})
            continue
        try:
            with torch.no_grad():
                emb = encoder.encode_batch(torch.from_numpy(seg).unsqueeze(0))
            emb = emb.squeeze().cpu().numpy().astype(np.float32)
        except Exception as exc:  # noqa: BLE001 — no silent fallback: record and move on, never guess a value
            embeddings.append(None)
            failures.append({"start": s, "end": e, "reason": f"{type(exc).__name__}: {exc}"[:200]})
            continue
        embeddings.append(emb)

    valid_idx = [i for i, e in enumerate(embeddings) if e is not None]
    if valid_idx:
        matrix = np.stack([embeddings[i] for i in valid_idx]).astype(np.float32)
        k, labels, centroids, silhouette, centroid_similarity = _cluster(matrix)
    else:
        matrix = np.zeros((0, 192), dtype=np.float32)
        k, labels, centroids = 1, np.zeros(0, dtype=int), np.zeros((1, 192), dtype=np.float32)
        silhouette, centroid_similarity = float("nan"), np.ones((1, 1), dtype=np.float32)

    n_windows = len(starts)
    cluster_of_window = np.full(n_windows, -1, dtype=int)
    similarity = np.full(n_windows, np.nan, dtype=np.float32)
    for j, i in enumerate(valid_idx):
        sims = _cosine_to_all(matrix[j], centroids)
        nearest = int(np.argmax(sims)) if len(sims) else 0
        cluster_of_window[i] = nearest
        similarity[i] = float(sims[nearest]) if len(sims) else 0.0

    return {
        "starts": np.array(starts, dtype=np.float32),
        "ends": np.array(ends, dtype=np.float32),
        "gate_activation": np.array(gate_activation, dtype=np.float32),
        "cluster_of_window": cluster_of_window,
        "similarity": similarity,
        "k": np.array(k),
        "duration_s": np.array(duration_s, dtype=np.float32),
        "failures": np.array(failures, dtype=object),
        "checkpoint_sha256": np.array(list(CHECKPOINT_SHA256.items()), dtype=object),
        "vad_gate": np.array(VAD_GATE, dtype=np.float32),
        "window_s": np.array(WINDOW_S, dtype=np.float32),
        "hop_s": np.array(HOP_S, dtype=np.float32),
        # The raw material the k decision was made from — cached so a future
        # re-clustering (e.g. re-running the collapse test with different
        # constants) is re-derivable without a GPU pass over the audio again.
        "embeddings": matrix,
        "embedded_window_index": np.array(valid_idx, dtype=int),
        "centroid_similarity": centroid_similarity,
        "silhouette": np.array(silhouette, dtype=np.float32),
    }


def save(song: str, data: dict) -> None:
    paths.CACHE_ROOT.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(paths.cache_path(song), **data)


def load(song: str, *, rebuild: bool = False, device: str = "cpu", encoder=None) -> dict:
    """Cached `compute`. Reading a cache needs neither `torch` nor
    `speechbrain` — only `export`/`score` should ever hit this path without
    `rebuild`."""
    path = paths.cache_path(song)
    if rebuild or not path.exists():
        data = compute(song, device=device, encoder=encoder)
        save(song, data)
        return data
    return dict(np.load(path, allow_pickle=True))


def singer_change_points(data: dict) -> list[dict]:
    """Change points between consecutive EMBEDDED windows whose nearest-
    centroid cluster differs. `confidence` is the lower of the two windows'
    own nearest-centroid similarities."""
    cluster = data["cluster_of_window"]
    similarity = data["similarity"]
    starts = data["starts"]
    ends = data["ends"]

    embedded_idx = [i for i in range(len(cluster)) if cluster[i] >= 0]
    out = []
    for a, b in zip(embedded_idx, embedded_idx[1:]):
        if cluster[a] == cluster[b]:
            continue
        out.append(
            {
                "time": round(float((ends[a] + starts[b]) / 2.0), 3),
                "from_cluster": int(cluster[a]),
                "to_cluster": int(cluster[b]),
                "confidence": round(float(min(similarity[a], similarity[b])), 3),
            }
        )
    return out
