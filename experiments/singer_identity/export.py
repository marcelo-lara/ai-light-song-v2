"""Write the ECAPA-TDNN speaker-embedding candidate's `voice_similarity`
(output 1, in the shared `voiceness` field) and `singer_change` (output 2) to
`reference/proposals/singer_identity.json` via `voiceness_common.schema`, so
`voiceness_common.scorer` scores output 1 with no new scoring code.

Single producer, single channel (the vocal stem only) — same shape as
`whisperx_vad` (item 7). `singer_change` is not part of the shared schema
(it has no incumbent to be scored against elsewhere), so it rides along as
an extra top-level key added after `VoicenessProposal.to_proposal_json()`
builds the shared shape, rather than folded into `generated_from` metadata —
it is a real output, not provenance.

**Grid (`docs/experiments.md` "Singer Identity", decided 2026-09-12):**
`voice_similarity`'s native unit of measurement is the 1.5s/0.25s-hop window
itself — there is nothing finer to resample from — but it is emitted here on
the shared **50ms grid** by nearest-window hold (each 50ms frame takes the
value of the native window whose centre is nearest it), not interpolated
(unlike `whisperx_vad`, which resamples a genuinely continuous curve via
`np.interp`; a hold is the honest operation over a value that is constant
across its whole native window). This is what lets a per-frame AND against
`whisperx_vad`/`vocal_voiceness`/`clap_voiceness` work at all. The grid times
themselves are read straight from `whisperx_vad`'s own cached grid
(`model._load_vad`) rather than re-derived, so the two proposals' frame times
are identical, not just similarly-spaced. `generated_from` still records the
true native resolution (`window_s`/`hop_s`) beside the 50ms emission grid, so
no reader mistakes 50ms of precision for something this candidate actually
measured.
"""
from __future__ import annotations

import json

import numpy as np

from experiments.voiceness_common.schema import VoicenessFrame, VoicenessProposal

from . import model, paths

EXPERIMENT = "experiments/singer_identity"
ENGINE = (
    "singer_identity.model (speechbrain/spkrec-ecapa-voxceleb ECAPA-TDNN "
    "embeddings, 1.5s/0.25s-hop windows gated at whisperx_vad activation "
    ">= 0.2, agglomerative cosine clustering k in 1..4 by silhouette, "
    "voiceness = cosine similarity to nearest cluster centroid, resampled "
    "onto the shared 50ms grid by nearest-window hold)"
)

#: The shared emission grid every voiceness candidate writes to
#: (`voiceness_common.schema`'s default `interval_ms=50`) — distinct from
#: this candidate's own native resolution (`model.WINDOW_S`/`model.HOP_S`).
GRID_S = 0.05


def _grid_times(song: str) -> np.ndarray:
    """The exact 50ms grid `whisperx_vad`'s own proposal was built on (not a
    freshly-derived `np.arange` that could drift from it by a rounding
    step), read straight from its cache so this candidate's frame times are
    identical to `whisperx_vad.json`'s — required for the per-frame AND the
    grid decision exists for."""
    vad_times, _ = model._load_vad(song)
    return vad_times


def _nearest_window_hold(grid_times: np.ndarray, starts: np.ndarray, ends: np.ndarray) -> np.ndarray:
    """For each 50ms grid time, the index of the native window whose centre
    is nearest — provided that window's own span actually covers the grid
    time (`start <= t <= end`). Returns -1 where no native window covers the
    instant (e.g. a grid frame past the last window's end): the hold must
    never invent coverage outside the embedded region."""
    if len(starts) == 0:
        return np.full(len(grid_times), -1, dtype=int)
    centers = (starts + ends) / 2.0
    idx = np.clip(np.searchsorted(centers, grid_times), 0, len(centers) - 1)
    idx_prev = np.clip(idx - 1, 0, len(centers) - 1)
    use_prev = np.abs(grid_times - centers[idx_prev]) <= np.abs(grid_times - centers[idx])
    nearest = np.where(use_prev, idx_prev, idx)
    covered = (grid_times >= starts[nearest]) & (grid_times <= ends[nearest])
    return np.where(covered, nearest, -1)


def build_frames(song: str, data: dict | None = None) -> tuple[list[VoicenessFrame], int]:
    """The one and only definition of the emitted `voice_similarity` series —
    50ms grid, nearest-window hold. `export()` calls this to write the
    proposal; `score.py` calls this (or reads the proposal `export()` already
    wrote) so the scored series and the published series are never two
    independent implementations that can drift apart (docs/experiments.md
    "Singer Identity" — the whole point of the grid decision is that the
    scored and published series are the *same* object).

    Returns `(frames, n_grid_frames_uncovered)`.
    """
    data = data if data is not None else model.load(song)

    starts = data["starts"]
    ends = data["ends"]
    cluster = data["cluster_of_window"]
    similarity = data["similarity"]
    gate_activation = data["gate_activation"]

    grid_times = _grid_times(song)
    nearest = _nearest_window_hold(grid_times, starts, ends)

    frames = []
    n_uncovered = 0
    for t, i in zip(grid_times, nearest):
        t = float(t)
        if i < 0:
            # No native window covers this 50ms instant (past the last
            # window's end — the native windows stop at the vocal stem's
            # own duration, which need not land exactly on the shared
            # grid's last step). Honest null, not an invented hold.
            n_uncovered += 1
            frames.append(VoicenessFrame(time_s=t, voiceness=0.0, confidence=None))
            continue
        if cluster[i] < 0:
            if gate_activation[i] < model.VAD_GATE:
                # Below the VAD gate: not embedded, by design — the gate
                # itself is the "no voice here" claim, reused from
                # whisperx_vad, not a guessed similarity. Unchanged by the
                # grid change.
                frames.append(VoicenessFrame(time_s=t, voiceness=0.0, confidence=None))
            # else: the nearest native window cleared the gate but its own
            # embedding failed — omitted entirely, see `model.py`'s
            # "embedding_failures" and its module docstring ("No silent
            # fallbacks"). No frame is emitted for this time.
            continue
        frames.append(
            VoicenessFrame(time_s=t, voiceness=round(float(similarity[i]), 4), confidence=None)
        )
    return frames, n_uncovered


def export(song: str) -> dict:
    data = model.load(song)

    starts = data["starts"]
    cluster = data["cluster_of_window"]
    gate_activation = data["gate_activation"]

    frames, n_uncovered = build_frames(song, data=data)

    # `vocal_phrase` is left empty: this candidate does not derive its own
    # phrase segmentation (that is `whisperx_vad`'s job, reused above via
    # `gate_activation`) — only the frame-level `voice_similarity` and the
    # `singer_change` points below are this candidate's actual output.
    phrases: list = []

    failures = list(data["failures"]) if data["failures"].size else []
    checkpoint_sha256 = {k: v for k, v in data["checkpoint_sha256"]}

    # `None`, not a NaN literal, for JSON — this project's convention for
    # "no measurement was made" (see `VoicenessFrame.confidence`).
    silhouette_raw = float(data["silhouette"])
    silhouette = silhouette_raw if silhouette_raw == silhouette_raw else None  # NaN != NaN

    centroid_similarity = data["centroid_similarity"]
    if centroid_similarity.shape[0] >= 2:
        off_diag = centroid_similarity[
            ~np.eye(centroid_similarity.shape[0], dtype=bool)
        ]
        max_centroid_similarity = float(off_diag.max())
    else:
        # k=1 (or no embedded windows at all) has no second centroid to
        # compare against.
        max_centroid_similarity = None

    proposal = VoicenessProposal(
        song_name=song,
        experiment=EXPERIMENT,
        engine=ENGINE,
        frames=frames,
        vocal_phrase=phrases,
        generated_from_extra={
            "checkpoint": "speechbrain/spkrec-ecapa-voxceleb (ECAPA-TDNN)",
            "checkpoint_sha256": checkpoint_sha256,
            "vad_gate": float(data["vad_gate"]),
            # True underlying resolution — the emitted grid below is a hold
            # over this, not a genuinely finer measurement (CLAUDE.md: say
            # so rather than implying a precision that isn't there).
            "native_window_s": float(data["window_s"]),
            "native_hop_s": float(data["hop_s"]),
            "emission_grid_s": GRID_S,
            "emission_method": "nearest-window hold onto whisperx_vad's own 50ms grid",
            "k": int(data["k"]),
            # The two numbers the k=1 collapse test's constants
            # (`model.SILHOUETTE_FLOOR`/`model.MERGE_SIMILARITY`) were
            # applied to — so the k decision is auditable from the
            # published proposal alone, without recomputing embeddings.
            "silhouette": silhouette,
            "max_centroid_similarity": max_centroid_similarity,
            "n_windows": int(len(starts)),
            "n_windows_embedded": int((cluster >= 0).sum()),
            "n_windows_below_gate": int((gate_activation < model.VAD_GATE).sum()),
            "embedding_failures": failures,
            "n_grid_frames_uncovered": n_uncovered,
            "grid_frames_uncovered_reason": (
                "grid frame time falls outside every native window's "
                "[start, end] span (typically past the last window's end) "
                "— held at 0.0/null rather than invented"
                if n_uncovered
                else None
            ),
            "reuses_vad_from": "experiments/whisperx_vad (cached activation and grid times, not recomputed)",
        },
        interval_ms=int(round(GRID_S * 1000)),
    )
    payload = proposal.to_proposal_json()
    payload["singer_change"] = model.singer_change_points(data)

    path = paths.proposal_path(song)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return payload


def export_all(songs: list[str]) -> None:
    for song in songs:
        export(song)
        print(f"exported {song}")
