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


def pooled_prf(
    detections_by_song: dict[str, list[float]], truth_by_song: dict[str, list[float]], tol: float
) -> tuple[float, float, float]:
    """Corpus-pooled precision/recall/F1 at one tolerance.

    Precision is pooled properly (matched detections / all detections summed
    across songs, each song matched against its own truth) rather than
    averaged per-song, which is why this needs the per-song lists rather than
    pre-aggregated counts.
    """
    matched_det = 0
    n_det = 0
    matched_truth = 0
    n_truth = 0
    for song, dets in detections_by_song.items():
        truth = truth_by_song.get(song, [])
        matched_det += sum(1 for d in dets if truth and min(abs(d - t) for t in truth) <= tol)
        n_det += len(dets)
        matched_truth += sum(1 for t in truth if dets and min(abs(d - t) for d in dets) <= tol)
        n_truth += len(truth)
    p = matched_det / n_det if n_det else 0.0
    r = matched_truth / n_truth if n_truth else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f


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
    detections_by_song = {k: {} for k in ("state", "shipped", "grid")}
    truth_by_song: dict[str, list[float]] = {}
    for song in songs:
        res = detector.detect(song)
        truth_by_song[song] = [t for t, _ in hint_boundaries(song)]
        detections_by_song["state"][song] = [c.time for c in res.changes]
        detections_by_song["shipped"][song] = shipped_boundaries(song)
        detections_by_song["grid"][song] = grid_boundaries(res.duration, len(res.changes))
    for key, label in (("state", "arrangement state"), ("shipped", "shipped sections (incumbent)"), ("grid", "even grid (baseline)")):
        row = f"   {label:<28}"
        for tol in TOLERANCES:
            p, _, _ = pooled_prf(detections_by_song[key], truth_by_song, tol)
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


def ablation_report(song: str = "_test_song") -> str:
    """`detect()` vs `detect_smoothed()` on one song — reproduces README

    "Measurement 1" (smoothing destroys the boundary) from the module itself
    rather than an asserted number.
    """
    truth = hint_boundaries(song)
    truth_t = [t for t, _ in truth]

    variants = [
        ("persistence gate, fine edge reported (detect)", detector.detect(song)),
        ("+-1s duty-cycle smoothing + hysteresis (detect_smoothed)", detector.detect_smoothed(song)),
    ]

    lines: list[str] = []
    lines.append(f"Ablation — persistence gate vs duty-cycle smoothing, on {song}")
    lines.append("=" * 78)
    lines.append("")
    header = f"   {'variant':<58}{'n':>4}"
    for tol in TOLERANCES:
        header += f"   {'P/R/F1 @' + str(tol) + 's':>20}"
    lines.append(header)
    for name, res in variants:
        det = [c.time for c in res.changes]
        row = f"   {name:<58}{len(det):>4}"
        for tol in TOLERANCES:
            p, r, f, _ = prf(det, truth_t, tol)
            row += f"   {p:>5.2f}/{r:.2f}/{f:.2f}"
        lines.append(row)
    lines.append("")

    spacer_t = next((t for t, title in truth if title == "Spacer"), None)
    lines.append("   Spacer hint boundary error (nearest detection per variant)")
    if spacer_t is None:
        lines.append("   (no hint titled 'Spacer' in this song's human_hints.json)")
    else:
        for name, res in variants:
            det = [c.time for c in res.changes]
            if det:
                nearest = min(det, key=lambda d: abs(d - spacer_t))
                delta = nearest - spacer_t
                lines.append(
                    f"     {name:<58} nearest {nearest:7.2f}  d={delta:+6.2f}  |d|={abs(delta):.2f}"
                )
            else:
                lines.append(f"     {name:<58} (no detections)")
    lines.append("")
    return "\n".join(lines)


MARGIN_THRESHOLDS = (0.0, 2.0, 4.0, 6.0, 8.0, 10.0, 12.0, 15.0)


def margin_sweep_report(songs: list[str]) -> str:
    """Filtering `detect()`'s changes by `margin_db` — does it buy precision.

    Reproduces the README's "gating changes by margin_db trades recall for
    precision without ever improving corpus F1" finding, on demand.
    """
    lines: list[str] = []
    lines.append("Margin-db sweep — filtering detect() changes by margin_db >= threshold")
    lines.append("=" * 78)
    lines.append("")

    truth_by_song = {song: [t for t, _ in hint_boundaries(song)] for song in songs}
    raw_by_song = {song: detector.detect(song) for song in songs}

    for threshold in MARGIN_THRESHOLDS:
        lines.append(f"## threshold >= {threshold:.0f} dB")
        detections_by_song: dict[str, list[float]] = {}
        header = f"   {'song':<34}{'n':>4}   F1@0.5s"
        lines.append(header)
        for song in songs:
            res = raw_by_song[song]
            dets = [c.time for c in res.changes if c.margin_db >= threshold]
            detections_by_song[song] = dets
            _, _, f, _ = prf(dets, truth_by_song[song], 0.5)
            lines.append(f"   {song:<34}{len(dets):>4}   {f:.2f}")
        row = "   pooled corpus            "
        for tol in TOLERANCES:
            p, r, f = pooled_prf(detections_by_song, truth_by_song, tol)
            row += f"   @{tol}s P {p:.2f} R {r:.2f} F1 {f:.2f}"
        lines.append(row)
        lines.append("")

    return "\n".join(lines)


def breath_compare_report(song: str = "Armin - Revolution") -> str:
    """Hand-marked "Breath" vs the arrangement-state block vs the CLAP block.

    Reproduces the README's "Measurement 3" from the files at run time —
    nothing here is hardcoded.
    """
    doc = json.loads(paths.character_proposal_path(song).read_text())
    char_block = next((b for b in doc.get("blocks", []) if b.get("id") == "char-004"), None)
    if char_block is None:
        raise ValueError(
            f"no block with id 'char-004' in {paths.character_proposal_path(song)}"
        )

    hints_doc = json.loads(paths.hints_path(song).read_text())
    breath = next((h for h in hints_doc["human_hints"] if h.get("title") == "Breath"), None)
    if breath is None:
        raise ValueError(f"no hint titled 'Breath' in {paths.hints_path(song)}")

    res = detector.detect(song)
    hint_span = (breath["start_time"], breath["end_time"])

    def overlap(a: tuple[float, float], b: tuple[float, float]) -> float:
        return max(0.0, min(a[1], b[1]) - max(a[0], b[0]))

    state_blocks = detector.blocks(res)
    best_block = max(state_blocks, key=lambda b: overlap(hint_span, (b["start_s"], b["end_s"])))

    lines: list[str] = []
    lines.append(f'Breath compare — hand-marked "Breath" vs arrangement state vs CLAP, on {song}')
    lines.append("=" * 78)
    lines.append("")
    lines.append(f"   {'source':<34}{'start':>10}{'end':>10}{'start err':>12}{'end err':>10}")
    lines.append(
        f"   {'hand-marked':<34}{breath['start_time']:>10.2f}{breath['end_time']:>10.2f}{'':>12}{'':>10}"
    )
    lines.append(
        f"   {'arrangement state (own block)':<34}{best_block['start_s']:>10.2f}{best_block['end_s']:>10.2f}"
        f"{best_block['start_s'] - breath['start_time']:>+12.2f}{best_block['end_s'] - breath['end_time']:>+10.2f}"
    )
    lines.append(
        f"   {'CLAP block (char-004)':<34}{char_block['start_s']:>10.2f}{char_block['end_s']:>10.2f}"
        f"{char_block['start_s'] - breath['start_time']:>+12.2f}{char_block['end_s'] - breath['end_time']:>+10.2f}"
    )
    lines.append("")
    return "\n".join(lines)
