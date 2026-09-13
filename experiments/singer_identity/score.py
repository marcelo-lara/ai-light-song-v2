"""Score output 1 (`voice_similarity`, in the shared `voiceness` field)
against the three shared incumbents (`voiceness_common.incumbents`) plus
`whisperx_vad` itself, via the shared scorer (`voiceness_common.scorer`) — no
new scoring code, per `docs/experiments.md` "Singer Identity".

**Scoring corpus is the three songs that actually carry three-class ground
truth** (`experiments/voiceness_common/vocal_ground_truth.json`): `ayuni`,
`Cinderella - Ella Lee`, `Armin - Revolution` — not the item 4-7 family's
four-gold-song `GOLD_SONGS`, none of which are in that map. Matches the
spec's own "Scoring" section.

**Kill condition** (spec, restated so it is checked in one place): output 1
is killed if it neither beats `whisperx_vad` on `Cinderella - Ella Lee`'s
`false_vocal_rate` nor matches it on `ayuni`'s. This module does not decide
the kill itself — it only produces the comparable numbers; the decision is
the operator's, made from `gold_table`'s output.

**Output 2 (`singer_change`) is reported, not scored by this module** — it
is compared against `Armin - Revolution`'s one marked handoff (male 30.0-55.8s
-> female 81.6-88.0s) at +-1.0s tolerance, but that comparison is a manual
by-ear/by-eye check against the exported `singer_change` list (per the spec:
"reported-not-scored elsewhere"), not a boundary-F1 pass through
`voiceness_common.scorer` (which only knows `vocal_phrase` edges, not named
cluster identities).

Same three-class ground truth machinery as `whisperx_vad`/`vocal_voiceness`:
`scorer.ground_truth(hints_doc, song, scorer.load_class_map())` — see that
module's docstring for what each class means and what denominator changed.
"""
from __future__ import annotations

import json
import statistics

import numpy as np

from experiments.voiceness_common import incumbents, scorer as voiceness_scorer
from experiments.voiceness_common.schema import frames_as_tuples, phrases_as_dicts
from experiments.whisperx_vad import model as whisperx_vad_model

from . import export as export_mod, model, paths

CANDIDATES = ("singer_identity", "whisperx_vad", "arrangement_state", "vocal_phrases", "mix_rms_baseline")


def _candidate_frames_phrases(name: str, song: str):
    if name == "singer_identity":
        # Score the exact series `export.py` publishes — 50ms grid, nearest-
        # window hold — never a second, independently-derived native-hop
        # series (docs/experiments.md "Singer Identity": scoring at 0.25s
        # while publishing at 50ms would defeat the point of the grid
        # decision, since the scored series and the published lane must be
        # the same object for the reported numbers to describe what
        # `voice_similarity` actually is). Prefer reading the already-written
        # proposal (exactly what a consumer reads); fall back to
        # `export.build_frames` — the single shared definition, not a
        # reimplementation — if `export` hasn't run yet for this song.
        proposal_path = paths.proposal_path(song)
        if proposal_path.exists():
            payload = json.loads(proposal_path.read_text())
            frames = [(f["time"], f["voiceness"]) for f in payload["frames"]]
        else:
            built, _n_uncovered = export_mod.build_frames(song)
            frames = frames_as_tuples(built)
        return frames, []  # no vocal_phrase — see export.py
    if name == "whisperx_vad":
        vad_data = whisperx_vad_model.load(song)
        frames = [(float(t), float(v)) for t, v in zip(vad_data["times"], vad_data["voiceness"])]
        phrases = whisperx_vad_model.vocal_phrases(vad_data)
        return frames, phrases
    if name == "arrangement_state":
        f, p = incumbents.arrangement_state_incumbent(song)
        return frames_as_tuples(f), phrases_as_dicts(p)
    if name == "vocal_phrases":
        f, p = incumbents.vocal_phrases_incumbent(song)
        return frames_as_tuples(f), phrases_as_dicts(p)
    if name == "mix_rms_baseline":
        f, p = incumbents.mix_rms_baseline_incumbent(song)
        return frames_as_tuples(f), phrases_as_dicts(p)
    raise ValueError(name)


def _load_ground_truth(song: str) -> voiceness_scorer.GroundTruth:
    hints_path = paths.hints_path(song)
    hints_doc = json.loads(hints_path.read_text()) if hints_path.exists() else {"human_hints": []}
    class_map = voiceness_scorer.load_class_map()
    return voiceness_scorer.ground_truth(hints_doc, song, class_map)


def score_song(song: str) -> dict:
    truth = _load_ground_truth(song)

    out = {
        "song": song,
        "n_positive_spans": len(truth.positive),
        "n_residual_spans": len(truth.residual),
        "n_negative_spans": len(truth.negative),
        "candidates": {},
    }
    for name in CANDIDATES:
        frames, phrases = _candidate_frames_phrases(name, song)
        duration = max((t for t, _ in frames), default=0.0)
        result = voiceness_scorer.score(frames, phrases, truth, duration_s=duration)
        out["candidates"][name] = {
            "frame_accuracy": round(result.frame_accuracy, 4),
            "false_vocal_rate": round(result.false_vocal_rate, 4),
            "residual_firing_rate": round(result.residual_firing_rate, 4),
            "bounds_per_min": round(result.bounds_per_min, 2),
            "boundary_f1": {str(t): round(b.f1, 3) for t, b in result.boundary.items()},
            "is_proxy_no_ground_truth": result.n_frames_evaluable == result.n_frames_residual,
        }
    return out


def gold_table(songs: list[str]) -> str:
    lines = []
    agg_acc: dict[str, list[float]] = {c: [] for c in CANDIDATES}
    agg_false_vocal: dict[str, list[float]] = {c: [] for c in CANDIDATES}
    agg_bpm: dict[str, list[float]] = {c: [] for c in CANDIDATES}

    for song in songs:
        row = score_song(song)
        lines.append(
            f"\n{song}  ({row['n_positive_spans']} positive / "
            f"{row['n_residual_spans']} residual / {row['n_negative_spans']} negative spans)"
        )
        header = (
            f"  {'candidate':<20}{'frame_acc':>11}{'false_vocal_rate':>18}"
            f"{'residual_firing':>16}{'bounds/min':>12}{'F1@0.5s':>10}"
        )
        lines.append(header)
        for name in CANDIDATES:
            c = row["candidates"][name]
            lines.append(
                f"  {name:<20}{c['frame_accuracy']:>11.4f}{c['false_vocal_rate']:>18.4f}"
                f"{c['residual_firing_rate']:>16.4f}{c['bounds_per_min']:>12.2f}{c['boundary_f1'].get('0.5', 0.0):>10.3f}"
                f"{'  (proxy — no evaluable ground truth)' if c['is_proxy_no_ground_truth'] else ''}"
            )
            agg_acc[name].append(c["frame_accuracy"])
            agg_false_vocal[name].append(c["false_vocal_rate"])
            agg_bpm[name].append(c["bounds_per_min"])

    lines.append(f"\nAggregate across {len(songs)} songs:")
    header = f"  {'candidate':<20}{'avg frame_acc':>15}{'avg false_vocal_rate':>22}{'avg bounds/min':>16}"
    lines.append(header)
    for name in CANDIDATES:
        lines.append(
            f"  {name:<20}{statistics.mean(agg_acc[name]):>15.4f}"
            f"{statistics.mean(agg_false_vocal[name]):>22.4f}"
            f"{statistics.mean(agg_bpm[name]):>16.2f}"
        )
    return "\n".join(lines)


def write_report(songs: list[str] | None = None) -> None:
    songs = songs if songs else paths.SCORING_CORPUS
    paths.OUT_ROOT.mkdir(parents=True, exist_ok=True)
    text = "Singer Identity — vs whisperx_vad / arrangement_state / vocal_phrases / mix-RMS\n" + "=" * 80 + "\n"
    text += gold_table(songs) + "\n"
    paths.score_out_path().write_text(text)
    print(text)


# --- singer-count calibration report (2026-09-13) -------------------------
# Scores the k=1 collapse test (`model._cluster`) against
# `singer_ground_truth.json` — the operator's by-ear `lead_voices` map. This
# is a separate report from `write_report` above: that one scores the shared
# `voice_similarity` output against the three-class vocal ground truth; this
# one scores the *cluster count* `k` against declared singer counts, which
# needs no `voiceness_common` machinery at all, only this experiment's own
# cache.

def _load_ground_truth_map() -> dict:
    doc = json.loads(paths.singer_ground_truth_path().read_text())
    return {song: meta for song, meta in doc.items() if not song.startswith("_")}


def _load_cache(song: str) -> dict:
    """Read-only: never falls back to `compute` (which needs the
    `singer-identity` sandbox, not the plain `app` image this report runs
    in). A declared ground-truth song with no cache yet is a hard failure,
    not a skip — see `calibration_report`'s docstring."""
    cache_path = paths.cache_path(song)
    if not cache_path.exists():
        raise FileNotFoundError(
            f"singer_ground_truth.json declares {song!r} but "
            f"experiments/singer_identity/cache/{song}.npz does not exist — "
            "run `compute` for it first (needs the singer-identity sandbox "
            "image); this report never computes, only reads what compute "
            "already wrote"
        )
    return dict(np.load(cache_path, allow_pickle=True))


def singer_count_row(song: str) -> dict:
    """One song's predicted-vs-cached facts: `k`, the winning silhouette,
    the max off-diagonal centroid similarity, and the `singer_change` count
    and rate — the same quantities `export.py` publishes into
    `generated_from_extra`, read straight from the cache so this report and
    the published proposal can never independently drift."""
    data = _load_cache(song)
    if "silhouette" not in data:
        raise KeyError(
            f"{song!r}'s cache at {paths.cache_path(song)} predates the "
            "2026-09-13 k=1 collapse-test fix (no 'silhouette'/"
            "'centroid_similarity' arrays) — re-run `compute` for it before "
            "calibrating; this report never re-derives them from an older cache"
        )
    k = int(data["k"])
    silhouette_raw = float(data["silhouette"])
    silhouette = silhouette_raw if silhouette_raw == silhouette_raw else None  # NaN != NaN

    centroid_similarity = data["centroid_similarity"]
    if centroid_similarity.shape[0] >= 2:
        off_diag = centroid_similarity[~np.eye(centroid_similarity.shape[0], dtype=bool)]
        max_sim = float(off_diag.max())
    else:
        max_sim = None

    changes = model.singer_change_points(data)
    duration_min = float(data["duration_s"]) / 60.0
    rate = (len(changes) / duration_min) if duration_min > 0 else 0.0

    return {
        "song": song,
        "k": k,
        "silhouette": silhouette,
        "max_centroid_similarity": max_sim,
        "n_singer_change": len(changes),
        "singer_change_per_min": round(rate, 2),
    }


def _fmt(value, spec: str) -> str:
    return format(value, spec) if value is not None else "n/a"


def _fmt_row(row: dict, *, declared: bool) -> str:
    sil = _fmt(row["silhouette"], ">11.3f")
    sim = _fmt(row["max_centroid_similarity"], ">8.3f")
    prefix = f"  {row['song']:<38}"
    if declared:
        prefix += f"{row['declared']:>9}"
    return (
        f"{prefix}{row['k']:>8}{sil:>12}{sim:>9}"
        f"{row['n_singer_change']:>9}{row['singer_change_per_min']:>9.2f}"
    )


def calibration_report() -> str:
    """Declared `lead_voices` vs predicted `k` for every song in
    `singer_ground_truth.json`, plus predicted-only rows for every song that
    has a cache but no declared ground truth (the "unscoreable" block — the
    operator's own note in `singer_ground_truth.json` is why those songs are
    never scored, and this report must not guess a `lead_voices` value for
    them). Raises `FileNotFoundError` — does not skip — if a declared song's
    cache is missing."""
    gt = _load_ground_truth_map()

    header_declared = f"  {'song':<38}{'declared':>9}{'pred k':>8}{'silhouette':>12}{'max_sim':>9}{'changes':>9}{'per_min':>9}"
    header_undeclared = f"  {'song':<38}{'pred k':>8}{'silhouette':>12}{'max_sim':>9}{'changes':>9}{'per_min':>9}"

    scoreable, extra_speech = [], []
    for song, meta in gt.items():
        row = singer_count_row(song)
        row["declared"] = meta["lead_voices"]
        (extra_speech if meta["extra_speech"] else scoreable).append(row)

    lines = ["Singer Identity — singer-count calibration (k vs declared lead_voices)", "=" * 80]

    lines.append(f"\nScoreable ({len(scoreable)} songs, extra_speech=false; k == declared is a hit):")
    lines.append(header_declared)
    n_hit = 0
    for row in scoreable:
        hit = row["k"] == row["declared"]
        n_hit += int(hit)
        lines.append(_fmt_row(row, declared=True) + ("  OK" if hit else "  MISS"))
    if scoreable:
        lines.append(f"\naccuracy: {n_hit}/{len(scoreable)} = {n_hit / len(scoreable):.3f}")

    lines.append(
        f"\nextra_speech songs ({len(extra_speech)}; k >= declared is acceptable — "
        "non-lead speech may legitimately split its own cluster — k < declared "
        "is not; NOT folded into the accuracy above):"
    )
    lines.append(header_declared)
    for row in extra_speech:
        ok = row["k"] >= row["declared"]
        lines.append(_fmt_row(row, declared=True) + ("  OK" if ok else "  MISS"))

    unscoreable_songs = [
        s for s in paths.all_analysed_songs() if s not in gt and paths.cache_path(s).exists()
    ]
    lines.append(
        f"\nUnscoreable ({len(unscoreable_songs)}; no declared ground truth — "
        "predicted k only, for the operator's eye, never scored):"
    )
    lines.append(header_undeclared)
    for song in unscoreable_songs:
        lines.append(_fmt_row(singer_count_row(song), declared=False))

    return "\n".join(lines)


def write_calibration_report() -> None:
    paths.OUT_ROOT.mkdir(parents=True, exist_ok=True)
    text = calibration_report() + "\n"
    paths.singer_count_report_path().write_text(text)
    print(text)
