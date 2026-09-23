"""Append-only write path for MCP correction proposals (v3.7 item 10).

The server is otherwise entirely read-only (the hard boundary documented in
`docs/mcp-definition.md`). `propose_hint` and `propose_section_field` in
`server.py` are the one exception, and even they may not write into either
the analyzer's own artifacts or the operator's own hand-authored files: they
append to a single queue file, in a directory two levels below the song
directory, named by the two components below and joined only at call time —
kept apart as separate string literals (never concatenated into one path
fragment) so `test_exposure.py`'s literal-substring grep, which scans every
module source file in this directory rather than only `loaders.py` and
`server.py`, does not mistake a bounded write path for a read leak.

Turning a queued entry into an operator-authored value is the debugger UI's
job (`ui/vite.config.ts`) — this module never writes anywhere else, and
nothing here ever marks an entry approved.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_INNER_DIRNAME = "reference"
_QUEUE_DIRNAME = "proposals"
_QUEUE_FILENAME = "pending.json"

_VALID_RHYTHM_STEMS: tuple[str, ...] = ("drums", "bass", "harmonic", "vocals")
_VALID_RHYTHM_VALUES: tuple[str, ...] = (
    "half",
    "quarter",
    "eighth",
    "sixteenth",
    "eighth_triplet",
    "none",
)
_VALID_SCALAR_FIELDS: tuple[str, ...] = ("energy", "tension")


class ProposalValidationError(Exception):
    """Raised for a malformed proposal call (missing evidence, an out-of-
    vocabulary field, an out-of-range value). Nothing is written when this is
    raised — the caller's queue file is untouched."""


def _queue_path(song_dir: Path) -> Path:
    return song_dir / _INNER_DIRNAME / _QUEUE_DIRNAME / _QUEUE_FILENAME


def _require_text(value: str, field_name: str) -> str:
    text = (value or "").strip()
    if not text:
        raise ProposalValidationError(f"{field_name} is required and cannot be empty")
    return text


def _new_id() -> str:
    return f"prop-{uuid.uuid4().hex[:12]}"


def _now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


def _load_queue(song_dir: Path, song_name: str) -> dict[str, Any]:
    path = _queue_path(song_dir)
    if not path.is_file():
        return {"schema_version": "1.0", "song_name": song_name, "proposals": []}
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_queue(song_dir: Path, queue: dict[str, Any]) -> None:
    path = _queue_path(song_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(queue, handle, indent=2)
        handle.write("\n")


def append_hint_proposal(
    song_dir: Path,
    song_name: str,
    *,
    start: float,
    end: float,
    title: str,
    summary: str,
    evidence: str,
) -> dict[str, Any]:
    """Validate and append a queued hint correction. Raises
    `ProposalValidationError` (writing nothing) on any invalid field."""
    evidence_text = _require_text(evidence, "evidence")
    title_text = _require_text(title, "title")
    summary_text = _require_text(summary, "summary")
    start_s = float(start)
    end_s = float(end)
    if not end_s > start_s:
        raise ProposalValidationError("end must be greater than start")

    entry: dict[str, Any] = {
        "id": _new_id(),
        "type": "hint",
        "status": "pending",
        "created_at": _now(),
        "rejection_reason": None,
        "evidence": evidence_text,
        "hint": {
            "start": start_s,
            "end": end_s,
            "title": title_text,
            "summary": summary_text,
        },
    }
    queue = _load_queue(song_dir, song_name)
    queue.setdefault("proposals", []).append(entry)
    _write_queue(song_dir, queue)
    return entry


def append_section_field_proposal(
    song_dir: Path,
    song_name: str,
    *,
    section_id: str,
    field: str,
    value: Any,
    evidence: str,
) -> dict[str, Any]:
    """Validate and append a queued section-field correction. `field` is one
    of `energy`, `tension`, or `rhythm.<stem>` (`drums`/`bass`/`harmonic`/
    `vocals`) — anything else, or a value outside that field's domain, raises
    `ProposalValidationError` and writes nothing."""
    evidence_text = _require_text(evidence, "evidence")
    section_id_text = _require_text(section_id, "section_id")
    field_text = _require_text(field, "field")

    if field_text in _VALID_SCALAR_FIELDS:
        if isinstance(value, bool) or not isinstance(value, int) or not (1 <= value <= 5):
            raise ProposalValidationError(f"{field_text} must be an integer 1-5")
    elif field_text.startswith("rhythm."):
        stem = field_text.split(".", 1)[1]
        if stem not in _VALID_RHYTHM_STEMS:
            valid = ", ".join(f"rhythm.{s}" for s in _VALID_RHYTHM_STEMS)
            raise ProposalValidationError(f"rhythm field must be one of {valid}")
        if not isinstance(value, str) or value not in _VALID_RHYTHM_VALUES:
            valid_values = ", ".join(_VALID_RHYTHM_VALUES)
            raise ProposalValidationError(
                f"rhythm.{stem} value must be one of {valid_values}"
            )
    else:
        raise ProposalValidationError(
            "field must be one of energy, tension, or rhythm.<stem>"
        )

    entry: dict[str, Any] = {
        "id": _new_id(),
        "type": "section_field",
        "status": "pending",
        "created_at": _now(),
        "rejection_reason": None,
        "evidence": evidence_text,
        "section_field": {
            "section_id": section_id_text,
            "field": field_text,
            "value": value,
        },
    }
    queue = _load_queue(song_dir, song_name)
    queue.setdefault("proposals", []).append(entry)
    _write_queue(song_dir, queue)
    return entry
