"""Score voice multiplicity against human hints with `voices` field.

Ground truth: entries in `reference/human/human_hints.json` that carry a
`"voices"` field whose value is `"solo"` or `"stacked"`.

Metric: mean multiplicity over solo spans, mean over stacked spans, and AUC of
stacked-vs-solo (higher multiplicity = stacked).
"""
from __future__ import annotations

import json

import numpy as np

from . import features as feat_mod
from . import paths


def _load_voice_hints(song: str) -> list[tuple[float, float, str]]:
    """Load (start, end, kind) tuples from human_hints.json where voices field exists."""
    hints_path = paths.hints_path(song)
    if not hints_path.exists():
        return []

    doc = json.loads(hints_path.read_text())
    hints = doc.get("human_hints", [])
    result = []
    for hint in hints:
        if "voices" in hint:
            voices = hint["voices"]
            if voices in ("solo", "stacked"):
                start = float(hint["start_time"])
                end = float(hint.get("end_time", start + 1.0))
                result.append((start, end, voices))
    return result


def _auc(a: np.ndarray, b: np.ndarray) -> float:
    """AUC as rank statistic: P(random a > random b)."""
    if len(a) == 0 or len(b) == 0:
        return np.nan
    b_sorted = np.sort(b)
    auc_vals = []
    for x in a:
        left = np.searchsorted(b_sorted, x, "left")
        right = np.searchsorted(b_sorted, x, "right")
        auc_vals.append((left + right) / (2.0 * len(b)))
    return float(np.mean(auc_vals))


def score_song(song: str) -> dict[str, any] | None:
    """Score one song. Returns None if no voice hints."""
    hints = _load_voice_hints(song)
    if not hints:
        return None

    cache = feat_mod.load_cache(song)
    times = np.array(cache["times"], dtype=float)
    multiplicity = np.array(cache["multiplicity"], dtype=float)
    present = np.array(cache["present"], dtype=bool)

    solo_mults = []
    stacked_mults = []

    for start, end, kind in hints:
        # Find frames in [start, end]
        mask = (times >= start) & (times < end) & present
        mults = multiplicity[mask]
        mults = mults[~np.isnan(mults)]

        if len(mults) > 0:
            if kind == "solo":
                solo_mults.extend(mults)
            elif kind == "stacked":
                stacked_mults.extend(mults)

    result = {}
    if solo_mults:
        result["mean_solo"] = float(np.mean(solo_mults))
    else:
        result["mean_solo"] = None

    if stacked_mults:
        result["mean_stacked"] = float(np.mean(stacked_mults))
    else:
        result["mean_stacked"] = None

    if solo_mults and stacked_mults:
        result["auc_stacked_vs_solo"] = _auc(np.array(stacked_mults), np.array(solo_mults))
    else:
        result["auc_stacked_vs_solo"] = None

    result["n_solo_samples"] = len(solo_mults)
    result["n_stacked_samples"] = len(stacked_mults)

    return result


def build_report() -> str:
    """Build a score report over all songs."""
    lines = [
        "Voice Multiplicity — mean scores vs human hints with `voices` field",
        "=" * 74,
        "",
    ]

    all_songs = paths.all_songs()
    for song in sorted(all_songs):
        result = score_song(song)
        if result is None:
            lines.append(f"{song}: no `voices` labels — unscored")
        else:
            lines.append(f"{song}")
            if result["mean_solo"] is not None:
                lines.append(f"  mean_solo:           {result['mean_solo']:7.3f} ({result['n_solo_samples']} samples)")
            else:
                lines.append(f"  mean_solo:           None (0 samples)")
            if result["mean_stacked"] is not None:
                lines.append(f"  mean_stacked:        {result['mean_stacked']:7.3f} ({result['n_stacked_samples']} samples)")
            else:
                lines.append(f"  mean_stacked:        None (0 samples)")
            if result["auc_stacked_vs_solo"] is not None:
                lines.append(f"  AUC(stacked vs solo): {result['auc_stacked_vs_solo']:7.3f}")
            else:
                lines.append(f"  AUC(stacked vs solo): N/A (need both classes)")
            lines.append("")

    return "\n".join(lines)


def write_report() -> None:
    paths.OUT_ROOT.mkdir(parents=True, exist_ok=True)
    text = build_report()
    (paths.OUT_ROOT / "score.txt").write_text(text)
    print(text)
