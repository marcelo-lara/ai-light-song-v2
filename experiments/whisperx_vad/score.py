"""Score this candidate against the three shared incumbents
(`voiceness_common.incumbents`) via the shared scorer
(`voiceness_common.scorer`), at a matched firing budget (bounds/min reported
beside every F1, never compared on F1 alone).

**Unlike `clap_voiceness`/`svd_tagger` (items 5/6), boundary F1 IS scored
here, not just reported.** whisperX's VAD front-end reports real sub-second
phrase onsets/offsets (its segmentation model's native ~17ms frames,
`Binarize`d with library-default hysteresis) rather than a 5s clip-level
window, so `voiceness_common.scorer`'s 0.25/0.5/1.0s tolerances are a
legitimate test of this candidate, the same way they are for `vocal_voiceness`
(item 4).

**No ground truth exists yet** — same finding as items 3-6: every song in
`paths.SCORING_CORPUS` has zero `type == "vocal"` rows in
`reference/human/human_hints.json` in this environment, so `false_vocal_rate`
is a firing-rate proxy, `is_proxy_no_ground_truth` flagged per row, not the
validated metric the plan specifies. Re-running `score` after the operator
marks `type: "vocal"` spans on `ayuni` recomputes the real number with no
code change.
"""
from __future__ import annotations

import json
import statistics

from experiments.voiceness_common import incumbents, scorer as voiceness_scorer
from experiments.voiceness_common.schema import frames_as_tuples, phrases_as_dicts

from . import model, paths

CANDIDATES = ("whisperx_vad", "arrangement_state", "vocal_phrases", "mix_rms_baseline")


def _candidate_frames_phrases(name: str, song: str):
    if name == "whisperx_vad":
        data = model.load(song)
        frames = [(float(t), float(v)) for t, v in zip(data["times"], data["voiceness"])]
        phrases = model.vocal_phrases(data)
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
            "is_proxy_no_ground_truth": len(marked_spans) == 0,
        }
    return out


def gold_table(songs: list[str]) -> str:
    lines = []
    agg_false_vocal: dict[str, list[float]] = {c: [] for c in CANDIDATES}
    agg_bpm: dict[str, list[float]] = {c: [] for c in CANDIDATES}

    for song in songs:
        row = score_song(song)
        lines.append(f"\n{song}  ({row['n_marked_vocal_spans']} marked vocal spans)")
        header = f"  {'candidate':<20}{'false_vocal_rate':>18}{'bounds/min':>12}{'F1@0.5s':>10}"
        lines.append(header)
        for name in CANDIDATES:
            c = row["candidates"][name]
            lines.append(
                f"  {name:<20}{c['false_vocal_rate']:>18.4f}{c['bounds_per_min']:>12.2f}"
                f"{c['boundary_f1'].get('0.5', 0.0):>10.3f}"
                f"{'  (proxy — no ground truth)' if c['is_proxy_no_ground_truth'] else ''}"
            )
            agg_false_vocal[name].append(c["false_vocal_rate"])
            agg_bpm[name].append(c["bounds_per_min"])

    lines.append(f"\nAggregate across {len(songs)} songs:")
    header = f"  {'candidate':<20}{'avg false_vocal_rate':>22}{'avg bounds/min':>16}"
    lines.append(header)
    for name in CANDIDATES:
        lines.append(
            f"  {name:<20}{statistics.mean(agg_false_vocal[name]):>22.4f}"
            f"{statistics.mean(agg_bpm[name]):>16.2f}"
        )
    return "\n".join(lines)


def write_report(songs: list[str] | None = None) -> None:
    songs = songs if songs else paths.SCORING_CORPUS
    paths.OUT_ROOT.mkdir(parents=True, exist_ok=True)
    text = "WhisperX VAD — vs arrangement_state / vocal_phrases / mix-RMS\n" + "=" * 66 + "\n"
    text += gold_table(songs) + "\n"
    paths.score_out_path().write_text(text)
    print(text)
