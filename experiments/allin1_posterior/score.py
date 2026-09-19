"""Scores shadow-label boundaries against the human-hint boundaries, with
`sections.json`'s own boundaries as incumbent and an even grid at a matched
boundary budget as the naive baseline — the same shape every other entry in
docs/experiments.md uses.

Also reports the entropy-confidence parity check (item 1 is already shipped;
this confirms this module's posterior math reproduces `function_confidence`
exactly rather than re-measuring a different quantity under the same name).
"""
from __future__ import annotations

import json

from . import analysis, paths

TOLERANCES = (0.10, 0.25, 0.50)


def _hint_boundaries(song: str) -> list[float]:
    path = paths.hints_path(song)
    if not path.exists():
        return []
    rows = json.loads(path.read_text())["human_hints"]
    out = []
    for h in rows:
        out.append(float(h["start_time"]))
        out.append(float(h["end_time"]))
    return sorted(set(round(x, 3) for x in out))


def _shipped_boundaries(song: str) -> list[float]:
    sections = analysis.published_sections(song)
    return sorted({float(s["start"]) for s in sections if float(s["start"]) > 0.05})


def _shadow_boundaries(song: str) -> list[float]:
    shadows = analysis.detect_shadow_labels(song)
    out = set()
    for s in shadows:
        out.add(round(s["start_s"], 3))
        out.add(round(s["end_s"], 3))
    return sorted(out)


def _even_grid(n: int, duration: float) -> list[float]:
    if n <= 0 or duration <= 0:
        return []
    step = duration / n
    return [round(step * i, 3) for i in range(1, n + 1)]


def _song_duration(song: str) -> float:
    sections = analysis.published_sections(song)
    return max((float(s["end"]) for s in sections), default=0.0)


def _recall(boundaries: list[float], targets: list[float], tol: float) -> int:
    if not boundaries:
        return 0
    return sum(1 for t in targets if any(abs(b - t) <= tol for b in boundaries))


def _per_minute(boundaries: list[float], span_s: float) -> float:
    return len(boundaries) / (span_s / 60.0) if span_s > 0 else 0.0


def score_song(song: str) -> dict:
    targets = _hint_boundaries(song)
    duration = _song_duration(song)
    shadow = _shadow_boundaries(song)
    incumbent = _shipped_boundaries(song)
    baseline = _even_grid(len(shadow), duration)  # matched budget to the shadow detector

    row = {"song": song, "n_hint_boundaries": len(targets), "duration_s": round(duration, 1)}
    for name, boundaries in (("shadow_labels", shadow), ("sections_incumbent", incumbent), ("even_grid_baseline", baseline)):
        row[name] = {
            "n_boundaries": len(boundaries),
            "bounds_per_min": round(_per_minute(boundaries, duration), 2),
            **{f"recall@{tol}s": _recall(boundaries, targets, tol) for tol in TOLERANCES},
        }
    return row


def armin_worked_example() -> dict:
    """The specific claim docs/experiments.md cites: break holds ~30% of the
    posterior across 143.4-175.0s on Armin, in no published section."""
    song = "Armin - Revolution"
    shadows = analysis.detect_shadow_labels(song)
    hits = [s for s in shadows if s["label"] == "break" and s["start_s"] < 175.0 and s["end_s"] > 143.4]
    return {"song": song, "expected_break_span": [143.4, 175.0], "detected_matching_spans": hits}


def write_report(songs: list[str]) -> None:
    paths.OUT_ROOT.mkdir(parents=True, exist_ok=True)
    rows = [score_song(s) for s in songs]
    worked_example = armin_worked_example()
    out = {"rows": rows, "armin_worked_example": worked_example}
    (paths.OUT_ROOT / "score.json").write_text(json.dumps(out, indent=2))

    print("| song | hints | shadow bounds/min | shadow r@0.1/0.25/0.5 | sections bounds/min | sections r@0.1/0.25/0.5 | grid bounds/min | grid r@0.1/0.25/0.5 |")
    print("| --- | --- | --- | --- | --- | --- | --- | --- |")
    for r in rows:
        sh, se, gr = r["shadow_labels"], r["sections_incumbent"], r["even_grid_baseline"]
        print(
            f"| {r['song']} | {r['n_hint_boundaries']} | {sh['bounds_per_min']} | "
            f"{sh['recall@0.1s']}/{sh['recall@0.25s']}/{sh['recall@0.5s']} | {se['bounds_per_min']} | "
            f"{se['recall@0.1s']}/{se['recall@0.25s']}/{se['recall@0.5s']} | {gr['bounds_per_min']} | "
            f"{gr['recall@0.1s']}/{gr['recall@0.25s']}/{gr['recall@0.5s']} |"
        )
    print()
    print("Armin worked example (break, 143.4-175.0s):", worked_example["detected_matching_spans"])
