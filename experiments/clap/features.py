"""Everything derived from the cached CLAP embeddings. No audio, no GPU.

Three separable questions are asked of the same vectors:

1. **Identity** — pooled inside a section, do two sections that are the same
   part of the song sit closer together than two that are not? This is the gap
   §1.2 names and no shipped artifact fills: knowing a chorus has returned is
   what lets a light show reuse a look.
2. **Boundaries** — does the embedding change where the song changes?
3. **Catalog similarity** — the whole-song vector, for song-to-song matching.

Pooling is *guarded*: a 5 s window centred 2 s inside a section still contains
2.5 s of its neighbour, so only windows lying wholly inside the section
contribute. Forgetting this guard is the easiest way to manufacture agreement
between neighbouring sections, and the survey made the same mistake once
already with its before/after probes.
"""
from __future__ import annotations

import numpy as np

from .model import unit


# ------------------------------------------------------------------ pooling --


def centre(emb: np.ndarray) -> np.ndarray:
    """Remove the song's own mean direction, then renormalise.

    CLAP's audio space is strongly anisotropic: two *different* sections of the
    same song come back at cosine 0.96-1.00, because almost all of the vector is
    a direction every window shares. Subtracting the song mean spreads the same
    pairs over -0.9..0.98, which is what makes an absolute distance threshold
    expressible at all.

    It is not free. Measured over 20 songs it *costs* accuracy on the headline
    question — mean same-part AUC falls from 0.68 raw to 0.61 centred — while
    improving the label-free split-half score (0.81 to 0.83). The shared
    direction is apparently carrying some real signal about which part of the
    song a window belongs to.

    So centring is used only where a threshold is needed: the review lane's
    identity letters. Every measurement in `score.py` is rank-based, reports raw
    and centred side by side, and depends on no threshold at all.
    """
    out = emb.astype(np.float32)
    out = out - out.mean(axis=0, keepdims=True)
    return out / (np.linalg.norm(out, axis=-1, keepdims=True) + 1e-8)


def pool_sections(times: np.ndarray, emb: np.ndarray, sections: list[dict],
                  window_s: float) -> tuple[np.ndarray, list[dict]]:
    """Mean CLAP vector per section, from windows lying wholly inside it.

    Returns `(vectors, rows)` where `rows[i]` records how many windows the
    vector was pooled from and whether the guard had to be relaxed — a section
    shorter than the analysis window has no clean window at all, and saying so
    is better than silently pooling contaminated ones.
    """
    half = window_s / 2.0
    vectors, rows = [], []
    for section in sections:
        start, end = float(section["start_s"]), float(section["end_s"])
        inside = (times - half >= start) & (times + half <= end)
        guarded = bool(inside.any())
        if not guarded:
            # Section shorter than the window: fall back to the single window
            # whose centre is nearest the section's middle, and mark it.
            inside = np.zeros(len(times), dtype=bool)
            inside[int(np.argmin(np.abs(times - (start + end) / 2.0)))] = True
        pooled = unit(emb[inside].astype(np.float32).mean(axis=0))
        vectors.append(pooled)
        rows.append({
            "id": section["id"],
            "windows": int(inside.sum()),
            "guarded": guarded,
            "start_s": start,
            "end_s": end,
            "function": section.get("function", "unknown"),
            "name": section.get("name", section.get("function", "unknown")),
        })
    return np.array(vectors, dtype=np.float32), rows


def split_half_vectors(times: np.ndarray, emb: np.ndarray, sections: list[dict],
                       window_s: float) -> tuple[np.ndarray, list[int]]:
    """Each section pooled twice — its first half and its second half.

    This is the one identity measurement that needs no second model and no
    labels at all. If the first half of a section is not closer to its own
    second half than to some other section's half, the embedding cannot support
    identity on this song, whatever any label says. Sections yielding fewer than
    two guarded windows are skipped rather than split.

    Returns the halves stacked in order, and the section index each half
    belongs to.
    """
    half = window_s / 2.0
    vectors, owner = [], []
    for index, section in enumerate(sections):
        start, end = float(section["start_s"]), float(section["end_s"])
        inside = np.where((times - half >= start) & (times + half <= end))[0]
        if len(inside) < 2:
            continue
        cut = len(inside) // 2
        for part in (inside[:cut], inside[cut:]):
            if len(part) == 0:
                continue
            vectors.append(unit(emb[part].astype(np.float32).mean(axis=0)))
            owner.append(index)
    return np.array(vectors, dtype=np.float32), owner


def split_half_auc(times: np.ndarray, emb: np.ndarray, sections: list[dict],
                   window_s: float) -> tuple[float | None, int]:
    """AUC separating "two halves of the same section" from "halves of different
    sections". 0.5 is chance; below ~0.7 the song has no usable identity signal."""
    vectors, owner = split_half_vectors(times, emb, sections, window_s)
    if len(vectors) < 4:
        return None, len(vectors)
    sim = similarity_matrix(vectors)
    scores, positive = [], []
    for i in range(len(vectors)):
        for j in range(i + 1, len(vectors)):
            scores.append(float(sim[i, j]))
            positive.append(owner[i] == owner[j])
    return roc_auc(np.array(scores), np.array(positive, dtype=bool)), len(vectors)


def song_vector(emb: np.ndarray) -> np.ndarray:
    """One 512-d vector for the whole song — the 'audio vector' framing."""
    return unit(emb.astype(np.float32).mean(axis=0))


# ----------------------------------------------------------------- identity --


def similarity_matrix(vectors: np.ndarray) -> np.ndarray:
    return vectors @ vectors.T


def pair_scores(vectors: np.ndarray, labels: list[str]) -> tuple[np.ndarray, np.ndarray]:
    """(cosine, same_label) over every unordered pair of sections in a song.

    `same_label` comes from allin1's functional labels. It is **agreement
    between two independently trained models, not accuracy against truth** —
    the repository has no hand-labelled section identity at all. A high score
    means CLAP and allin1 partition the song the same way; it cannot mean
    either of them is right.
    """
    n = len(vectors)
    sim = similarity_matrix(vectors)
    cos, same = [], []
    for i in range(n):
        for j in range(i + 1, n):
            cos.append(float(sim[i, j]))
            same.append(labels[i] == labels[j])
    return np.array(cos, dtype=np.float32), np.array(same, dtype=bool)


def roc_auc(scores: np.ndarray, positive: np.ndarray) -> float | None:
    """Probability that a same-label pair scores above a different-label pair.

    0.5 is chance, 1.0 is perfect separation. Rank-based, so it needs no
    threshold — which matters, because any threshold would be a hyperparameter
    fitted on four songs. Ties count as half, so a constant score gives exactly
    0.5 rather than an accidental win.
    """
    pos, neg = scores[positive], scores[~positive]
    if len(pos) == 0 or len(neg) == 0:
        return None
    order = np.argsort(np.concatenate([pos, neg]), kind="mergesort")
    ranks = np.empty(len(order), dtype=np.float64)
    ranks[order] = np.arange(1, len(order) + 1)
    # average ranks over ties
    values = np.concatenate([pos, neg])[order]
    i = 0
    while i < len(values):
        j = i
        while j + 1 < len(values) and values[j + 1] == values[i]:
            j += 1
        if j > i:
            ranks[order[i:j + 1]] = (i + j + 2) / 2.0
        i = j + 1
    rank_sum = ranks[:len(pos)].sum()
    return float((rank_sum - len(pos) * (len(pos) + 1) / 2.0) / (len(pos) * len(neg)))


#: Cosine distance on **centred** vectors at which two sections stop being "the
#: same part". It is a display threshold for the review lane only: no
#: measurement in `score.py` depends on it, which is why the AUCs above are
#: rank-based. Picked once from the pooled corpus distribution (see the README's
#: identity section) and then left alone.
IDENTITY_DISTANCE = 0.55

#: Below this split-half AUC a song's identity read is reported as unreliable
#: rather than shown as fact. 0.70 is the point at which the two halves of a
#: section stop being reliably closer to each other than to other sections.
IDENTITY_MIN_AUC = 0.70


def identity_letters(vectors: np.ndarray, threshold: float = IDENTITY_DISTANCE) -> list[str]:
    """Average-linkage agglomerative clustering on cosine distance -> A, B, C…

    Letters are assigned in order of first appearance, so `A B A C` reads as
    "the third section is the first one again".
    """
    n = len(vectors)
    if n == 0:
        return []
    distance = 1.0 - similarity_matrix(vectors)
    clusters = {i: [i] for i in range(n)}
    while len(clusters) > 1:
        best, pair = None, None
        keys = sorted(clusters)
        for a_i, a in enumerate(keys):
            for b in keys[a_i + 1:]:
                block = distance[np.ix_(clusters[a], clusters[b])]
                d = float(block.mean())
                if best is None or d < best:
                    best, pair = d, (a, b)
        if best is None or best > threshold:
            break
        a, b = pair
        clusters[a] = clusters[a] + clusters.pop(b)
    member_of = {}
    for members in clusters.values():
        for m in members:
            member_of[m] = min(members)
    letters, seen = [], {}
    for i in range(n):
        root = member_of[i]
        if root not in seen:
            seen[root] = chr(ord("A") + len(seen))
        letters.append(seen[root])
    return letters


# ---------------------------------------------------------------- boundaries --


def novelty(times: np.ndarray, emb: np.ndarray, lag_s: float = 4.0) -> np.ndarray:
    """Cosine distance between the window `lag_s` before and after each point.

    A text-free "the music became a different kind of thing" curve.
    """
    vectors = unit(emb.astype(np.float32))
    hop = float(np.median(np.diff(times))) if len(times) > 2 else 1.0
    lag = max(1, int(round(lag_s / hop)))
    out = np.zeros(len(vectors), dtype=np.float32)
    for i in range(len(vectors)):
        a = vectors[max(0, i - lag)]
        b = vectors[min(len(vectors) - 1, i + lag)]
        out[i] = 1.0 - float(a @ b)
    return out


def peak_pick(curve: np.ndarray, times: np.ndarray, *, min_gap_s: float,
              top_k: int) -> list[float]:
    """Greedy peak picking with a hard minimum spacing.

    `top_k` is set by the caller to the incumbent's boundary count, so both
    methods are compared at the same budget — a method that simply proposes
    more boundaries is not better.
    """
    order = np.argsort(curve)[::-1]
    chosen: list[int] = []
    for index in order:
        if len(chosen) >= top_k:
            break
        if any(abs(times[index] - times[c]) < min_gap_s for c in chosen):
            continue
        chosen.append(int(index))
    return sorted(float(times[c]) for c in chosen)
