"""Measure the vocal-phrase detector against the incumbent and a cheap baseline.

    question    Do vocal-phrase/breath/instrumental-gap edges land where the
                operator marks a hint boundary, more often than the shipped
                sections.json, at a comparable boundary budget?
    measurement Recall of every human_hints.json start/end instant at
                +-0.10 / 0.25 / 0.50 s, reported with boundaries/min.
    incumbent   `data/analysis/<song>/sections.json` boundaries.
    baseline    A fixed threshold on **mix** RMS (no stem, no hysteresis) —
                the do-nothing detector any stem-based method must beat.

Plus: phrase-edge MAE against `_test_song`'s (now word-level) Moises lyrics,
and a breath-threshold sweep table.
"""
from __future__ import annotations

import json
import statistics

import librosa
import numpy as np

from . import detector, paths

TOLERANCES = (0.10, 0.25, 0.50)


def _boundary_list(payload: dict) -> list[float]:
    out = []
    for p in payload["vocal_phrases"]:
        out.append(p["start"])
        out.append(p["end"])
    for g in payload["instrumental_gaps"]:
        out.append(g["start"])
        out.append(g["end"])
    return sorted(set(round(x, 3) for x in out))


def _hint_boundaries(song: str) -> list[float]:
    path = paths.hints_path(song)
    if not path.exists():
        return []
    rows = json.loads(path.read_text())["human_hints"]
    out = []
    for h in rows:
        out.append(float(h["start_time"]))
        out.append(float(h["end_time"]))
    return out


def _shipped_boundaries(song: str) -> list[float]:
    path = paths.shipped_sections_path(song)
    if not path.exists():
        return []
    rows = json.loads(path.read_text())
    return [float(r["start"]) for r in rows if float(r["start"]) > 0.05]


def _recall(boundaries: list[float], targets: list[float], tol: float) -> int:
    if not boundaries:
        return 0
    return sum(1 for t in targets if any(abs(b - t) <= tol for b in boundaries))


def _per_minute(boundaries: list[float], span: float) -> float:
    return len(boundaries) / (span / 60.0) if span > 0 else 0.0


def _mix_rms_baseline(song: str, threshold_ratio: float = 1.15) -> list[float]:
    """Fixed threshold on mix RMS, no hysteresis, no stem. The cheap baseline."""
    y, sr = librosa.load(str(paths.mix_audio_path(song)), sr=None, mono=True)
    hop = detector.HOP_LENGTH
    rms = librosa.feature.rms(y=y, frame_length=detector.FRAME_LENGTH, hop_length=hop)[0]
    times = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=hop)
    thresh = float(np.median(rms)) * threshold_ratio
    active = rms >= thresh
    spans = detector._runs(active, times.tolist())
    out = []
    for s, e in spans:
        if e - s >= detector.MIN_PHRASE_S:
            out.append(round(s, 3))
            out.append(round(e, 3))
    return sorted(set(out))


def gold_table() -> str:
    lines = []
    total_hints = 0
    agg = {"vocal_phrases": {t: 0 for t in TOLERANCES}, "shipped sections.json": {t: 0 for t in TOLERANCES},
           "mix-RMS baseline": {t: 0 for t in TOLERANCES}}
    agg_bpm = {"vocal_phrases": [], "shipped sections.json": [], "mix-RMS baseline": []}

    for song in paths.GOLD_SONGS:
        env = detector.load_envelope(song)
        derived = detector.derive_phrases(env)
        payload = {"vocal_phrases": derived["vocal_phrases"], "instrumental_gaps": derived["instrumental_gaps"]}
        vp_bounds = _boundary_list(payload)
        shipped = _shipped_boundaries(song)
        baseline = _mix_rms_baseline(song)
        hints = _hint_boundaries(song)
        span = env.times[-1] if env.times else 0.0

        lines.append(f"\n{song}  ({len(hints)} hint boundaries, span {span:.1f}s)")
        header = f"  {'method':<26}" + "".join(f"{'+-' + str(t):>8}" for t in TOLERANCES) + f"{'bounds/min':>12}"
        lines.append(header)
        for name, bounds in (
            ("vocal_phrases", vp_bounds),
            ("shipped sections.json", shipped),
            ("mix-RMS baseline", baseline),
        ):
            row = f"  {name:<26}"
            for t in TOLERANCES:
                hit = _recall(bounds, hints, t)
                agg[name][t] += hit
                row += f"{hit:>5}/{len(hints):<2}"
            bpm = _per_minute(bounds, span)
            agg_bpm[name].append(bpm)
            row += f"{bpm:>12.2f}"
            lines.append(row)
        total_hints += len(hints)

    lines.append(f"\nAggregate across {len(paths.GOLD_SONGS)} songs, {total_hints} hint boundaries:")
    header = f"  {'method':<26}" + "".join(f"{'+-' + str(t):>8}" for t in TOLERANCES) + f"{'avg bounds/min':>16}"
    lines.append(header)
    for name in agg:
        row = f"  {name:<26}"
        for t in TOLERANCES:
            row += f"{agg[name][t]:>5}/{total_hints:<2}"
        row += f"{statistics.mean(agg_bpm[name]):>16.2f}"
        lines.append(row)
    return "\n".join(lines)


def breath_sweep_table() -> str:
    """Phrase-edge MAE against _test_song's word-level Moises lyrics, per breath_s."""
    song = paths.WORD_LEVEL_LYRICS_SONG
    lyrics = json.loads(paths.lyrics_path(song).read_text())
    lines_by_id: dict[int, list[dict]] = {}
    for tok in lyrics:
        lines_by_id.setdefault(tok["line_id"], []).append(tok)
    line_edges = []
    for lid, toks in sorted(lines_by_id.items()):
        words = [t for t in toks if not t["text"].startswith("<")]
        if not words:
            continue
        line_edges.append((min(t["start"] for t in words), max(t["end"] for t in words)))

    env = detector.load_envelope(song)
    out = ["breath_s sweep on _test_song, MAE against word-level line on/off:", ""]
    out.append(f"  {'breath_s':<10}{'phrases':>10}{'onset MAE':>12}{'offset MAE':>12}")
    for breath_s in (0.3, 0.5, 0.7, 1.0):
        derived = detector.derive_phrases(env, breath_s=breath_s)
        phrase_starts = [p["start"] for p in derived["vocal_phrases"]]
        phrase_ends = [p["end"] for p in derived["vocal_phrases"]]
        onset_errs = [min(abs(s - le[0]) for s in phrase_starts) for le in line_edges if phrase_starts]
        offset_errs = [min(abs(e - le[1]) for e in phrase_ends) for le in line_edges if phrase_ends]
        onset_mae = statistics.mean(onset_errs) if onset_errs else float("nan")
        offset_mae = statistics.mean(offset_errs) if offset_errs else float("nan")
        out.append(f"  {breath_s:<10}{len(derived['vocal_phrases']):>10}{onset_mae:>12.3f}{offset_mae:>12.3f}")
    return "\n".join(out)


def write_report() -> None:
    paths.OUT_ROOT.mkdir(parents=True, exist_ok=True)
    text = "Vocal phrase blocks — score vs incumbent + mix-RMS baseline\n" + "=" * 60 + "\n"
    text += gold_table() + "\n\n" + breath_sweep_table() + "\n"
    (paths.OUT_ROOT / "score.txt").write_text(text)
    print(text)
