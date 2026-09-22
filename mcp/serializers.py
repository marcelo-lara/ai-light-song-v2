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
- `arrangement_state.json` is one of the 9 required top-level files (v3.6 item
  9 dropped its old pre-v3.2 degraded path) — its block is always present; a
  leading block's `null` `margin_db` / `confidence` pass through untouched,
  never filled in;
- `drum_events.json`'s single file-level `confidence`/`confidence_reason` pair
  is surfaced once per block, never repeated (null) on every row;
- no full beat list ever leaves `get_song_overview`; `get_detail`'s structural
  view carries an explicit, undecimated `beats` block instead — see below.

No backwards compatibility: every one of the 9 required top-level files is
assumed present once `resolve_song_dir` has validated the song, and this module
reads their fields directly. A shape that does not match is a bug to surface
loudly (`KeyError`/`TypeError`), never a silent `.get(..., default)`.
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

# Sparse-event row cap (D3.4): applies per-sparse block (e.g., drum events),
# independent of the dense-series DENSE_CAP_S.
SPARSE_ROW_CAP = 512

# Default stem set for get_detail, in a stable order.
DEFAULT_SOURCES: tuple[str, ...] = ("mix", "bass", "drums", "harmonic", "vocals")

_SAME_LABEL_CAVEAT = "same_label_as is label repetition, not acoustic identity"

# v3.6 item 10 — exact text from docs/product-refinement-v3.6.md item 6.
REVIEW_WARNING_TEXT = (
    "energy/tension/rhythm sourced `seed_unreviewed` are inferred, not yet "
    "reviewed by the operator; verify on the final show."
)


def _seed_unreviewed_section_ids(sections: list[dict]) -> list[str]:
    """`section_id`s of every row where `energy`, `tension` or any
    `rhythm.<source>` field carries a `seed_unreviewed` source (v3.6 item 10:
    energy_source/tension_source overrides, or a rhythm sub-object's own
    `source` key — see analyzer.stages.section_clues)."""
    ids: list[str] = []
    for s in sections:
        seeded = (
            s.get("energy_source") == "seed_unreviewed"
            or s.get("tension_source") == "seed_unreviewed"
            or any(
                (entry or {}).get("source") == "seed_unreviewed"
                for entry in (s.get("rhythm") or {}).values()
            )
        )
        if seeded:
            ids.append(s["section_id"])
    return ids


def _section_clue_fields(s: dict) -> dict[str, Any]:
    """`energy`/`tension`/`rhythm` fields, present only when the row carries
    them (v3.6 item 10 — no silent fallback, a section with no resolved clue
    simply omits the key)."""
    out: dict[str, Any] = {}
    if "energy" in s:
        out["energy"] = s["energy"]
        out["energy_confidence"] = s.get("energy_confidence")
        if "energy_source" in s:
            out["energy_source"] = s["energy_source"]
    if "tension" in s:
        out["tension"] = s["tension"]
        out["tension_confidence"] = s.get("tension_confidence")
        if "tension_source" in s:
            out["tension_source"] = s["tension_source"]
    if "rhythm" in s:
        out["rhythm"] = s["rhythm"]
    # v3.7 item 2/4 — `impact_alignment` is always a key on the STORED
    # sections.json row (explicit `null` there — CLAUDE.md "no silent
    # fallbacks"), but the projected view omits it entirely when `null`,
    # same token-cost convention as energy/tension/rhythm above (D25's
    # get_song_overview byte budget is load-bearing — see
    # test_overview_budget_mcpfull_under_6kb).
    if s.get("impact_alignment") is not None:
        out["impact_alignment"] = s["impact_alignment"]
    return out


class DetailScopeError(ValueError):
    """Raised for an invalid get_detail scope selection (zero or >1 selectors,
    a half-specified window, or an interval below the published floor)."""


# --------------------------------------------------------------------------- #
# get_song_overview
# --------------------------------------------------------------------------- #

def build_song_overview(song: str, root: str | Path | None = None, scope: str | None = None) -> dict[str, Any]:
    """Whole-song overview: identity, grid, sections, gestures, transitions, hints.

    Compact by construction — the grid is a summary (never the beat list),
    gestures are grouped one row per composite gesture (never one row per phase),
    and prose is kept to the honest downbeat note. Genre `guidance` prose no
    longer lives on `genre.json` (v3.6 item 8) — it is stated once in this
    tool's own description instead (see server.py).

    When scope=="brief" (D3.3) return a reduced payload: keep identity, grid
    summary, section rows without description prose, gesture rows, arrangement
    rows, transition rows, and hint counts. Exclude full hint prose and section
    description.
    """
    song_dir = resolve_song_dir(song, root=root)

    info = load_top_level_json(song_dir, "info.json")
    beats_doc = load_top_level_json(song_dir, "beats.json")
    sections_doc = load_top_level_json(song_dir, "sections.json")
    timeline_doc = load_top_level_json(song_dir, "song_event_timeline.json")
    hints_doc = load_top_level_json(song_dir, "hints.json")
    genre_doc = load_top_level_json(song_dir, "genre.json")
    arrangement_doc = load_top_level_json(song_dir, "arrangement_state.json")

    beats = beats_doc.get("beats", [])
    sections = sections_doc.get("sections", [])
    events = timeline_doc.get("events", [])

    # precompute total hints for brief-scope compacting
    total_hints = len(hints_doc.get("hints", []))

    # Each block carries its own `field_sources` summary, drawn once from the
    # file header it came from — never repeated per row, never a redundant
    # response-level copy.
    #
    # v3.7 item 3/5 — `position` is NOT attached here. This tool stays
    # compact by construction (F4.20's byte budget on the module's own golden
    # fixture is load-bearing — see the module docstring "Compact by
    # construction"): a `position` object roughly doubles a section/gesture/
    # hint row. `get_detail` is the on-demand, span-scoped read and carries
    # `position` on every time field in both its structural and dense views;
    # a client wanting bar/beat context for a specific row fetches it there.
    overview: dict[str, Any] = {
        "song_name": info.get("song_name"),
        "identity": _identity_block(info, sections, genre_doc),
        "grid": _grid_block(info, beats_doc, beats),
        "sections": _sections_block(sections_doc, sections),
        "gestures": {"phase_legend": PHASE_LEGEND, **_gestures_block(timeline_doc, events)},
    }

    # v3.6 item 10 — omitted entirely (not null, not empty) when no section
    # row carries a seed_unreviewed source; present with the affected
    # section_ids otherwise.
    seed_ids = _seed_unreviewed_section_ids(sections)
    if seed_ids:
        overview["review_warning"] = {"text": REVIEW_WARNING_TEXT, "section_ids": seed_ids}

    # If brief scope requested, prune prose-heavy bits per D3.3
    if scope == "brief":
        # prune section descriptions and non-essential fields to minimal ids
        sec_block = overview.get("sections", {})
        pruned_rows = []
        for r in sec_block.get("rows", []):
            pr = {
                "section_id": r.get("section_id"),
            }
            pruned_rows.append(pr)
        overview["sections"] = {"caveat": sec_block.get("caveat"), "rows": pruned_rows, "field_sources": sec_block.get("field_sources")}

        # prune gestures to only the anchor fields to keep the overview tiny
        g = overview.get("gestures", {})
        brief_g_rows = []
        for r in g.get("rows", []):
            brief_g_rows.append({
                "gesture_id": r.get("gesture_id"),
                "impact_time": r.get("impact_time"),
            })
        overview["gestures"] = {"rows": brief_g_rows}

        # transitions kept as-is

    # arrangement_state.json is one of the 9 required top-level files (v3.6
    # item 9) — the block is always present, no degraded/omitted path.
    overview["arrangement"] = _arrangement_block(arrangement_doc)
    if scope == "brief":
        # simplify arrangement in brief scope to only block_count to save tokens
        arr = overview["arrangement"]
        overview["arrangement"] = {"block_count": arr.get("block_count")}

    overview["transitions"] = _transitions_block(timeline_doc, events)

    # human_hints: brief scope gets only the total count, otherwise the full block
    if scope == "brief":
        overview["human_hints"] = {"total_hints": total_hints}
    else:
        overview["human_hints"] = _hints_block(hints_doc)

    return overview


def _r(value: Any, places: int = 3) -> Any:
    return round(value, places) if isinstance(value, (int, float)) else value


# --------------------------------------------------------------------------- #
# position — musical addressing (v3.7 item 3/5). `{"bar", "beat", "section_id",
# "resolved"}`, derived on read from the published beat grid + sections.json.
# Never stored: seconds remain the only stored/joined unit in src/. `section_id`
# here always means the PUBLISHED sections.json (v3.7 item 6 generalises the
# same rule to hints.py/gestures.py's own stored `section_id` fields).
# --------------------------------------------------------------------------- #

#: corpus-wide 4/4 assumption (docs/analysis-definition.md "corpus is 4/4 and
#: constant BPM") — never inferred per song, never hedged about meter changes.
BEATS_PER_BAR = 4


def _section_id_for_time(time_s: float, sections: list[dict]) -> str | None:
    for s in sections:
        if float(s["start"]) <= time_s < float(s["end"]):
            return s.get("section_id")
    if sections and time_s >= float(sections[-1]["start"]):
        return sections[-1].get("section_id")
    return None


def _downbeat_confidence_for_bar(bar: int, beats: list[dict]) -> float | None:
    """The `downbeat_confidence` on `bar`'s own downbeat (`beat == 1`) row.
    Only the downbeat row carries this value — the other 3 beats of a 4/4
    bar publish `downbeat_confidence: null` on their own row regardless of
    whether the bar's downbeat was confidently detected, so `_position` must
    look this up rather than read the nearest beat row's own field."""
    for b in beats:
        if int(b["bar"]) == bar and int(b["beat"]) == 1:
            return b.get("downbeat_confidence")
    return None


def _nearest_beat_at_or_before(time_s: float, beats: list[dict]) -> dict | None:
    best = None
    for b in beats:
        t = float(b["time"])
        if t <= time_s + 1e-9 and (best is None or t > float(best["time"])):
            best = b
    return best


def _nearest_beat_after(time_s: float, beats: list[dict]) -> dict | None:
    best = None
    for b in beats:
        t = float(b["time"])
        if t > time_s + 1e-9 and (best is None or t < float(best["time"])):
            best = b
    return best


def _beat_index(bar: int, beat: int) -> float:
    return (bar - 1) * BEATS_PER_BAR + (beat - 1)


def _extrapolate_bar_beat(anchor: dict, delta_beats: float) -> tuple[int, int]:
    """`anchor`'s (bar, beat) shifted by `delta_beats` fractional beats
    (positive = forward), assuming 4/4. Used only when a time falls outside
    the published beat grid — the one case this module extrapolates rather
    than reads a detected beat."""
    index = _beat_index(int(anchor["bar"]), int(anchor["beat"])) + delta_beats
    bar = int(index // BEATS_PER_BAR) + 1
    beat = int(round(index % BEATS_PER_BAR)) + 1
    if beat > BEATS_PER_BAR:
        beat = 1
        bar += 1
    return max(bar, 1), beat


def _position(
    time_s: float | None, beats: list[dict], sections: list[dict], bpm: float | None
) -> dict[str, Any] | None:
    """`{"bar", "beat", "section_id", "resolved"}` for `time_s`. `None` when
    `time_s` is `None` — an absent time has no position, never a guessed one.

    The common case reads `bar`/`beat` directly off the nearest published
    beat at-or-before `time_s` — no arithmetic. `resolved` reports whether
    *that bar* was itself grounded in a detected downbeat: `false` when the
    governing beat row's `downbeat_confidence` is `null` (allin1's downbeat
    phase measures ~0.226 F1 — CLAUDE.md: never present a guessed bar as
    detected). Only when `time_s` falls before the first published beat does
    this extrapolate by tempo arithmetic off the nearest beat — always
    `resolved: false` there, since no beat was actually detected at that
    instant."""
    if time_s is None:
        return None
    time_s = float(time_s)
    section_id = _section_id_for_time(time_s, sections)

    at = _nearest_beat_at_or_before(time_s, beats)
    if at is not None:
        bar = int(at["bar"])
        return {
            "bar": bar,
            "beat": int(at["beat"]),
            "section_id": section_id,
            "resolved": _downbeat_confidence_for_bar(bar, beats) is not None,
        }

    after = _nearest_beat_after(time_s, beats)
    if after is not None and bpm:
        beat_period = 60.0 / float(bpm)
        delta_beats = (time_s - float(after["time"])) / beat_period
        bar, beat = _extrapolate_bar_beat(after, delta_beats)
        return {"bar": bar, "beat": beat, "section_id": section_id, "resolved": False}

    return {"bar": None, "beat": None, "section_id": section_id, "resolved": False}


def _time_for_bar_beat(
    bar: int, beat: int, beats: list[dict], bpm: float | None
) -> float | None:
    """Inverse of `_position`: the time of a given `(bar, beat)`, for the
    `bars` `get_detail` scope selector. Reads the published beat row when one
    exists; otherwise extrapolates off the nearest published beat by tempo
    arithmetic (4/4). `None` only when there is no beat grid and no bpm to
    extrapolate from at all."""
    for b in beats:
        if int(b["bar"]) == bar and int(b["beat"]) == beat:
            return float(b["time"])
    if not beats or not bpm:
        return None
    target_index = _beat_index(bar, beat)
    anchor = min(
        beats,
        key=lambda b: abs(_beat_index(int(b["bar"]), int(b["beat"])) - target_index),
    )
    anchor_index = _beat_index(int(anchor["bar"]), int(anchor["beat"]))
    beat_period = 60.0 / float(bpm)
    return float(anchor["time"]) + (target_index - anchor_index) * beat_period


def _make_position_fn(beats: list[dict], sections: list[dict], bpm: float | None):
    return lambda time_s: _position(time_s, beats, sections, bpm)


def _attach_positions(
    rows: list[dict], fields: list[tuple[str, str]], pos_fn
) -> None:
    """Mutates `rows` in place: for each `(time_field, position_field)` pair,
    adds `position_field` beside `time_field` (v3.7 item 3/5). A row missing
    `time_field` (or carrying `None`) gets `position_field: None` — never a
    guessed position."""
    for row in rows:
        for time_field, pos_field in fields:
            row[pos_field] = pos_fn(row.get(time_field))


def _identity_block(info: dict, sections: list[dict], genre_doc: dict) -> dict[str, Any]:
    keys = [s.get("key") for s in sections if s.get("key")]
    unique = list(dict.fromkeys(keys))
    if not unique:
        whole_key: Any = None
    elif len(unique) == 1:
        whole_key = unique[0]
    else:
        whole_key = {"varies": unique}

    # genre.json is a required top-level file (v3.6 item 9) — always present.
    # `guidance` was dropped from the file (one identical text across the
    # corpus) and lives once in the get_song_overview tool description instead.
    genre = {
        "genres": genre_doc.get("genres"),
        "confidence": genre_doc.get("confidence"),
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
    # `label` / `description` / `chord_progression` were dropped from
    # sections.json in v3.6 item 8 (display prose, moved to a debugger-only
    # inner-folder file this module must never read — see loaders.py's
    # exposure guard). function_status is a required field on every row; a
    # shape that lacks it is a bug to surface loudly, never a silent
    # "unknown" default.
    rows = [
        {
            "section_id": s["section_id"],
            "start": s["start"],
            "end": s["end"],
            "function": s["function"],
            "function_confidence": s["function_confidence"],
            "function_status": s["function_status"],
            "same_label_as": s["same_label_as"],
            "confidence": s["confidence"],
            **_section_clue_fields(s),
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
        # determine impact_time if an impact phase exists
        impact_row = next((r for r in phase_rows if r.get("type") == "impact"), None)
        impact_time = impact_row.get("start_time") if impact_row is not None else None
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
                "impact_time": impact_time,
            }
        )
    return {
        "rows": rows,
        "field_sources": timeline_doc.get("field_sources"),
    }


def _arrangement_block(doc: dict, pos_fn=None) -> dict[str, Any]:
    """Compact per-block stem-state view from the required top-level
    arrangement_state.json. One row per block, `start`/`end` to match the
    sibling sections/gestures rows. `confidence` (and the leading block's
    `null`) is passed through as-is; `margin_db` and per-row sources are left to
    get_detail's structural view.

    `vocals_phrase` (v3.5 item 7 promotion) is a second, independent read on
    the vocals stem from the `whisperx_vad` detector (its own pipeline
    service, v3.6 item 2) — every span's `confidence` is `1.0` by the
    operator's own rule (a detected phrase is asserted certain, not
    graded)."""
    blocks = doc.get("blocks", [])
    rows = [
        {
            "start": b.get("start_s"),
            "end": b.get("end_s"),
            "playing": b.get("playing", []),
            "entered": b.get("entered", []),
            "left": b.get("left", []),
            "confidence": b.get("confidence"),
        }
        for b in blocks
    ]
    vocals_phrase = [dict(p) for p in (doc.get("vocals_phrase") or [])]
    if pos_fn is not None:
        _attach_positions(rows, [("start", "start_position"), ("end", "end_position")], pos_fn)
        _attach_positions(
            vocals_phrase, [("start_s", "start_position"), ("end_s", "end_position")], pos_fn
        )
    return {
        "block_count": len(blocks),
        "blocks": rows,
        "vocals_phrase": vocals_phrase,
        "vocals_sibilance_song_mean": doc.get("vocals_sibilance_song_mean"),
        "field_sources": doc.get("field_sources"),
    }


def _transitions_block(timeline_doc: dict, events: list[dict], pos_fn=None) -> dict[str, Any]:
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
    if pos_fn is not None:
        _attach_positions(rows, [("time", "position")], pos_fn)
    return {
        "rows": rows,
        "field_sources": timeline_doc.get("field_sources"),
    }


def _hints_block(hints_doc: dict, pos_fn=None) -> dict[str, Any]:
    # v3.6 item 8 restructured hints.json to a flat `hints[]` (no `sections[]`
    # wrapper — that duplicated sections.json's join). Every row is human by
    # construction; `source` is declared once here rather than per row.
    rows = []
    for hint in hints_doc.get("hints", []):
        row = {
            "section_id": hint.get("section_id"),
            "title": hint.get("title"),
            "text": hint.get("text"),
            "start_time": hint.get("start_time"),
            "end_time": hint.get("end_time"),
        }
        if hint.get("lighting_hint") is not None:
            row["lighting_hint"] = hint["lighting_hint"]
        rows.append(row)
    if pos_fn is not None:
        _attach_positions(rows, [("start_time", "start_position"), ("end_time", "end_position")], pos_fn)
    return {
        "rows": rows,
        "source": "human",
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
    bars: list[int] | None = None,
    interval_ms: int | None = None,
    sources: list[str] | None = None,
    root: str | Path | None = None,
) -> dict[str, Any]:
    """Dense detail for one resolved span.

    Exactly one scope selector is required — `section_id`, `gesture_id`,
    `start_ms` + `end_ms`, or `bars` (v3.7 item 5, `[start_bar, end_bar]`
    inclusive). Zero or two is an error (no precedence rule). A span longer
    than the 5 s cap returns the structural view with the dense frames
    withheld and the cap named. `interval_ms` is caller-chosen and decimates the
    published 20 ms series by pair-averaging; finer than 20 ms is an error.
    """
    song_dir = resolve_song_dir(song, root=root)

    info_doc = load_top_level_json(song_dir, "info.json")
    sections_doc = load_top_level_json(song_dir, "sections.json")
    timeline_doc = load_top_level_json(song_dir, "song_event_timeline.json")
    hints_doc = load_top_level_json(song_dir, "hints.json")
    arrangement_doc = load_top_level_json(song_dir, "arrangement_state.json")
    drum_doc = load_top_level_json(song_dir, "drum_events.json")
    # beats.json (v3.6 item 9): the structural view's `beats` block is the one
    # deliberate exception to "no full beat list ever leaves this module" — it
    # is scoped to the resolved span, undecimated, and present even past the
    # dense-series cap (unlike loudness's dense frames, which the cap withholds).
    beats_doc = load_top_level_json(song_dir, "beats.json")
    beats_list = beats_doc.get("beats", [])
    bpm = info_doc.get("bpm")

    scope, span_start, span_end = _resolve_span(
        section_id=section_id,
        gesture_id=gesture_id,
        start_ms=start_ms,
        end_ms=end_ms,
        bars=bars,
        sections=sections_doc.get("sections", []),
        events=timeline_doc.get("events", []),
        beats=beats_list,
        bpm=bpm,
    )
    pos_fn = _make_position_fn(beats_list, sections_doc.get("sections", []), bpm)

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
        "span": {
            "start": span_start,
            "end": span_end,
            "duration": duration,
            "start_position": pos_fn(span_start),
            "end_position": pos_fn(span_end),
        },
        "structural": _structural_view(
            span_start, span_end, sections_doc, timeline_doc, hints_doc,
            arrangement_doc, drum_doc, beats_doc, events, pos_fn
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

    loudness_doc = load_top_level_json(song_dir, "loudness.json")
    response["dense"] = _dense_frames(
        loudness_doc, span_start, span_end, target_interval, stem_set, pos_fn
    )
    return response


def _resolve_span(
    *,
    section_id: str | None,
    gesture_id: str | None,
    start_ms: int | None,
    end_ms: int | None,
    bars: list[int] | None,
    sections: list[dict],
    events: list[dict],
    beats: list[dict],
    bpm: float | None,
) -> tuple[dict[str, Any], float, float]:
    has_window = start_ms is not None or end_ms is not None
    selectors = [section_id is not None, gesture_id is not None, has_window, bars is not None]
    chosen = sum(selectors)

    if chosen == 0:
        raise DetailScopeError(
            "a scope selector is required: section_id, gesture_id, "
            "start_ms + end_ms, or bars"
        )
    if chosen > 1:
        raise DetailScopeError(
            "exactly one scope selector is allowed (section_id, gesture_id, "
            "start_ms + end_ms, or bars) — there is no precedence rule; pass just one"
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

    if bars is not None:
        if len(bars) != 2:
            raise DetailScopeError(f"bars must be [start_bar, end_bar], got {bars!r}")
        start_bar, end_bar = int(bars[0]), int(bars[1])
        if start_bar < 1 or end_bar < start_bar:
            raise DetailScopeError(
                f"bars must satisfy 1 <= start_bar <= end_bar, got {bars!r}"
            )
        span_start_t = _time_for_bar_beat(start_bar, 1, beats, bpm)
        span_end_t = _time_for_bar_beat(end_bar + 1, 1, beats, bpm)
        if span_start_t is None or span_end_t is None:
            raise DetailScopeError(
                f"cannot resolve bars {bars!r} — no beat grid or bpm to derive bar "
                "times from"
            )
        return (
            {"kind": "bars", "bars": [start_bar, end_bar]},
            span_start_t,
            span_end_t,
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
    arrangement_doc: dict,
    drum_doc: dict,
    beats_doc: dict,
    events: list[dict],
    pos_fn=None,
) -> dict[str, Any]:
    section_rows = [
        {
            "section_id": s["section_id"],
            "start": s["start"],
            "end": s["end"],
            "function": s["function"],
            "function_status": s["function_status"],
            "same_label_as": s["same_label_as"],
            **_section_clue_fields(s),
        }
        for s in sections_doc.get("sections", [])
        if _overlaps(span_start, span_end, float(s["start"]), float(s["end"]))
    ]
    if pos_fn is not None:
        _attach_positions(section_rows, [("start", "start_position"), ("end", "end_position")], pos_fn)
        for _row in section_rows:
            _ia = _row.get("impact_alignment")
            if _ia is not None:
                _ia["impact_position"] = pos_fn(_ia.get("impact_time"))

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
    if pos_fn is not None:
        _attach_positions(phase_rows, [("start", "start_position"), ("end", "end_position")], pos_fn)

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
    if pos_fn is not None:
        _attach_positions(transition_rows, [("time", "position")], pos_fn)

    hint_rows = []
    for hint in hints_doc.get("hints", []):
        h_start = hint.get("start_time")
        h_end = hint.get("end_time")
        if h_start is None or h_end is None:
            continue
        if _overlaps(span_start, span_end, float(h_start), float(h_end)):
            row = {
                "section_id": hint.get("section_id"),
                "title": hint.get("title"),
                "text": hint.get("text"),
                "start_time": h_start,
                "end_time": h_end,
            }
            if hint.get("lighting_hint") is not None:
                row["lighting_hint"] = hint["lighting_hint"]
            hint_rows.append(row)
    if pos_fn is not None:
        _attach_positions(hint_rows, [("start_time", "start_position"), ("end_time", "end_position")], pos_fn)

    intensities = [r["intensity"] for r in phase_rows if r["intensity"] is not None]
    if intensities:
        aggregate = {
            "peak": max(intensities),
            "mean": round(sum(intensities) / len(intensities), 6),
        }
    else:
        aggregate = None

    # Drum events: structural rows overlapping the window, plus the file-level
    # confidence/confidence_reason pair (v3.6 item 8 collapsed the per-event
    # `confidence` — always null across the whole corpus — to one file-level
    # pair, so it is surfaced once here, never repeated null on every row).
    drum_rows: list[dict] = []
    for e in drum_doc.get("events", []):
        t = e.get("time")
        if t is None:
            continue
        if span_start <= float(t) <= span_end:
            drum_rows.append({"time": t, "event_type": e.get("event_type")})
    if pos_fn is not None:
        _attach_positions(drum_rows, [("time", "position")], pos_fn)

    # Apply sparse-row cap: if there are more rows than SPARSE_ROW_CAP, do not
    # silently truncate. Instead present an explicit withheld block so callers
    # can distinguish a data cap from an empty result.
    if len(drum_rows) > SPARSE_ROW_CAP:
        drum_block = {
            "rows": [],
            "field_sources": drum_doc.get("field_sources"),
            "summary": drum_doc.get("summary"),
            "confidence": drum_doc.get("confidence"),
            "confidence_reason": drum_doc.get("confidence_reason"),
            "sparse_withheld": {
                "reason": (
                    f"sparse event cap exceeded: observed {len(drum_rows)} rows, "
                    f"cap {SPARSE_ROW_CAP} rows"
                ),
                "observed_rows": len(drum_rows),
                "cap_rows": SPARSE_ROW_CAP,
            },
        }
    else:
        drum_block = {
            "rows": drum_rows,
            "field_sources": drum_doc.get("field_sources"),
            "summary": drum_doc.get("summary"),
            "confidence": drum_doc.get("confidence"),
            "confidence_reason": drum_doc.get("confidence_reason"),
        }

    # Beats: every beat inside the resolved span, undecimated. This is the one
    # deliberate exception to "no full beat list" and to the dense-series cap —
    # the caller sees it in the structural view even when `dense` is withheld.
    beat_rows = [
        {
            "time": b["time"],
            "bar": b["bar"],
            "beat": b["beat"],
            "downbeat_confidence": b.get("downbeat_confidence"),
        }
        for b in beats_doc.get("beats", [])
        if span_start <= float(b["time"]) <= span_end
    ]

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
            "source": "human",
            "field_sources": hints_doc.get("field_sources"),
        },
        "arrangement": _arrangement_structural(arrangement_doc, span_start, span_end, pos_fn),
        "drum_events": drum_block,
        "beats": {
            "rows": beat_rows,
            "field_sources": beats_doc.get("field_sources"),
        },
        "aggregate_intensity": aggregate,
    }


def _arrangement_structural(
    doc: dict, span_start: float, span_end: float, pos_fn=None
) -> dict[str, Any]:
    """Overlapping arrangement_state blocks for the resolved span. Structural
    block data — no decimation, no dense cap — so it is present in the
    structural view even when the span exceeds DENSE_CAP_S. arrangement_state
    is a required top-level file (v3.6 item 9) — always present."""
    rows = [
        {
            "start_s": b.get("start_s"),
            "end_s": b.get("end_s"),
            "playing": b.get("playing", []),
            "entered": b.get("entered", []),
            "left": b.get("left", []),
            "margin_db": b.get("margin_db"),
            "confidence": b.get("confidence"),
        }
        for b in doc.get("blocks", [])
        if _overlaps(span_start, span_end, float(b["start_s"]), float(b["end_s"]))
    ]
    vocals_phrase = [
        {
            "start_s": p.get("start_s"),
            "end_s": p.get("end_s"),
            "confidence": p.get("confidence"),
            "sibilance": p.get("sibilance"),
        }
        for p in (doc.get("vocals_phrase") or [])
        if _overlaps(span_start, span_end, float(p["start_s"]), float(p["end_s"]))
    ]
    if pos_fn is not None:
        _attach_positions(rows, [("start_s", "start_position"), ("end_s", "end_position")], pos_fn)
        _attach_positions(vocals_phrase, [("start_s", "start_position"), ("end_s", "end_position")], pos_fn)
    return {
        "rows": rows,
        "vocals_phrase": vocals_phrase,
        "vocals_sibilance_song_mean": doc.get("vocals_sibilance_song_mean"),
        "field_sources": doc.get("field_sources"),
    }


def _dense_frames(
    loudness_doc: dict,
    span_start: float,
    span_end: float,
    interval_ms: int,
    stem_set: list[str],
    pos_fn=None,
) -> dict[str, Any]:
    # v3.6 item 8 flattened interval_ms/source_order out of a `metadata`
    # wrapper to top-level fields on loudness.json.
    published_order = loudness_doc.get("source_order", list(DEFAULT_SOURCES))
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
        frames.append(_average_chunk(chunk, keep_idx, pos_fn))

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


def _average_chunk(chunk: list[dict], keep_idx: list[int], pos_fn=None) -> dict[str, Any]:
    n = len(chunk)
    time = round(sum(f["time"] for f in chunk) / n, 6)
    values = [
        round(sum(f["values"][i] for f in chunk) / n, 6) for i in keep_idx
    ]
    normalized = [
        round(sum(f["normalized_values"][i] for f in chunk) / n, 6)
        for i in keep_idx
    ]
    row: dict[str, Any] = {"time": time, "values": values, "normalized_values": normalized}
    if pos_fn is not None:
        row["position"] = pos_fn(time)
    return row
