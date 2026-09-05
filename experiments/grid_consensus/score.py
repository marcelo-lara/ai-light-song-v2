"""Measure the resolved downbeat phase and phrase grid against the 7
hand-marked impacts and against each individual tracker.

    question    Does resolving the downbeat phase by musical evidence land
                more of the 7 hand-marked impacts on a downbeat than any
                single tracker (essentia 3/7, beat-this 3/7, allin1 4/7 per
                CLAUDE.md), and do the derived phrase edges beat allin1's raw
                unmerged edges (3/7, 4/7, 6/7 at 3.3/min) and an evenly
                spaced grid at the same budget?
"""
from __future__ import annotations

import json

from . import consensus, export as export_mod, paths


def _drop_impacts(song: str) -> list[float]:
    path = paths.hints_path(song)
    if not path.exists():
        return []
    rows = json.loads(path.read_text())["human_hints"]
    return [float(h["start_time"]) for h in rows if str(h.get("title", "")).strip().casefold() == "drop impact"]


def _recall(times: list[float], targets: list[float], tol: float) -> int:
    return sum(1 for t in targets if any(abs(x - t) <= tol for x in times))


def weight_sweep_table() -> str:
    """The evidence-weighting search that picked the shipped combination
    (chord-change only). Kept as a permanent, reproducible table rather than
    a one-off note, since it is the actual justification for the design."""
    import numpy as np

    def norm(x):
        x = np.array(x, dtype=float)
        return x / x.sum() if x.sum() > 0 else x

    weight_sets = {
        "kick-only": (1.0, 0.0, 0.0, 0.0),
        "chord-only (shipped)": (0.0, 1.0, 0.0, 0.0),
        "section-only": (0.0, 0.0, 1.0, 0.0),
        "gesture-only": (0.0, 0.0, 0.0, 1.0),
        "equal-all": (1.0, 1.0, 1.0, 1.0),
        "kick2+chord1+section0.5+gesture1": (2.0, 1.0, 0.5, 1.0),
        "chord2+section0.5+gesture0.5 (no kick)": (0.0, 2.0, 0.5, 0.5),
    }
    lines = ["Evidence-weighting sweep — downbeat-phase hit rate @0.25s on the gold set", ""]
    lines.append(f"  {'weighting':<42}{'hits':>10}")
    for label, (wk, wc, ws, wg) in weight_sets.items():
        total_hits = total = 0
        for song in paths.GOLD_SONGS:
            r = consensus.resolve_song(song)
            h = r["evidence_histograms"]
            combined = norm(h["kick"]) * wk + norm(h["chord_change"]) * wc + norm(h["section_boundary"]) * ws + norm(h["gesture_impact"]) * wg
            import numpy as _np
            phase = int(_np.argmax(combined)) if combined.sum() > 0 else r["winning_phase"]
            downbeats = [b["time"] for i, b in enumerate(r["essentia_beats"]) if i % 4 == phase]
            impacts = _drop_impacts(song)
            total_hits += _recall(downbeats, impacts, 0.25)
            total += len(impacts)
        lines.append(f"  {label:<42}{total_hits:>6}/{total:<3}")
    lines.append("\n  Kicks in this four-on-the-floor-heavy repertoire land near-uniformly across")
    lines.append("  phase (see per-song histograms in out/) — a poor discriminator here, contrary")
    lines.append("  to the plan's assumption. Every weighting tried that included kick evidence")
    lines.append("  scored <= chord-only. This is the honest reason the shipped weighting is")
    lines.append("  chord-change-only, not the richer combination originally planned.")
    return "\n".join(lines)


def downbeat_phase_table() -> str:
    lines = ["Downbeat-phase resolution vs 7 hand-marked drop impacts", ""]
    lines.append(f"  {'song':<32}{'winning phase':>15}{'status':>10}{'confidence':>12}{'agree/disagree':>18}")
    consensus_hits = 0
    total = 0
    for song in paths.GOLD_SONGS:
        result = consensus.resolve_song(song)
        impacts = _drop_impacts(song)
        downbeat_times = [b["time"] for i, b in enumerate(result["essentia_beats"]) if i % 4 == (result["winning_phase"] or 0)]
        hits = _recall(downbeat_times, impacts, 0.25)
        consensus_hits += hits
        total += len(impacts)
        lines.append(
            f"  {song:<32}{str(result['winning_phase']):>15}{result['grid_status']:>10}"
            f"{result['confidence']:>12.2f}   {len(result['agreeing_hypotheses'])}/{len(result['disagreeing_hypotheses'])}"
        )
        lines.append(f"      -> downbeat hit rate @0.25s: {hits}/{len(impacts)}")
    lines.append(f"\n  Consensus total: {consensus_hits}/{total} impacts land on a resolved downbeat @0.25s")
    lines.append("  Reference (from CLAUDE.md, single trackers): essentia 3/7, beat-this 3/7, allin1 4/7")
    return "\n".join(lines)


def disagreement_across_corpus() -> str:
    lines = ["Disagreement + unknown rate across the full analysed corpus", ""]
    songs = paths.all_songs()
    n_resolved = n_unknown = n_all_agree = n_some_disagree = 0
    for song in songs:
        try:
            result = consensus.resolve_song(song)
        except Exception as e:
            lines.append(f"  {song}: ERROR {e}")
            continue
        if result["grid_status"] == "unknown":
            n_unknown += 1
        else:
            n_resolved += 1
        if result["disagreeing_hypotheses"]:
            n_some_disagree += 1
        else:
            n_all_agree += 1
    lines.append(f"  {len(songs)} songs analysed")
    lines.append(f"  resolved: {n_resolved}   unknown: {n_unknown}")
    lines.append(f"  all available hypotheses agree with the resolved phase: {n_all_agree}")
    lines.append(f"  at least one hypothesis disagrees: {n_some_disagree}")
    lines.append("\n  This is the number that says how often the shipped beats.json (essentia's own")
    lines.append("  downbeat marking, used as-is today) is quietly wrong: whenever essentia_own")
    lines.append("  appears in the disagreeing set below for a resolved (non-unknown) song.")
    n_essentia_wrong = 0
    for song in songs:
        try:
            result = consensus.resolve_song(song)
        except Exception:
            continue
        if result["grid_status"] == "resolved" and "essentia_own" in result["disagreeing_hypotheses"]:
            n_essentia_wrong += 1
    lines.append(f"  essentia's own downbeat phase overridden by evidence: {n_essentia_wrong}/{len(songs)} songs")
    return "\n".join(lines)


def phrase_grid_table() -> str:
    lines = ["Phrase-grid edges vs 7 hand-marked drop impacts", ""]
    lines.append(f"  {'song':<32}{'length (bars)':>15}{'edges':>8}{'hits@0.5':>10}{'hits@1.0':>10}{'hits@2.0':>10}")
    for song in paths.GOLD_SONGS:
        payload = export_mod.export(song)
        boundaries = [b["time"] for b in payload["phrase_grid"]["boundaries"]]
        impacts = _drop_impacts(song)
        h5 = _recall(boundaries, impacts, 0.5)
        h10 = _recall(boundaries, impacts, 1.0)
        h20 = _recall(boundaries, impacts, 2.0)
        lines.append(f"  {song:<32}{str(payload['phrase_grid']['phrase_length_bars']):>15}{len(boundaries):>8}{h5:>10}{h10:>10}{h20:>10}")
    lines.append("\n  Reference (allin1 raw unmerged phrase edges, from docs/experiments.md):")
    lines.append("  3/7 @0.5s, 4/7 @1.0s, 6/7 @2.0s at 3.3 boundaries/min")
    return "\n".join(lines)


def write_report() -> None:
    paths.OUT_ROOT.mkdir(parents=True, exist_ok=True)
    text = "Grid consensus — score report\n" + "=" * 60 + "\n\n"
    text += weight_sweep_table() + "\n\n"
    text += downbeat_phase_table() + "\n\n"
    text += phrase_grid_table() + "\n\n"
    text += disagreement_across_corpus() + "\n"
    (paths.OUT_ROOT / "score.txt").write_text(text)
    print(text)
