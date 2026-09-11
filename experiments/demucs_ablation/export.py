"""Writes the per-song x per-variant score table to `out/score.json` (and a
printable markdown table) — the input to `docs/experiments.md`'s entry.
Never writes into `data/analysis/`."""
from __future__ import annotations

import datetime
import json

from . import paths, score


def export(songs: list[str], variants: list[str]) -> list[dict]:
    rows: list[dict] = []
    for song in songs:
        for variant in variants:
            try:
                rows.append(score.score_variant(song, variant))
            except FileNotFoundError as exc:
                rows.append({"song": song, "variant": variant, "error": str(exc)})
    return rows


def write_report(songs: list[str], variants: list[str]) -> list[dict]:
    rows = export(songs, variants)
    out_path = paths.score_out_path()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "songs": songs,
        "variants": variants,
        "rows": rows,
    }
    out_path.write_text(json.dumps(payload, indent=2))
    print(_as_markdown(rows))
    return rows


def _as_markdown(rows: list[dict]) -> str:
    lines = ["| song | variant | voiced_duration_fraction | false_vocal_rate | proxy (no ground truth) |",
             "| --- | --- | --- | --- | --- |"]
    for r in rows:
        if "error" in r:
            lines.append(f"| {r['song']} | {r['variant']} | error: {r['error']} | | |")
            continue
        lines.append(
            f"| {r['song']} | {r['variant']} | {r['voiced_duration_fraction']:.3f} | "
            f"{r['false_vocal_rate']:.3f} | {r['is_proxy_no_ground_truth']} |"
        )
    return "\n".join(lines)
