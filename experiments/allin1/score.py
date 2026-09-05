"""Measure the proposal against the incumbent and against a cheap baseline.

The experiment method (docs/experiments.md): an experiment states a question and a measurement up front and
scores against the incumbent *and* a baseline. Here:

    question    Do allin1's named section boundaries land where a human marked a
                drop, more often than the segmentation the pipeline ships?
    measurement Recall of the 7 hand-placed `drop impact` instants at +-0.5 /
                1.0 / 2.0 s, at a comparable boundary budget (boundaries/min).
    incumbent   `data/analysis/<song>/sections.json` boundaries.
    baseline    A fixed grid every N seconds, matched to the same budget. It is
                the honest floor: any method that cannot beat evenly-spaced
                guesses has found nothing.

Seven positives across four songs is a small sample and every number here should
be read as such. It is enough to separate "at chance" from "not at chance", and
not enough to rank two working methods.
"""
from __future__ import annotations

import json
import statistics

from . import features, model
from .paths import GOLD_SONGS, all_songs, shipped_sections_path

TOLERANCES = (0.5, 1.0, 2.0)


def _recall(boundaries: list[float], impacts: list[float], tol: float) -> int:
    return sum(1 for i in impacts if any(abs(b - i) <= tol for b in boundaries))


def _per_minute(boundaries: list[float], span: float) -> float:
    return len(boundaries) / (span / 60.0) if span > 0 else 0.0


def shipped_boundaries(song: str) -> list[float]:
    path = shipped_sections_path(song)
    if not path.exists():
        return []
    rows = json.loads(path.read_text())
    return [float(r["start"]) for r in rows if float(r["start"]) > 0.05]


def even_grid(span: float, count: int) -> list[float]:
    """`count` evenly spaced instants across the song — the do-nothing baseline."""
    if count <= 0 or span <= 0:
        return []
    step = span / (count + 1)
    return [step * (i + 1) for i in range(count)]


def gold_table() -> str:
    rows: dict[str, dict[str, list[float]]] = {}
    impacts: dict[str, list[float]] = {}
    spans: dict[str, float] = {}

    for song in GOLD_SONGS:
        raw = model.load(song)
        derived = features.derive(song, raw)
        span = derived["sections"][-1]["end_s"] if derived["sections"] else 0.0
        spans[song] = span
        impacts[song] = features.human_impacts(song)
        allin1_bounds = [t["time_s"] for t in derived["transitions"]]
        phrase_bounds = [p["start_s"] for p in derived["phrases"] if p["start_s"] > 0.05]
        shipped = shipped_boundaries(song)
        rows[song] = {
            "allin1 section transitions": allin1_bounds,
            "allin1 phrase edges (all segments)": phrase_bounds,
            "shipped sections.json": shipped,
            "even grid (= shipped budget)": even_grid(span, len(shipped)),
        }

    methods = list(next(iter(rows.values())).keys())
    total = sum(len(v) for v in impacts.values())
    lines = [f"Gold set: {len(GOLD_SONGS)} songs, {total} hand-placed drop impacts.", ""]
    header = f"{'method':<36}" + "".join(f"{'+-' + str(t):>9}" for t in TOLERANCES) + f"{'bounds/min':>12}"
    lines += [header, "-" * len(header)]
    for method in methods:
        cells = []
        for tol in TOLERANCES:
            hits = sum(_recall(rows[s][method], impacts[s], tol) for s in GOLD_SONGS)
            cells.append(f"{hits}/{total}")
        rate = statistics.mean(_per_minute(rows[s][method], spans[s]) for s in GOLD_SONGS)
        lines.append(f"{method:<36}" + "".join(f"{c:>9}" for c in cells) + f"{rate:>12.1f}")

    lines += ["", "Per song, nearest allin1 transition to each impact:", ""]
    for song in GOLD_SONGS:
        bounds = rows[song]["allin1 section transitions"]
        for impact in impacts[song]:
            if bounds:
                nearest = min(bounds, key=lambda b: abs(b - impact))
                lines.append(f"  {song:<40} impact {impact:7.2f}  nearest {nearest:7.2f}"
                             f"  ({nearest - impact:+.2f}s)")
            else:
                lines.append(f"  {song:<40} impact {impact:7.2f}  no transitions")
    return "\n".join(lines)


def stability_table(runs: list[dict]) -> str:
    """How much does allin1 change its mind between two runs on the same audio?

    Written from `out/stability.json`, which `run.py stability` produces by
    calling the model repeatedly. This is not a curiosity: the determinism rule makes
    byte-identical output for the same input a condition of being in `src/`, and
    a segmentation that moves between runs cannot anchor a light show.
    """
    lines = ["Run-to-run stability of allin1 on identical audio.", ""]
    for entry in runs:
        lines.append(f"  {entry['song']}")
        for i, sequence in enumerate(entry["label_sequences"], 1):
            lines.append(f"    run {i}: {' '.join(sequence)}")
        agree = entry["boundary_agreement"]
        lines.append(f"    boundaries matched across all runs (+-0.5s): "
                     f"{agree['matched']}/{agree['union']}")
        lines.append("")
    return "\n".join(lines)


def corpus_table(songs: list[str] | None = None) -> str:
    songs = songs or model.cached_songs(all_songs())
    lines = [f"Labelling health over {len(songs)} songs.", ""]
    header = (f"{'song':<40}{'sections':>9}{'labels':>8}{'dominant':>10}"
              f"{'share':>8}  status")
    lines += [header, "-" * len(header)]
    degenerate = []
    for song in songs:
        derived = features.derive(song, model.load(song))
        lab = derived["labelling"]
        lines.append(f"{song:<40}{len(derived['sections']):>9}{lab['distinct_labels']:>8}"
                     f"{str(lab['dominant_label']):>10}{lab['dominant_share']:>8.2f}"
                     f"  {lab['status']}")
        if lab["status"] != "ok":
            degenerate.append(f"{song} ({lab['reason']})")
    lines += ["", f"Degenerate on {len(degenerate)}/{len(songs)}:"]
    lines += [f"  {row}" for row in degenerate] or ["  none"]
    return "\n".join(lines)


def grid_table(songs: list[str] | None = None) -> str:
    """Does allin1's own beat grid agree with the one the pipeline already ships?

    The offset is reported as a fraction of a beat period, because that is what
    separates the two failure modes. A ratio near 0 means the grids agree; near
    0.5 means allin1 is a *half beat out of phase* — sitting on the offbeat, not
    wrong about the tempo; a beat count that is half essentia's means allin1
    halved the tempo outright.
    """
    songs = songs or model.cached_songs(all_songs())
    lines = ["allin1 beat grid vs. the essentia grid the pipeline already ships.", ""]
    header = (f"{'song':<40}{'bpm':>6}{'beats':>7}{'ess beats':>11}"
              f"{'median |err|':>14}{'of a beat':>11}  verdict")
    lines += [header, "-" * len(header)]
    for song in songs:
        raw = model.load(song)
        beats = raw["beats"]
        agree = features.beat_agreement(beats, features.essentia_beats(song))
        if not agree["comparable"] or len(beats) < 3:
            lines.append(f"{song:<40}{raw['bpm']:>6}  no comparable essentia grid")
            continue
        period = statistics.median(b - a for a, b in zip(beats, beats[1:]))
        ratio = agree["median_abs_offset_s"] / period if period else 0.0
        ess_count = agree["essentia_beat_count"]
        if ess_count and len(beats) < ess_count * 0.7:
            verdict = "HALF TEMPO"
        elif ratio > 0.3:
            verdict = "half-beat phase offset"
        elif ratio > 0.1:
            verdict = "drifting"
        else:
            verdict = "agrees"
        lines.append(f"{song:<40}{raw['bpm']:>6}{len(beats):>7}{ess_count:>11}"
                     f"{agree['median_abs_offset_s']:>14.3f}{ratio:>11.2f}  {verdict}")
    return "\n".join(lines)
