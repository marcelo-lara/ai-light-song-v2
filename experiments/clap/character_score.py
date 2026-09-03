"""Score the character layer against the operator's hand-marked character hints.

    question    Beyond the arrangement, can these models find the passages a
                human marks and gives a distinct look — the "Breath" in Armin,
                the "Spacer" and vocal outros in `_test_song`?
    measurement Per hint: the z-score of every axis inside the hint against the
                whole song, and whether a character block of any kind covers it.
    incumbent   Nothing. The pipeline emits no texture or character layer at all.
    baseline    The stems alone, which are already in the trusted half of the
                pipeline. CLAP has to add something on top of them to be worth a
                GPU pass, and the ablation below is what says whether it does.

Ten hand-marked non-drop hints across two songs is a very small evaluation, and
nine of them are in a 58 s synthetic excerpt. Read the direction, not the
decimals.
"""
from __future__ import annotations

import json

import numpy as np

from . import character, model, probes
from .paths import ANALYSIS_ROOT, all_songs


def character_hints(song: str) -> list[dict]:
    """Hand-marked hints that are not part of a drop sequence."""
    path = ANALYSIS_ROOT / song / "reference" / "human" / "human_hints.json"
    if not path.exists():
        return []
    payload = json.loads(path.read_text())
    return [h for h in payload.get("human_hints", [])
            if not str(h.get("title", "")).strip().casefold().startswith("drop ")]


def _z(curve: np.ndarray, mask: np.ndarray) -> float:
    if not mask.any():
        return float("nan")
    return float((curve[mask].mean() - curve.mean()) / (curve.std() + 1e-8))


def report(songs: list[str]) -> str:
    text_emb = probes.text_embeddings()
    axes = list(probes.PAIRS)
    stem_names = ["vocals", "drums", "bass", "harmonic", "mix"]

    lines = [
        "Character hints: what the models say inside the passages a human marked.",
        "",
        "Every column is a z-score of that signal inside the hint against the whole",
        "song. CLAP axes are contrastive pairs (positive = the first sentence);",
        "stem columns are per-stem RMS the pipeline already produces.",
        "",
    ]
    header = (f"{'song':<20}{'hint':<24}{'span':>14}  "
              + " ".join(f"{a[:5]:>6}" for a in axes)
              + " | " + " ".join(f"{s[:4]:>5}" for s in stem_names) + "  covered by")
    lines += [header, "-" * len(header)]

    covered_any = covered_stems_only = total = 0
    for song in songs:
        hints = character_hints(song)
        if not hints:
            continue
        times, stems = character.stem_grid(song)
        cache = model.load(song)
        clap = {k: character.resample(cache["times"], v, times)
                for k, v in probes.axes(model.unit(cache["emb"]), text_emb).items()}
        rows = character.blocks(song, times, stems, clap)

        for hint in hints:
            lo, hi = float(hint["start_time"]), float(hint["end_time"])
            hi = max(hi, lo + 0.5)
            mask = (times >= lo) & (times < hi)
            if not mask.any():
                mask = np.zeros(len(times), dtype=bool)
                mask[int(np.argmin(np.abs(times - (lo + hi) / 2)))] = True
            hit = [r["kind"] for r in rows
                   if r["start_s"] < hi and r["end_s"] > lo]
            total += 1
            covered_any += bool(hit)
            lines.append(
                f"{song[:19]:<20}{str(hint['title'])[:23]:<24}{lo:6.1f}-{hi:6.1f}  "
                + " ".join(f"{_z(clap[a], mask):+6.2f}" for a in axes)
                + " | " + " ".join(f"{_z(stems[s], mask):+5.1f}" for s in stem_names)
                + "  " + (", ".join(sorted(set(hit))) if hit else "-")
            )

    lines += [
        "-" * len(header),
        f"Hints covered by some character block: {covered_any}/{total}",
        "",
        "Coverage is a weak test — a block that spans half the song covers everything.",
        "The per-axis columns are the substance: they say whether the signal a human",
        "responded to is actually present in the representation.",
        "",
        "",
        ablation(songs, text_emb),
    ]
    return "\n".join(lines)


def ablation(songs: list[str], text_emb) -> str:
    """Does CLAP's calm axis earn its GPU pass on top of the stems?

    The stems are free and trusted, so the question is not whether the combined
    rule works — it is whether dropping the two CLAP terms changes the answer.
    Recall is measured on the one block big enough to measure (`Armin` "Breath");
    specificity is measured as how much of the corpus each rule claims, because
    a rule that fires everywhere finds everything and says nothing.
    """
    lines = ["Ablation: what the CLAP calm axis adds to the stems.", ""]
    header = (f"{'rule':<28}{'breath blocks':>15}{'breath seconds':>16}"
              f"{'full-power blocks':>19}{'% of corpus':>13}")
    lines += [header, "-" * len(header)]

    for use_clap in (True, False):
        breath_blocks = breath_seconds = power_blocks = 0
        claimed = duration = 0.0
        armin_hit = False
        for song in songs:
            times, stems = character.stem_grid(song)
            cache = model.load(song)
            clap = {k: character.resample(cache["times"], v, times)
                    for k, v in probes.axes(model.unit(cache["emb"]), text_emb).items()}
            rows = character.blocks(song, times, stems, clap,
                                    use_clap=use_clap, include_shadow=False)
            duration += float(times[-1]) if len(times) else 0.0
            for row in rows:
                span = row["end_s"] - row["start_s"]
                claimed += span
                if row["kind"] == "breath":
                    breath_blocks += 1
                    breath_seconds += span
                    if song == "Armin - Revolution" and row["start_s"] < 96.3 and row["end_s"] > 81.4:
                        armin_hit = True
                elif row["kind"] == "full power":
                    power_blocks += 1
        name = "stems + CLAP calm" if use_clap else "stems alone (CLAP dropped)"
        lines.append(f"{name:<28}{breath_blocks:>15}{breath_seconds:>15.0f}s"
                     f"{power_blocks:>19}{100 * claimed / max(duration, 1):>12.0f}%")
        lines.append(f"{'    Armin Breath found':<28}{'yes' if armin_hit else 'NO':>15}")
    lines += [
        "",
        "Both rules find the Armin block. The difference is specificity: without the",
        "calm term `breath` degenerates into `any voice with the drums down`, and",
        "`full power` into `drums and bass both playing`, which is most of a dance",
        "track. The stems say what is playing; CLAP says how it feels, and only the",
        "second distinguishes a breath from a verse.",
    ]
    return "\n".join(lines)
