"""The measurements. Reads caches only — no audio, no GPU, no model.

    question    Do CLAP audio embeddings know that a returning chorus is the
                same part of the song, and do they place section boundaries?
    measurement (1) ROC-AUC separating same-part from different-part section
                pairs; (2) recall of the 7 hand-placed drop impacts at a matched
                boundary budget; (3) whole-song nearest neighbours.
    incumbent   `sections.json`. For identity it emits nothing at all — see
                `identity_table` — so for boundaries it is `sections.json`'s own
                boundaries, and for identity the comparison is against the
                baselines below.
    baselines   MFCC and chroma over the identical windows and pooling; plus two
                controls that catch a confounded result — pair time-distance
                (are "same part" pairs just neighbours?) and duration.
"""
from __future__ import annotations

import json
import statistics

import numpy as np

from . import baselines, features, model
from .paths import (GOLD_SONGS, all_songs, allin1_sections, human_impacts,
                    shipped_sections_path)

TOLERANCES = (0.5, 1.0, 2.0)


# ----------------------------------------------------------------- identity --


def _section_vectors(song: str) -> tuple[list[dict], dict[str, np.ndarray], list[str]] | None:
    """Pooled section vectors for every representation, on identical windows."""
    sections = allin1_sections(song)
    if len(sections) < 3:
        return None
    clap = model.load(song)
    base = baselines.load(song)
    window_s = float(clap["window_s"])

    reps: dict[str, np.ndarray] = {}
    rows: list[dict] = []
    for name, matrix in (
        ("CLAP raw", model.unit(clap["emb"])),
        ("CLAP centred", features.centre(clap["emb"])),
        ("MFCC 20", baselines.standardised(base["mfcc"])),
        ("chroma 12", baselines.standardised(base["chroma"])),
    ):
        times = clap["times"] if name.startswith("CLAP") else base["times"]
        vectors, pooled_rows = features.pool_sections(times, matrix, sections, window_s)
        reps[name] = vectors
        rows = rows or pooled_rows

    labels = [s["function"] for s in sections]
    return rows, reps, labels


def _control_scores(rows: list[dict], kind: str) -> np.ndarray:
    """Pair scores for a control that uses no audio at all.

    If either control scores well, a good audio result means little: it would
    say only that same-labelled sections happen to be adjacent, or the same
    length, in this corpus.
    """
    out = []
    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            a, b = rows[i], rows[j]
            if kind == "time":
                mid_a = (a["start_s"] + a["end_s"]) / 2
                mid_b = (b["start_s"] + b["end_s"]) / 2
                out.append(-abs(mid_a - mid_b))
            else:
                da = a["end_s"] - a["start_s"]
                db = b["end_s"] - b["start_s"]
                out.append(-abs(da - db))
    return np.array(out, dtype=np.float32)


def identity_table(songs: list[str] | None = None) -> str:
    songs = songs or model.cached_songs(all_songs())
    per_method: dict[str, list[float]] = {}
    split_half: list[float] = []
    per_song_rows = []

    for song in songs:
        bundle = _section_vectors(song)
        if bundle is None:
            continue
        rows, reps, labels = bundle
        scored: dict[str, float] = {}
        same = None
        for name, vectors in reps.items():
            cos, same = features.pair_scores(vectors, labels)
            auc = features.roc_auc(cos, same)
            if auc is not None:
                scored[name] = auc
        for control in ("time", "duration"):
            auc = features.roc_auc(_control_scores(rows, control), same)
            if auc is not None:
                scored[f"ctl {control}"] = auc
        if not scored or same is None:
            continue

        clap = model.load(song)
        sh, _ = features.split_half_auc(
            clap["times"], features.centre(clap["emb"]),
            allin1_sections(song), float(clap["window_s"]))
        if sh is not None:
            split_half.append(sh)
        per_song_rows.append((song, len(rows), int(same.sum()), len(same), scored, sh))
        for name, auc in scored.items():
            per_method.setdefault(name, []).append(auc)

    methods = list(per_method)
    lines = [
        "Identity: can a representation tell a returning part from a different part?",
        "",
        "Columns 1-4: ROC-AUC over every pair of allin1 sections in a song, positives",
        "being the pairs allin1 gave the same functional label. 0.50 is chance.",
        "This is AGREEMENT BETWEEN TWO MODELS, not accuracy — the repository holds no",
        "hand-labelled section identity, so nothing here says either model is right.",
        "",
        "`ctl` columns use no audio at all and catch a confounded result.",
        "",
        "`split` is the one number that needs neither labels nor a second model: AUC",
        "separating the two halves of the same section from halves of different",
        "sections. It asks only whether the embedding is stable within a part.",
        "",
    ]
    header = (f"{'song':<40}{'sec':>4}{'pairs':>8}"
              + "".join(f"{m[:13]:>15}" for m in methods) + f"{'split':>8}")
    lines += [header, "-" * len(header)]
    for song, n_sec, n_same, n_pairs, scored, sh in per_song_rows:
        cells = "".join(f"{scored.get(m, float('nan')):>15.2f}" for m in methods)
        tail = f"{sh:>8.2f}" if sh is not None else f"{'-':>8}"
        lines.append(f"{song:<40}{n_sec:>4}{f'{n_same}/{n_pairs}':>8}{cells}{tail}")
    lines += ["-" * len(header)]
    mean_cells = "".join(f"{statistics.mean(per_method[m]):>15.2f}" for m in methods)
    mean_split = f"{statistics.mean(split_half):>8.2f}" if split_half else f"{'-':>8}"
    lines.append(f"{'mean over songs':<40}{'':>4}{'':>8}{mean_cells}{mean_split}")
    lines += [
        "",
        "The incumbent has no row here. `src/analyzer/stages/sections/form.py` computes",
        "a `repetition_group` letter and `ui_data.py` copies it into the projected",
        "`sections.json` — but it is `null` on every section of all 21 songs, so the key",
        "is dropped on write and no identity reaches the authoring model at all.",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------- boundaries --


def shipped_boundaries(song: str) -> list[float]:
    path = shipped_sections_path(song)
    if not path.exists():
        return []
    rows = json.loads(path.read_text())
    return [float(r["start"]) for r in rows if float(r["start"]) > 0.05]


def even_grid(span: float, count: int) -> list[float]:
    if count <= 0 or span <= 0:
        return []
    step = span / (count + 1)
    return [step * (i + 1) for i in range(count)]


def boundary_table(songs: list[str] | None = None) -> str:
    songs = [s for s in (songs or GOLD_SONGS) if human_impacts(s)]
    impacts = {s: human_impacts(s) for s in songs}
    total = sum(len(v) for v in impacts.values())
    rows: dict[str, dict[str, list[float]]] = {}
    spans: dict[str, float] = {}

    for song in songs:
        clap = model.load(song)
        base = baselines.load(song)
        span = float(clap["duration_s"])
        spans[song] = span
        shipped = shipped_boundaries(song)
        budget = max(len(shipped), 1)
        clap_novelty = features.novelty(clap["times"], model.unit(clap["emb"]))
        mfcc_novelty = features.novelty(base["times"], baselines.standardised(base["mfcc"]))
        rows[song] = {
            "CLAP semantic novelty": features.peak_pick(
                clap_novelty, clap["times"], min_gap_s=8.0, top_k=budget),
            "MFCC novelty (baseline)": features.peak_pick(
                mfcc_novelty, base["times"], min_gap_s=8.0, top_k=budget),
            "allin1 transitions": [
                s["start_s"] for s in allin1_sections(song)[1:]],
            "shipped sections.json": shipped,
            "even grid (= shipped budget)": even_grid(span, len(shipped)),
        }

    methods = list(next(iter(rows.values())).keys())
    lines = [
        "Boundaries: recall of the 7 hand-placed drop impacts, at a matched budget.",
        "",
        "Every learned method is capped at the incumbent's own boundary count for that",
        "song, so nothing wins by proposing more.",
        "",
    ]
    header = f"{'method':<32}" + "".join(f"{'+-' + str(t):>9}" for t in TOLERANCES) + f"{'bounds/min':>12}"
    lines += [header, "-" * len(header)]
    for method in methods:
        cells = []
        for tol in TOLERANCES:
            hits = sum(
                1 for song in songs for i in impacts[song]
                if any(abs(b - i) <= tol for b in rows[song][method])
            )
            cells.append(f"{hits}/{total}")
        rate = statistics.mean(
            len(rows[s][method]) / (spans[s] / 60.0) for s in songs if spans[s] > 0)
        lines.append(f"{method:<32}" + "".join(f"{c:>9}" for c in cells) + f"{rate:>12.1f}")
    return "\n".join(lines)


# ------------------------------------------------------------------ catalog --


def catalog_table(songs: list[str] | None = None) -> str:
    """Whole-song nearest neighbours, raw and after corpus centring.

    Raw, every song is every other song's neighbour at cosine ~0.998 — the same
    anisotropy that flattens the section vectors, one level up. Subtracting the
    corpus mean is what turns the numbers back into a ranking.
    """
    songs = songs or model.cached_songs(all_songs())
    raw = np.array([features.song_vector(model.load(s)["emb"]) for s in songs])
    centred = raw - raw.mean(axis=0, keepdims=True)
    centred /= np.linalg.norm(centred, axis=1, keepdims=True) + 1e-8

    lines = [
        "Catalog similarity: nearest neighbour of each song's mean CLAP vector.",
        "",
        "This is the 'audio vectors for similarity search' use the queue entry names.",
        "Raw cosines span a range of about 0.05 across the whole corpus, so the raw",
        "column is a ranking of noise; the centred column is the usable one.",
        "",
        "It also reaches nothing. No projected file carries a song-to-song relation",
        "(constitution §1.3), so however good this is, it changes nothing about a light",
        "show authored for one song.",
        "",
    ]
    header = f"{'song':<40}{'nearest (raw)':<34}{'cos':>7}   {'nearest (centred)':<34}{'cos':>7}"
    lines += [header, "-" * len(header)]
    for i, song in enumerate(songs):
        row = []
        for matrix in (raw, centred):
            sim = matrix[i] @ matrix.T
            sim[i] = -np.inf
            j = int(np.argmax(sim))
            row.append((songs[j], float(sim[j])))
        lines.append(f"{song:<40}{row[0][0]:<34}{row[0][1]:>7.3f}   "
                     f"{row[1][0]:<34}{row[1][1]:>7.3f}")

    off = raw @ raw.T
    np.fill_diagonal(off, np.nan)
    lines += [
        "",
        f"Raw pairwise cosine across the corpus: min {np.nanmin(off):.3f}, "
        f"max {np.nanmax(off):.3f}, spread {np.nanmax(off) - np.nanmin(off):.3f}.",
    ]
    return "\n".join(lines)
