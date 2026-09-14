"""Shared `out/score.txt` table writer.

Every family writes one row per truth song plus one corpus row, same columns
throughout the family (`docs/product-refinement-v3.6.md` item 2, "Done
when"). This module only formats; each family decides its own columns and
corpus aggregation (a boundary F1 and a 1-5 exact/±1 rating do not aggregate
the same way).
"""
from __future__ import annotations

from pathlib import Path

CORPUS_ROW_LABEL = "CORPUS"


def _fmt(value) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def render_score_table(columns: list[str], rows: list[dict]) -> str:
    """`columns[0]` is conventionally the song/row label column. Every row
    dict must carry every column key (use `None` for not-applicable, never
    omit the key — an omitted key is a silent fallback to whatever the table
    writer defaults to)."""
    widths = [len(c) for c in columns]
    str_rows = []
    for row in rows:
        missing = [c for c in columns if c not in row]
        if missing:
            raise ValueError(f"score row missing columns {missing}: {row}")
        str_row = [_fmt(row[c]) for c in columns]
        str_rows.append(str_row)
        widths = [max(w, len(s)) for w, s in zip(widths, str_row)]

    def _line(cells: list[str]) -> str:
        return "  ".join(c.ljust(w) for c, w in zip(cells, widths)).rstrip()

    lines = [_line(columns), _line(["-" * w for w in widths])]
    lines.extend(_line(r) for r in str_rows)
    return "\n".join(lines) + "\n"


def write_score_txt(path: Path, columns: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_score_table(columns, rows))
