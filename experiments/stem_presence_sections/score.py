"""Boundary F1 @ +-1.0 s vs `reference/human/segments.json`, on
`truth_common.structure.SCORING_CORPUS` (ayuni, Cinderella - Ella Lee,
_test_song, What a Feeling - Courtney Storm).

Circularity rule (structure.py's own docstring): never score the published
`sections.json`. So the incumbent here is allin1's own RAW boundaries
(`artifacts/allin1/raw.json`), not the fused `sections.json`.

Four methods, all on the same corpus:
  1. this experiment       — `export.build_sections` (recomputed fresh, no
                              file write, so `score` never depends on
                              `reference/proposals/` having been written).
  2. incumbent allin1 raw  — `artifacts/allin1/raw.json` segment starts.
  3. baseline even 8-bar   — every 8th downbeat's time, no signal at all.
  4. incumbent arrangement_state — top-level `arrangement_state.json` block starts.
"""
from __future__ import annotations

import json

from experiments.truth_common import structure

from . import bars as bar_mod
from . import export as export_mod
from . import paths

METHOD_LABELS = {
    "stem_presence_sections": "this experiment — stem presence sections",
    "incumbent_allin1_raw": "incumbent — allin1 raw segments",
    "baseline_even_8bar": "baseline — even 8-bar grid",
    "incumbent_arrangement_state": "incumbent — arrangement_state.json blocks",
}


def _predicted_this_experiment(song: str) -> list[dict]:
    sections, _classifications, _cache = export_mod.build_sections(song)
    # boundaries are section starts after the first (song start is not a
    # boundary — matches structure.py's own `[1:]` truth convention)
    return [{"time": s.start_s, "label": None} for s in sections[1:]]


def _predicted_allin1_raw(song: str) -> list[dict]:
    segments = json.loads(paths.allin1_raw_path(song).read_text())["segments"]
    return [{"time": float(s["start"]), "label": s.get("label")} for s in segments[1:]]


def _predicted_even_8bar(song: str) -> list[dict]:
    grid = bar_mod.load_bar_grid(song)
    return [{"time": b.start, "label": None} for b in grid if (b.bar - 1) % 8 == 0 and b.bar > 1]


def _predicted_arrangement_state(song: str) -> list[dict]:
    blocks = json.loads(paths.arrangement_state_path(song).read_text())["blocks"]
    return [{"time": float(b["start_s"]), "label": None} for b in blocks[1:]]


_PREDICTORS = {
    "stem_presence_sections": _predicted_this_experiment,
    "incumbent_allin1_raw": _predicted_allin1_raw,
    "baseline_even_8bar": _predicted_even_8bar,
    "incumbent_arrangement_state": _predicted_arrangement_state,
}


def score_method(method: str) -> list[structure.StructureScore]:
    predictor = _PREDICTORS[method]
    scores = []
    for song in structure.SCORING_CORPUS:
        predicted = predictor(song)
        scores.append(structure.score_structure(song, predicted))
    return scores


def write_report() -> None:
    paths.OUT_ROOT.mkdir(parents=True, exist_ok=True)
    summary_lines = [
        "Stem Presence Sections — boundary F1 @ +-1.0 s vs reference/human/segments.json",
        "pooled corpus row per method (per-song rows in each method's own out/score_<method>.txt)",
        "=" * 88,
    ]
    for method, label in METHOD_LABELS.items():
        scores = score_method(method)
        out_path = paths.OUT_ROOT / f"score_{method}.txt"
        structure.write_report(out_path, scores)
        row = structure.corpus_row(scores)
        summary_lines.append(
            f"  {label:<44} P={row['precision']!s:>6} R={row['recall']!s:>6} F1={row['f1']:.4f}"
            f"  pred={row['n_predicted']} truth={row['n_truth']}"
        )
    summary = "\n".join(summary_lines) + "\n"
    (paths.OUT_ROOT / "score_summary.txt").write_text(summary)
    print(summary)
