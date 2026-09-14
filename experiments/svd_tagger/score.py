"""Score BOTH channels (`svd_tagger_stem`, `svd_tagger_mix`) against the
three shared incumbents (`truth_common.vocal_presence.incumbents`) via the shared
scorer (`truth_common.vocal_presence.scorer`), at a matched firing budget (bounds/min
reported beside every rate, never compared alone) — same shape as
`experiments/clap_voiceness/score.py`.

**Frame voiceness accuracy and false-vocal rate are the scored metrics for
both channels.** Boundary F1 is computed (so the table stays one comparable
shape) but is explicitly NOT a scored comparison here either — a 5s PANNs
window cannot time a phrase edge to sub-second tolerance, same reasoning as
`clap_voiceness`. Every `svd_tagger_*` row's `boundary_f1` numbers are
marked `boundary_f1_scored: false` and the printed table stars them.

**`_p98` rows** are the same two channels after `model.rescale_per_song`
(divide by the song's own p98). Item 6's narrow question: does calibration
alone make SVD competitive, given its within-song ranking is already good?

**Three-class ground truth** (`truth_common.vocal_presence.scorer.ground_truth`,
declared per-song in `truth_common.vocal_presence/vocal_ground_truth.json`): positive
(`type: "vocal"`), residual (excluded from every scored metric, its firing
rate reported separately) and negative (hard error) spans, resolved against
an `evaluable` region — everything else is unreviewed and excluded entirely.
A song with a hint that is neither `type: "vocal"` nor classified in the map
raises `ValueError` rather than being silently treated as a negative or
skipped.

`is_proxy_no_ground_truth` (kept per row) now means "zero evaluable
non-residual frames".
"""
from __future__ import annotations

import json
import statistics

from experiments.truth_common.vocal_presence import incumbents, scorer as voiceness_scorer
from experiments.truth_common.vocal_presence.schema import frames_as_tuples, phrases_as_dicts

from . import model, paths

CANDIDATES = (
    "svd_tagger_stem",
    "svd_tagger_mix",
    "svd_tagger_stem_p98",
    "svd_tagger_mix_p98",
    "arrangement_state",
    "vocal_phrases",
    "mix_rms_baseline",
)


def _candidate_frames_phrases(name: str, song: str):
    if name.startswith("svd_tagger_"):
        data = model.load(song)
        channel = "stem" if name.startswith("svd_tagger_stem") else "mix"
        times = data[f"{channel}_times"]
        voiceness = data[f"{channel}_voiceness"]
        # `_p98` rows: the same scores divided by the song's own p98 (item 6's rescale test)
        if name.endswith("_p98"):
            voiceness = model.rescale_per_song(voiceness)
        frames = [(float(t), float(v)) for t, v in zip(times, voiceness)]
        phrases = model.derive_vocal_phrases(times, voiceness)
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
            "boundary_f1_scored": not name.startswith("svd_tagger_"),
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
            f1_str = f"{c['boundary_f1'].get('0.5', 0.0):.3f}"
            if not c["boundary_f1_scored"]:
                f1_str += "*"
            lines.append(
                f"  {name:<20}{c['frame_accuracy']:>11.4f}{c['false_vocal_rate']:>18.4f}"
                f"{c['residual_firing_rate']:>16.4f}{c['bounds_per_min']:>12.2f}{f1_str:>10}"
                f"{'  (proxy — no evaluable ground truth)' if c['is_proxy_no_ground_truth'] else ''}"
            )
            agg_acc[name].append(c["frame_accuracy"])
            agg_false_vocal[name].append(c["false_vocal_rate"])
            agg_bpm[name].append(c["bounds_per_min"])

    lines.append(
        "\n* every svd_tagger_* row's F1@0.5s is REPORTED, NOT SCORED — a 5s "
        "PANNs window cannot time a phrase edge to sub-second tolerance. "
        "Frame voiceness accuracy and false_vocal_rate are the metrics "
        "these candidates are actually measured on."
    )
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
    text = "SVD Tagger (PANNs Singing) — stem vs mix, vs arrangement_state / vocal_phrases / mix-RMS\n" + "=" * 88 + "\n"
    text += gold_table(songs) + "\n"
    paths.score_out_path().write_text(text)
    print(text)
