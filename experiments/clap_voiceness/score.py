"""Score this candidate against the three shared incumbents
(`voiceness_common.incumbents`) via the shared scorer
(`voiceness_common.scorer`), at a matched firing budget (bounds/min reported
beside every rate, never compared alone).

**Frame voiceness accuracy and false-vocal rate are the scored metrics for
this candidate.** Boundary F1 is computed for every candidate (so the table
stays one comparable shape) but is explicitly NOT a scored comparison for
`clap_voiceness` — a 5s CLAP analysis window cannot time a phrase edge to the
0.25/0.5/1.0s tolerances `voiceness_common.scorer` uses. Every
`clap_voiceness` row's `boundary_f1` numbers are marked `boundary_f1_scored:
false` and the printed table stars them, so a reader cannot mistake the
column for a claim this candidate makes.

**No ground truth exists yet.** Same finding as items 3-4: every song in
`paths.SCORING_CORPUS` has zero `type == "vocal"` rows in
`reference/human/human_hints.json` in this environment. So `false_vocal_rate`
against an empty marked-span set is mathematically "fraction of frames this
candidate calls voiced" — reported honestly below, `is_proxy_no_ground_truth`
flagged per row, not dressed up as the validated metric. Re-running `score`
after the operator marks `type: "vocal"` spans recomputes the real number
with no code change.
"""
from __future__ import annotations

import json
import statistics

from experiments.voiceness_common import incumbents, scorer as voiceness_scorer
from experiments.voiceness_common.schema import frames_as_tuples, phrases_as_dicts

from . import model, paths

CANDIDATES = ("clap_voiceness", "arrangement_state", "vocal_phrases", "mix_rms_baseline")


def _candidate_frames_phrases(name: str, song: str):
    if name == "clap_voiceness":
        data = model.load(song)
        frames = [(float(t), float(v)) for t, v in zip(data["times"], data["voiceness"])]
        phrases = model.derive_vocal_phrases(data["times"], data["voiceness"], data["confidence"])
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


def score_song(song: str) -> dict:
    hints_path = paths.hints_path(song)
    marked_spans: list[tuple[float, float]] = []
    if hints_path.exists():
        marked_spans = voiceness_scorer.marked_vocal_spans(json.loads(hints_path.read_text()))

    out = {"song": song, "n_marked_vocal_spans": len(marked_spans), "candidates": {}}
    for name in CANDIDATES:
        frames, phrases = _candidate_frames_phrases(name, song)
        duration = max((t for t, _ in frames), default=0.0)
        result = voiceness_scorer.score(frames, phrases, marked_spans, duration_s=duration)
        out["candidates"][name] = {
            "frame_accuracy": round(result.frame_accuracy, 4),
            "false_vocal_rate": round(result.false_vocal_rate, 4),
            "bounds_per_min": round(result.bounds_per_min, 2),
            "boundary_f1": {str(t): round(b.f1, 3) for t, b in result.boundary.items()},
            # only clap_voiceness's own boundary read is unscored — the
            # incumbents keep whatever standing they already have elsewhere.
            "boundary_f1_scored": name != "clap_voiceness",
            "is_proxy_no_ground_truth": len(marked_spans) == 0,
        }
    return out


def gold_table(songs: list[str]) -> str:
    lines = []
    agg_acc: dict[str, list[float]] = {c: [] for c in CANDIDATES}
    agg_false_vocal: dict[str, list[float]] = {c: [] for c in CANDIDATES}
    agg_bpm: dict[str, list[float]] = {c: [] for c in CANDIDATES}

    for song in songs:
        row = score_song(song)
        lines.append(f"\n{song}  ({row['n_marked_vocal_spans']} marked vocal spans)")
        header = (
            f"  {'candidate':<20}{'frame_acc':>11}{'false_vocal_rate':>18}"
            f"{'bounds/min':>12}{'F1@0.5s':>10}"
        )
        lines.append(header)
        for name in CANDIDATES:
            c = row["candidates"][name]
            f1_str = f"{c['boundary_f1'].get('0.5', 0.0):.3f}"
            if not c["boundary_f1_scored"]:
                f1_str += "*"
            lines.append(
                f"  {name:<20}{c['frame_accuracy']:>11.4f}{c['false_vocal_rate']:>18.4f}"
                f"{c['bounds_per_min']:>12.2f}{f1_str:>10}"
                f"{'  (proxy — no ground truth)' if c['is_proxy_no_ground_truth'] else ''}"
            )
            agg_acc[name].append(c["frame_accuracy"])
            agg_false_vocal[name].append(c["false_vocal_rate"])
            agg_bpm[name].append(c["bounds_per_min"])

    lines.append(
        "\n* clap_voiceness's F1@0.5s is REPORTED, NOT SCORED — a 5s CLAP "
        "window cannot time a phrase edge to sub-second tolerance. Frame "
        "voiceness accuracy and false_vocal_rate are the metrics this "
        "candidate is actually measured on."
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
    text = "CLAP voiceness — vs arrangement_state / vocal_phrases / mix-RMS\n" + "=" * 66 + "\n"
    text += gold_table(songs) + "\n"
    paths.score_out_path().write_text(text)
    print(text)
