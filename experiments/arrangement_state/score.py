"""Score arrangement-state changes against the hand-marked hints.

Ground truth is the *start time* of every hint in
`reference/human/human_hints.json` — the operator's own answer to "something
different starts here". That is deliberately not the same target as the
arrangement-section F1 in `docs/analysis-definition.md`: hints include texture
and gesture boundaries that no verse/chorus segmenter is even trying to find.

Two comparisons, both required before this means anything:

* **incumbent** — the boundaries the shipped `sections.json` actually publishes.
* **baseline** — an evenly spaced grid given the *same detection budget*, which
  is the control that killed CLAP semantic novelty in `experiments/clap`.
"""
from __future__ import annotations

import json

from . import detector, paths

TOLERANCES = (0.5, 1.0)


def hint_boundaries(song: str) -> list[tuple[float, str]]:
    doc = json.loads(paths.hints_path(song).read_text())
    return sorted((h["start_time"], h.get("title", "")) for h in doc["human_hints"])


def shipped_boundaries(song: str) -> list[float]:
    doc = json.loads(paths.shipped_sections_path(song).read_text())
    # Section starts, minus t=0 which no detector should be credited for.
    return [s["start"] for s in doc["sections"] if s["start"] > 0.01]


def grid_boundaries(duration: float, count: int) -> list[float]:
    if count <= 0:
        return []
    step = duration / (count + 1)
    return [step * (i + 1) for i in range(count)]


def prf(detected: list[float], truth: list[float], tol: float) -> tuple[float, float, float, int]:
    if not detected or not truth:
        return 0.0, 0.0, 0.0, 0
    hits = sum(1 for t in truth if min(abs(d - t) for d in detected) <= tol)
    p = sum(1 for d in detected if min(abs(d - t) for t in truth) <= tol) / len(detected)
    r = hits / len(truth)
    f = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f, hits


def report(songs: list[str]) -> str:
    lines: list[str] = []
    lines.append("Arrangement-state changes vs hand-marked hint starts")
    lines.append("=" * 78)
    lines.append("")
    totals = {k: {t: [0, 0, 0] for t in TOLERANCES} for k in ("state", "shipped", "grid")}

    for song in songs:
        res = detector.detect(song)
        truth = hint_boundaries(song)
        truth_t = [t for t, _ in truth]
        det = [c.time for c in res.changes]
        shipped = shipped_boundaries(song)
        grid = grid_boundaries(res.duration, len(det))

        lines.append(f"## {song}   ({res.duration:.1f}s, {len(truth)} hints)")
        lines.append(f"   thresholds dB: {res.thresholds_db}")
        lines.append("")
        header = f"   {'method':<28}{'n':>4}"
        for tol in TOLERANCES:
            header += f"   {'P/R/F1 @' + str(tol) + 's':>20}"
        lines.append(header)
        for name, dets in (("arrangement state", det), ("shipped sections (incumbent)", shipped), ("even grid (baseline)", grid)):
            row = f"   {name:<28}{len(dets):>4}"
            key = {"arrangement state": "state", "shipped sections (incumbent)": "shipped", "even grid (baseline)": "grid"}[name]
            for tol in TOLERANCES:
                p, r, f, hits = prf(dets, truth_t, tol)
                row += f"   {p:>5.2f}/{r:.2f}/{f:.2f}"
                totals[key][tol][0] += hits
                totals[key][tol][1] += len(dets)
                totals[key][tol][2] += len(truth_t)
            lines.append(row)
        lines.append("")

        lines.append("   per-hint (arrangement state, tol 0.5s):")
        for t, title in truth:
            if det:
                near = min(det, key=lambda d: abs(d - t))
                mark = "HIT " if abs(near - t) <= 0.5 else "miss"
                lines.append(f"     {t:7.2f}  {title[:34]:36s} nearest {near:7.2f}  d={near - t:+6.2f}  {mark}")
        lines.append("")
        lines.append("   changes:")
        for c in res.changes:
            what = " ".join([f"+{s}" for s in c.entered] + [f"-{s}" for s in c.left])
            playing = ",".join(s for s, on in c.state.items() if on) or "(silence)"
            lines.append(f"     {c.time:7.2f}  {what:<28} -> [{playing}]  margin {c.margin_db:+.1f} dB")
        lines.append("")

    lines.append("=" * 78)
    lines.append("## Corpus totals (hits pooled across songs)")
    lines.append("")
    for key, label in (("state", "arrangement state"), ("shipped", "shipped sections (incumbent)"), ("grid", "even grid (baseline)")):
        row = f"   {label:<28}"
        for tol in TOLERANCES:
            hits, ndet, ntruth = totals[key][tol]
            r = hits / ntruth if ntruth else 0.0
            # Pooled precision needs per-song matched detections; recompute below.
            row += f"   R@{tol}s {r:.2f} ({hits}/{ntruth})"
        lines.append(row)
    lines.append("")

    # Pooled precision, computed properly per song then summed.
    lines.append("   pooled precision (matched detections / all detections)")
    pool = {k: {t: [0, 0] for t in TOLERANCES} for k in ("state", "shipped", "grid")}
    for song in songs:
        res = detector.detect(song)
        truth_t = [t for t, _ in hint_boundaries(song)]
        sets = {
            "state": [c.time for c in res.changes],
            "shipped": shipped_boundaries(song),
            "grid": grid_boundaries(res.duration, len(res.changes)),
        }
        for k, dets in sets.items():
            for tol in TOLERANCES:
                pool[k][tol][0] += sum(1 for d in dets if truth_t and min(abs(d - t) for t in truth_t) <= tol)
                pool[k][tol][1] += len(dets)
    for key, label in (("state", "arrangement state"), ("shipped", "shipped sections (incumbent)"), ("grid", "even grid (baseline)")):
        row = f"   {label:<28}"
        for tol in TOLERANCES:
            m, n = pool[key][tol]
            p = m / n if n else 0.0
            hits, _, ntruth = totals[key][tol]
            r = hits / ntruth if ntruth else 0.0
            f = 2 * p * r / (p + r) if p + r else 0.0
            row += f"   P@{tol}s {p:.2f}  F1 {f:.2f}"
        lines.append(row)
    lines.append("")
    return "\n".join(lines)


def write_report(songs: list[str]) -> None:
    paths.OUT_ROOT.mkdir(parents=True, exist_ok=True)
    text = report(songs)
    (paths.OUT_ROOT / "score.txt").write_text(text)
    print(text)
