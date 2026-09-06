"""Response shaping for the `mcp/` server (v3.1 items 9-10).

The *volatile* half of the module: `loaders.py` (song discovery, top-level file
access, the exposure guard) is stable; this file turns those top-level files into
the small, honest payloads `get_song_overview` and `get_detail` return. A
tool-surface reshape should touch this file and its golden snapshots and nothing
else.

Honesty obligations enforced here (see docs/mcp-definition.md "Honesty
obligations" and the MCP regression guide's F2-F4 checks):

- never invent a value to fill a field — an absent gesture phase is reported
  absent, a `null` downbeat confidence is passed through as `null`;
- a confidence is reported against the thing it measures — the beats file's
  confidence is surfaced as `downbeat_confidence`, never as a beat-time number;
- `function_status: "unknown"` is surfaced as-is;
- `same_label_as` grouping always carries the "label repetition, not acoustic
  identity" caveat;
- a drop is never named directly — it appears only as gesture phases or a
  section-pair transition;
- `field_sources` / `source` are passed through (summarised once per block from
  the file header, never dropped);
- no full beat list ever leaves this module.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from loaders import load_top_level_json, resolve_song_dir

# Canonical composite-gesture envelope. A gesture that is missing one of these
# phases has it listed in `phases_absent` — never zero-filled, never interpolated.
GESTURE_PHASES: tuple[str, ...] = ("approach", "build", "tension", "impact", "release")
_PHASE_CODE = {p: p[0] for p in GESTURE_PHASES}  # approach->a, build->b, ...
PHASE_LEGEND = "a=approach b=build t=tension i=impact r=release"

# The published loudness floor. A caller may ask for this interval or coarser,
# never finer — a finer request is an error, not a silent upsample.
LOUDNESS_FLOOR_MS = 20

# The dense-series window cap: a maximum, not a default (D2). A resolved span
# longer than this returns the structural view with the dense frames withheld.
DENSE_CAP_S = 5.0

# Default stem set for get_detail, in a stable order.
DEFAULT_SOURCES: tuple[str, ...] = ("mix", "bass", "drums", "harmonic", "vocals")

_SAME_LABEL_CAVEAT = "same_label_as is label repetition, not acoustic identity"


class DetailScopeError(ValueError):
    """Raised for an invalid get_detail scope selection (zero or >1 selectors,
    a half-specified window, or an interval below the published floor)."""


# --------------------------------------------------------------------------- #
# get_song_overview
# --------------------------------------------------------------------------- #

def build_song_overview(song: str, root: str | Path | None = None) -> dict[str, Any]:
    """Whole-song overview: identity, grid, sections, gestures, transitions, hints.

    Compact by construction — the grid is a summary (never the beat list),
    gestures are grouped one row per composite gesture (never one row per phase),
    and prose is kept to the honest downbeat note plus the file-supplied genre
    guidance.
    """
    song_dir = resolve_song_dir(song, root=root)

    info = load_top_level_json(song_dir, "info.json")
    beats_doc = load_top_level_json(song_dir, "beats.json")
    sections_doc = load_top_level_json(song_dir, "sections.json")
    timeline_doc = load_top_level_json(song_dir, "song_event_timeline.json")
    hints_doc = load_top_level_json(song_dir, "hints.json")
    genre_doc = _maybe_load(song_dir, "genre.json")

    beats = beats_doc.get("beats", [])
    sections = sections_doc.get("sections", [])
    events = timeline_doc.get("events", [])

    # Each block carries its own `field_sources` summary, drawn once from the
    # file header it came from — never repeated per row, never a redundant
    # response-level copy.
    return {
        "song_name": info.get("song_name"),
        "identity": _identity_block(info, sections, genre_doc),
        "grid": _grid_block(info, beats_doc, beats),
        "sections": _sections_block(sections_doc, sections),
        "gestures": {"phase_legend": PHASE_LEGEND, **_gestures_block(timeline_doc, events)},
        "transitions": _transitions_block(timeline_doc, events),
        "human_hints": _hints_block(hints_doc),
    }


def _r(value: Any, places: int = 3) -> Any:
    return round(value, places) if isinstance(value, (int, float)) else value


def _identity_block(info: dict, sections: list[dict], genre_doc: dict | None) -> dict[str, Any]:
    keys = [s.get("key") for s in sections if s.get("key")]
    unique = list(dict.fromkeys(keys))
    if not unique:
        whole_key: Any = None
    elif len(unique) == 1:
        whole_key = unique[0]
    else:
        whole_key = {"varies": unique}

    genre: Any = None
    if genre_doc is not None:
        genre = {
            "genres": genre_doc.get("genres"),
            "confidence": genre_doc.get("confidence"),
            "guidance": genre_doc.get("guidance"),
        }

    return {
        "song_name": info.get("song_name"),
        "bpm": info.get("bpm"),
        "duration": info.get("duration"),
        "key": whole_key,
        "genre": genre,
        "field_sources": {
            "bpm": "essentia",
            "duration": "essentia",
            "key": "harmonic",
            "genre": "genre",
        },
    }


def _grid_block(info: dict, beats_doc: dict, beats: list[dict]) -> dict[str, Any]:
    downbeats = [b for b in beats if b.get("type") == "downbeat"]
    total = len(downbeats)
    null_conf = sum(1 for b in downbeats if b.get("downbeat_confidence") is None)

    if total == 0:
        note = "No downbeats published — bar numbers are unavailable on this song."
    elif null_conf == total:
        note = (
            f"All {total} downbeats carry a null downbeat_confidence "
            "(allin1 downbeat phase, ~0.226 F1) — the bar phase is unresolved; "
            "do not trust bar numbers on this song."
        )
    elif null_conf > 0:
        note = (
            f"{null_conf} of {total} downbeats carry a null downbeat_confidence "
            "(allin1 downbeat phase, ~0.226 F1) — bar numbers are partly "
            "unresolved on this song."
        )
    else:
        note = (
            f"All {total} downbeats carry a downbeat_confidence "
            "(allin1 downbeat phase, ~0.226 F1) — treat bar numbers as approximate."
        )

    beats_per_bar = max((b.get("beat", 0) for b in beats), default=0)
    bar_count = max((b.get("bar", 0) for b in beats), default=0)

    return {
        "tempo": info.get("bpm"),
        "beats_per_bar": beats_per_bar,
        "bar_count": bar_count,
        "downbeat_count": total,
        "downbeats_null_confidence": null_conf,
        "downbeat_note": note,
        "field_sources": beats_doc.get("field_sources"),
    }


def _sections_block(sections_doc: dict, sections: list[dict]) -> dict[str, Any]:
    rows = [
        {
            "section_id": s.get("section_id"),
            "start": s.get("start"),
            "end": s.get("end"),
            "function": s.get("function"),
            "function_confidence": s.get("function_confidence"),
            "function_status": s.get("function_status", "unknown"),
            "same_label_as": s.get("same_label_as"),
            "description": s.get("description"),
            "confidence": s.get("confidence"),
        }
        for s in sections
    ]
    return {
        "caveat": _SAME_LABEL_CAVEAT,
        "rows": rows,
        "field_sources": sections_doc.get("field_sources"),
    }


def _group_gestures(events: list[dict]) -> list[tuple[str, list[dict]]]:
    order: list[str] = []
    groups: dict[str, list[dict]] = {}
    for event in events:
        gid = event.get("gesture_id")
        if not gid:
            continue
        if gid not in groups:
            groups[gid] = []
            order.append(gid)
        groups[gid].append(event)
    result = []
    for gid in order:
        phase_rows = sorted(
            groups[gid],
            key=lambda e: (
                e.get("start_time", 0.0),
                _phase_index(e.get("type", "")),
            ),
        )
        result.append((gid, phase_rows))
    return result


def _phase_index(phase: str) -> int:
    return GESTURE_PHASES.index(phase) if phase in GESTURE_PHASES else len(GESTURE_PHASES)


def _gestures_block(timeline_doc: dict, events: list[dict]) -> dict[str, Any]:
    rows = []
    for gid, phase_rows in _group_gestures(events):
        present = list(dict.fromkeys(r.get("type") for r in phase_rows))
        absent = [p for p in GESTURE_PHASES if p not in present]
        rows.append(
            {
                "gesture_id": gid,
                "start": min(r.get("start_time") for r in phase_rows),
                "end": max(r.get("end_time") for r in phase_rows),
                "section_id": phase_rows[0].get("section_id"),
                "peak_intensity": max(
                    (r.get("intensity") for r in phase_rows if r.get("intensity") is not None),
                    default=None,
                ),
                "phases_present": present,
                "phases_absent": absent,
            }
        )
    return {
        "rows": rows,
        "field_sources": timeline_doc.get("field_sources"),
    }


def _transitions_block(timeline_doc: dict, events: list[dict]) -> dict[str, Any]:
    rows = [
        {
            "transition": e.get("type"),
            "time": e.get("start_time"),
            "confidence": e.get("confidence"),
            "section_id": e.get("section_id"),
        }
        for e in events
        if not e.get("gesture_id") and "→" in str(e.get("type", ""))
    ]
    return {
        "rows": rows,
        "field_sources": timeline_doc.get("field_sources"),
    }


def _hints_block(hints_doc: dict) -> dict[str, Any]:
    rows = []
    for section in hints_doc.get("sections", []):
        for hint in section.get("hints", []):
            row = {
                "section_id": section.get("section_id"),
                "title": hint.get("title"),
                "text": hint.get("text"),
                "start_time": hint.get("start_time"),
                "end_time": hint.get("end_time"),
                "source": hint.get("source"),
            }
            if hint.get("lighting_hint") is not None:
                row["lighting_hint"] = hint["lighting_hint"]
            rows.append(row)
    return {
        "rows": rows,
        "field_sources": hints_doc.get("field_sources"),
        "note": "human hints are ground truth and outrank every inferred field above",
    }


# --------------------------------------------------------------------------- #
# get_detail
# --------------------------------------------------------------------------- #

def build_detail(
    song: str,
    *,
    section_id: str | None = None,
    gesture_id: str | None = None,
    start_ms: int | None = None,
    end_ms: int | None = None,
    interval_ms: int | None = None,
    sources: list[str] | None = None,
    root: str | Path | None = None,
) -> dict[str, Any]:
    """Dense detail for one resolved span.

    Exactly one scope selector is required — `section_id`, `gesture_id`, or
    `start_ms` + `end_ms`. Zero or two is an error (no precedence rule). A span
    longer than the 5 s cap returns the structural view with the dense frames
    withheld and the cap named. `interval_ms` is caller-chosen and decimates the
    published 20 ms series by pair-averaging; finer than 20 ms is an error.
    """
    song_dir = resolve_song_dir(song, root=root)

    sections_doc = load_top_level_json(song_dir, "sections.json")
    timeline_doc = load_top_level_json(song_dir, "song_event_timeline.json")
    hints_doc = load_top_level_json(song_dir, "hints.json")

    scope, span_start, span_end = _resolve_span(
        section_id=section_id,
        gesture_id=gesture_id,
        start_ms=start_ms,
        end_ms=end_ms,
        sections=sections_doc.get("sections", []),
        events=timeline_doc.get("events", []),
    )

    target_interval = LOUDNESS_FLOOR_MS if interval_ms is None else int(interval_ms)
    if target_interval < LOUDNESS_FLOOR_MS:
        raise DetailScopeError(
            f"interval_ms={target_interval} is finer than the published floor of "
            f"{LOUDNESS_FLOOR_MS} ms — the server decimates, it does not upsample"
        )

    stem_set = _resolve_sources(sources)

    duration = round(span_end - span_start, 6)
    events = timeline_doc.get("events", [])

    response: dict[str, Any] = {
        "song_name": timeline_doc.get("song_name"),
        "scope": scope,
        "span": {"start": span_start, "end": span_end, "duration": duration},
        "structural": _structural_view(
            span_start, span_end, sections_doc, timeline_doc, hints_doc, events
        ),
    }

    if duration > DENSE_CAP_S + 1e-9:
        response["dense"] = None
        response["dense_withheld"] = {
            "reason": (
                f"resolved span {duration:.3f} s exceeds the {DENSE_CAP_S:g} s "
                "dense-series cap (a maximum, not a default) — request a window "
                f"of {DENSE_CAP_S:g} s or less for dense frames"
            ),
            "cap_seconds": DENSE_CAP_S,
        }
        return response

    loudness_doc = _maybe_load(song_dir, "loudness.json")
    if loudness_doc is None:
        response["dense"] = None
        response["dense_withheld"] = {
            "reason": "loudness.json is not published for this song",
        }
        return response

    response["dense"] = _dense_frames(
        loudness_doc, span_start, span_end, target_interval, stem_set
    )
    return response


def _resolve_span(
    *,
    section_id: str | None,
    gesture_id: str | None,
    start_ms: int | None,
    end_ms: int | None,
    sections: list[dict],
    events: list[dict],
) -> tuple[dict[str, Any], float, float]:
    has_window = start_ms is not None or end_ms is not None
    selectors = [section_id is not None, gesture_id is not None, has_window]
    chosen = sum(selectors)

    if chosen == 0:
        raise DetailScopeError(
            "a scope selector is required: section_id, gesture_id, or "
            "start_ms + end_ms"
        )
    if chosen > 1:
        raise DetailScopeError(
            "exactly one scope selector is allowed (section_id, gesture_id, or "
            "start_ms + end_ms) — there is no precedence rule; pass just one"
        )

    if section_id is not None:
        for s in sections:
            if s.get("section_id") == section_id:
                return ({"kind": "section", "section_id": section_id},
                        float(s["start"]), float(s["end"]))
        raise DetailScopeError(f"no section {section_id!r} in sections.json")

    if gesture_id is not None:
        phase_rows = [
            e for e in events if e.get("gesture_id") == gesture_id
        ]
        if not phase_rows:
            raise DetailScopeError(
                f"no gesture {gesture_id!r} in song_event_timeline.json"
            )
        return (
            {"kind": "gesture", "gesture_id": gesture_id},
            min(float(r["start_time"]) for r in phase_rows),
            max(float(r["end_time"]) for r in phase_rows),
        )

    if start_ms is None or end_ms is None:
        raise DetailScopeError(
            "a window scope needs both start_ms and end_ms"
        )
    if end_ms <= start_ms:
        raise DetailScopeError(
            f"end_ms ({end_ms}) must be greater than start_ms ({start_ms})"
        )
    return (
        {"kind": "window", "start_ms": start_ms, "end_ms": end_ms},
        start_ms / 1000.0,
        end_ms / 1000.0,
    )


def _resolve_sources(sources: list[str] | None) -> list[str]:
    if sources is None:
        return list(DEFAULT_SOURCES)
    unknown = [s for s in sources if s not in DEFAULT_SOURCES]
    if unknown:
        raise DetailScopeError(
            f"unknown source(s) {unknown} — valid: {list(DEFAULT_SOURCES)}"
        )
    # Stable order: the published source order, filtered to the request.
    return [s for s in DEFAULT_SOURCES if s in sources]


def _overlaps(start: float, end: float, a: float, b: float) -> bool:
    return a < end and b > start


def _structural_view(
    span_start: float,
    span_end: float,
    sections_doc: dict,
    timeline_doc: dict,
    hints_doc: dict,
    events: list[dict],
) -> dict[str, Any]:
    section_rows = [
        {
            "section_id": s.get("section_id"),
            "start": s.get("start"),
            "end": s.get("end"),
            "function": s.get("function"),
            "function_status": s.get("function_status", "unknown"),
            "same_label_as": s.get("same_label_as"),
        }
        for s in sections_doc.get("sections", [])
        if _overlaps(span_start, span_end, float(s["start"]), float(s["end"]))
    ]

    phase_rows = [
        {
            "type": e.get("type"),
            "gesture_id": e.get("gesture_id"),
            "start": e.get("start_time"),
            "end": e.get("end_time"),
            "intensity": e.get("intensity"),
            "confidence": e.get("confidence"),
        }
        for e in events
        if e.get("gesture_id")
        and _overlaps(span_start, span_end, float(e["start_time"]), float(e["end_time"]))
    ]

    transition_rows = [
        {
            "transition": e.get("type"),
            "time": e.get("start_time"),
            "confidence": e.get("confidence"),
            "section_id": e.get("section_id"),
        }
        for e in events
        if not e.get("gesture_id")
        and "→" in str(e.get("type", ""))
        and span_start <= float(e["start_time"]) <= span_end
    ]

    hint_rows = []
    for section in hints_doc.get("sections", []):
        for hint in section.get("hints", []):
            h_start = hint.get("start_time")
            h_end = hint.get("end_time")
            if h_start is None or h_end is None:
                continue
            if _overlaps(span_start, span_end, float(h_start), float(h_end)):
                row = {
                    "section_id": section.get("section_id"),
                    "title": hint.get("title"),
                    "text": hint.get("text"),
                    "start_time": h_start,
                    "end_time": h_end,
                    "source": hint.get("source"),
                }
                if hint.get("lighting_hint") is not None:
                    row["lighting_hint"] = hint["lighting_hint"]
                hint_rows.append(row)

    intensities = [r["intensity"] for r in phase_rows if r["intensity"] is not None]
    if intensities:
        aggregate = {
            "peak": max(intensities),
            "mean": round(sum(intensities) / len(intensities), 6),
        }
    else:
        aggregate = None

    return {
        "sections": {
            "rows": section_rows,
            "field_sources": sections_doc.get("field_sources"),
        },
        "phases": {
            "rows": phase_rows,
            "field_sources": timeline_doc.get("field_sources"),
        },
        "transitions": {
            "rows": transition_rows,
            "field_sources": timeline_doc.get("field_sources"),
        },
        "hints": {
            "rows": hint_rows,
            "field_sources": hints_doc.get("field_sources"),
        },
        "aggregate_intensity": aggregate,
    }


def _dense_frames(
    loudness_doc: dict,
    span_start: float,
    span_end: float,
    interval_ms: int,
    stem_set: list[str],
) -> dict[str, Any]:
    published_order = loudness_doc.get("metadata", {}).get(
        "source_order", list(DEFAULT_SOURCES)
    )
    keep_idx = [published_order.index(s) for s in stem_set]

    window = [
        f for f in loudness_doc.get("frames", [])
        if span_start <= f["time"] <= span_end
    ]

    factor = max(1, interval_ms // LOUDNESS_FLOOR_MS)
    frames: list[dict[str, Any]] = []
    # Whole chunks only — an unfilled trailing chunk is dropped so every
    # emitted interval is exactly `factor * 20` ms (see D22).
    for base in range(0, len(window) - factor + 1, factor):
        chunk = window[base:base + factor]
        frames.append(_average_chunk(chunk, keep_idx))

    return {
        "interval_ms": interval_ms,
        "sources": stem_set,
        "frame_count": len(frames),
        "frames": frames,
        "decimation": (
            "pair-averaging" if factor > 1 else "none (published floor)"
        ),
        "field_sources": loudness_doc.get("field_sources"),
    }


def _average_chunk(chunk: list[dict], keep_idx: list[int]) -> dict[str, Any]:
    n = len(chunk)
    time = round(sum(f["time"] for f in chunk) / n, 6)
    values = [
        round(sum(f["values"][i] for f in chunk) / n, 6) for i in keep_idx
    ]
    normalized = [
        round(sum(f["normalized_values"][i] for f in chunk) / n, 6)
        for i in keep_idx
    ]
    return {"time": time, "values": values, "normalized_values": normalized}


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def _maybe_load(song_dir: Path, filename: str) -> dict | None:
    """Load an optional top-level file; return None if it is not published yet.

    genre.json / loudness.json are mid-migration and not in
    `REQUIRED_TOP_LEVEL_FILES` (D23). A serializer that needs one degrades
    honestly rather than raising.
    """
    try:
        return load_top_level_json(song_dir, filename)
    except FileNotFoundError:
        return None
