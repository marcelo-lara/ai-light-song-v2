"""Phase-4 publish stage — `vocal_cadence.json` (v3.9 item 1).

Promotes `experiments/vocal_cadence/` (12/12 on the operator's own Queen of
Kings facts — see `docs/analysis-definition.md` and
`docs/archive/experiments.promoted.vocal-cadence.md`) into the pipeline.
`src/` never imports `experiments/` (CLAUDE.md) — this module is a port, not
a caller.

Reads the operator's own lyric alignment (`reference/human/lyrics.json` >
`reference/moises/lyrics.json` — a publish stage may read `reference/`, no
interpret/relate stage may) plus the already-PUBLISHED `beats.json`,
`sections.json` and `info.json`. Never `reference/human/segments.json` — this
stage publishes strictly off the top-level `sections.json`, the only section
boundary the MCP or downstream contract ever sees.

TIMING ONLY. No lyric token text survives parsing: the only thing read from a
token's `text` field is (a) whether it is a `<SOL>`/`<EOL>` marker (excluded
from onsets and calls), and (b) whether the WHOLE stripped text is wrapped in
parentheses, e.g. `(hey)` — that token becomes a call event carrying only a
time, never text. Every other token becomes a bare onset (`start`/`end`
only). No dataclass or dict past `_build_lines` carries a text field —
`tests/test_vocal_cadence.py::test_no_lyric_text_in_output` guards this
against Queen of Kings.

D1.1 — always written. No lyrics tier -> `source: null`, empty
`lines`/`sections`/`calls`, `reason` set. The MCP's every-top-level-file-
required rule stays intact; an optional file would be its first exception.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field as dataclass_field

from analyzer.io import read_json, write_json
from analyzer.models import SCHEMA_VERSION, validate_field_sources
from analyzer.paths import SongPaths

BEATS_PER_BAR = 4
MARKERS = ("<SOL>", "<EOL>")

MATCH_TOLERANCE_MS = 80.0
CADENCE_MATCH_THRESHOLD = 0.5
BAR_OFFSET_RANGE = range(-4, 5)
MIN_REST_BEATS = 1.0
MIN_HELD_NOTE_BEATS = 2.0
RESOLVE_TOLERANCE_MS = 80.0
LEAD_IN_SEARCH_BARS_BEFORE = 2
LEAD_IN_SEARCH_BARS_AFTER = 1
LEAD_IN_MAX_GAP_BARS = 1.0


# ---------------------------------------------------------------- records --

@dataclass(frozen=True)
class Onset:
    token_id: int
    line_id: int
    start: float
    end: float


@dataclass(frozen=True)
class Call:
    token_id: int
    line_id: int
    time: float


@dataclass(frozen=True)
class Line:
    line_id: int
    start: float
    end: float
    onsets: tuple[Onset, ...] = dataclass_field(default_factory=tuple)
    calls: tuple[Call, ...] = dataclass_field(default_factory=tuple)

    @property
    def token_count(self) -> int:
        return len(self.onsets)


@dataclass(frozen=True)
class BeatRow:
    time: float
    bar: int
    beat: int
    downbeat_confidence: float | None


@dataclass(frozen=True)
class Section:
    section_id: str
    start: float
    end: float


@dataclass(frozen=True)
class PatternOnset:
    """One cadence onset, relative to a section's own boundary, in beats
    (negative for a lead-in onset that precedes the boundary)."""
    rel_beats: float
    abs_time: float


# ------------------------------------------------------------- lyrics tier --

def _is_call_token(text: str) -> bool:
    """A token is a call only when its ENTIRE text (once stripped) is
    wrapped in parentheses, e.g. `(hey)`. A token that merely contains a
    parenthesised aside is left as an ordinary cadence onset — a known,
    documented gap (see the archived experiment TLDR)."""
    t = text.strip()
    return len(t) >= 2 and t[0] == "(" and t[-1] == ")"


def _load_lyrics(paths: SongPaths) -> tuple[list[dict] | None, str | None]:
    """`(raw_tokens, tier)`, tier `"human"` or `"moises"`. `(None, None)`
    when neither exists — the caller writes an honest empty file, never
    infers."""
    human = paths.reference("human", "lyrics.json")
    if human.exists():
        return read_json(human), "human"
    moises = paths.reference("moises", "lyrics.json")
    if moises.exists():
        return read_json(moises), "moises"
    return None, None


def _build_lines(raw_tokens: list[dict]) -> list[Line]:
    """Groups tokens by `line_id`, first-seen order. `<SOL>`/`<EOL>` are
    dropped; a fully-parenthesised token becomes a `Call`, everything else an
    `Onset`. `line.start`/`line.end` are the min/max over the line's own
    onsets/calls (never the marker times)."""
    order: list[int] = []
    by_line: dict[int, list[dict]] = {}
    for tok in raw_tokens:
        lid = int(tok["line_id"])
        if lid not in by_line:
            by_line[lid] = []
            order.append(lid)
        by_line[lid].append(tok)

    lines: list[Line] = []
    for lid in order:
        onsets: list[Onset] = []
        calls: list[Call] = []
        for tok in by_line[lid]:
            text = tok.get("text", "")
            if text in MARKERS:
                continue
            start = float(tok["start"])
            end = float(tok["end"])
            tid = int(tok["id"])
            if _is_call_token(text):
                calls.append(Call(token_id=tid, line_id=lid, time=start))
            else:
                onsets.append(Onset(token_id=tid, line_id=lid, start=start, end=end))
        if not onsets and not calls:
            continue
        starts = [o.start for o in onsets] + [c.time for c in calls]
        ends = [o.end for o in onsets] + [c.time for c in calls]
        lines.append(
            Line(
                line_id=lid,
                start=min(starts),
                end=max(ends),
                onsets=tuple(sorted(onsets, key=lambda o: o.start)),
                calls=tuple(sorted(calls, key=lambda c: c.time)),
            )
        )
    return sorted(lines, key=lambda l: l.start)


# ------------------------------------------------------------ beats/sections

def _load_beats(paths: SongPaths) -> list[BeatRow]:
    doc = read_json(paths.beats_output_path)
    return [
        BeatRow(
            time=float(b["time"]),
            bar=int(b["bar"]),
            beat=int(b["beat"]),
            downbeat_confidence=b.get("downbeat_confidence"),
        )
        for b in doc["beats"]
    ]


def _load_bpm(paths: SongPaths) -> float | None:
    return read_json(paths.info_output_path).get("bpm")


def _load_sections(paths: SongPaths) -> list[Section]:
    doc = read_json(paths.sections_output_path)
    return [
        Section(section_id=row["section_id"], start=float(row["start"]), end=float(row["end"]))
        for row in doc["sections"]
    ]


# ------------------------------------------------------- bar/beat addressing

def _nearest_at_or_before(time_s: float, beats: list[BeatRow]) -> BeatRow | None:
    best = None
    for b in beats:
        if b.time <= time_s + 1e-9 and (best is None or b.time > best.time):
            best = b
    return best


def _nearest_after(time_s: float, beats: list[BeatRow]) -> BeatRow | None:
    best = None
    for b in beats:
        if b.time > time_s + 1e-9 and (best is None or b.time < best.time):
            best = b
    return best


def _downbeat_confidence_for_bar(bar: int, beats: list[BeatRow]) -> float | None:
    for b in beats:
        if b.bar == bar and b.beat == 1:
            return b.downbeat_confidence
    return None


def _beat_index(bar: int, beat: int) -> float:
    return (bar - 1) * BEATS_PER_BAR + (beat - 1)


def _position(time_s: float | None, beats: list[BeatRow]) -> dict | None:
    """`{"bar", "beat", "resolved"}` off the nearest published beat
    at-or-before `time_s`. Mirrors `mcp/serializers.py`'s `_position`
    convention: `resolved` reports the governing bar's OWN downbeat
    confidence, never guessed."""
    if time_s is None:
        return None
    at = _nearest_at_or_before(time_s, beats)
    if at is not None:
        return {
            "bar": at.bar,
            "beat": at.beat,
            "resolved": _downbeat_confidence_for_bar(at.bar, beats) is not None,
        }
    return {"bar": None, "beat": None, "resolved": False}


def _time_for_bar_beat(bar: int, beat: int, beats: list[BeatRow], bpm: float | None) -> float | None:
    for b in beats:
        if b.bar == bar and b.beat == beat:
            return b.time
    if not beats or not bpm:
        return None
    target = _beat_index(bar, beat)
    anchor = min(beats, key=lambda b: abs(_beat_index(b.bar, b.beat) - target))
    anchor_index = _beat_index(anchor.bar, anchor.beat)
    beat_period = 60.0 / float(bpm)
    return anchor.time + (target - anchor_index) * beat_period


def _fractional_beat_index(time_s: float, beats: list[BeatRow], bpm: float | None) -> float | None:
    """A fractional beat count via linear interpolation between the two
    published beats bracketing `time_s` — measures durations/offsets at the
    LOCAL tempo rather than one song-wide bpm. Falls back to tempo
    extrapolation off the nearest beat outside the published grid."""
    at = _nearest_at_or_before(time_s, beats)
    after = _nearest_after(time_s, beats)
    if at is not None and after is not None and after.time > at.time:
        frac = (time_s - at.time) / (after.time - at.time)
        return _beat_index(at.bar, at.beat) + frac * (
            _beat_index(after.bar, after.beat) - _beat_index(at.bar, at.beat)
        )
    anchor = at or after
    if anchor is not None and bpm:
        beat_period = 60.0 / float(bpm)
        return _beat_index(anchor.bar, anchor.beat) + (time_s - anchor.time) / beat_period
    return None


def _beats_between(t0: float, t1: float, beats: list[BeatRow], bpm: float | None) -> float | None:
    a = _fractional_beat_index(t0, beats, bpm)
    b = _fractional_beat_index(t1, beats, bpm)
    if a is None or b is None:
        return None
    return b - a


# ----------------------------------------------------------------- cadence --

def _resolve_downbeat(
    line: Line, beats: list[BeatRow], tolerance_ms: float = RESOLVE_TOLERANCE_MS,
) -> BeatRow | None:
    """The downbeat `line` "resolves on": the earliest downbeat within
    `tolerance_ms` of the line's span whose time is also within
    `tolerance_ms` of one of the line's token onsets. `None` (never guessed)
    when no token lands on any candidate downbeat."""
    tol = tolerance_ms / 1000.0
    candidates = sorted(
        (b for b in beats if b.beat == 1 and (line.start - tol) <= b.time <= (line.end + tol)),
        key=lambda b: b.time,
    )
    token_starts = [o.start for o in line.onsets]
    for db in candidates:
        if any(abs(ts - db.time) <= tol for ts in token_starts):
            return db
    return None


def _line_record(line: Line, beats: list[BeatRow], bpm: float | None) -> dict:
    start_pos = _position(line.start, beats)
    end_pos = _position(line.end, beats)
    duration_beats = _beats_between(line.start, line.end, beats, bpm)
    resolve_db = _resolve_downbeat(line, beats)
    resolve_time = resolve_db.time if resolve_db is not None else None
    resolve_position = _position(resolve_time, beats) if resolve_time is not None else None
    pickup = (
        None if resolve_db is None
        else bool(line.start < resolve_db.time - RESOLVE_TOLERANCE_MS / 1000.0)
    )
    return {
        "line_id": line.line_id,
        "start_s": round(line.start, 3),
        "end_s": round(line.end, 3),
        "start_position": start_pos,
        "end_position": end_pos,
        "duration_beats": round(duration_beats, 3) if duration_beats is not None else None,
        "token_count": line.token_count,
        "resolve_time_s": round(resolve_time, 3) if resolve_time is not None else None,
        "resolve_position": resolve_position,
        "pickup": pickup,
    }


def _owning_section_index(time_s: float, sections: list[Section]) -> int | None:
    for i, s in enumerate(sections):
        if s.start <= time_s < s.end:
            return i
    if sections and time_s >= sections[-1].start:
        return len(sections) - 1
    return None


def _lines_by_section(lines: list[Line], sections: list[Section]) -> dict[int, list[Line]]:
    owned: dict[int, list[Line]] = {i: [] for i in range(len(sections))}
    for line in lines:
        idx = _owning_section_index(line.start, sections)
        if idx is not None:
            owned[idx].append(line)
    return owned


def _section_pattern(
    idx: int, sections: list[Section], owned: dict[int, list[Line]],
    beats: list[BeatRow], bpm: float | None,
) -> tuple[list[PatternOnset], Line | None]:
    """The onset pattern for `sections[idx]`: its own owned lines' onsets,
    plus the previous section's trailing line when it spills over this
    section's boundary ("first line overlapping the section")."""
    section = sections[idx]
    lines = list(owned.get(idx, []))
    spillover_line = None
    if idx > 0:
        prev_lines = owned.get(idx - 1, [])
        if prev_lines and prev_lines[-1].end > section.start:
            spillover_line = prev_lines[-1]
            lines = [spillover_line] + lines

    pattern: list[PatternOnset] = []
    for line in lines:
        for onset in line.onsets:
            rel = _beats_between(section.start, onset.start, beats, bpm)
            if rel is not None:
                pattern.append(PatternOnset(rel_beats=rel, abs_time=onset.start))
    pattern.sort(key=lambda p: p.rel_beats)
    return pattern, spillover_line


def _gap_beats(a: Line, b: Line, beats: list[BeatRow], bpm: float | None) -> float | None:
    return _beats_between(a.end, b.start, beats, bpm)


def _chain_reaches_boundary(
    start_index: int, all_lines: list[Line], boundary: float,
    beats: list[BeatRow], bpm: float | None,
) -> bool:
    max_gap_beats = LEAD_IN_MAX_GAP_BARS * BEATS_PER_BAR
    i = start_index
    line = all_lines[i]
    if line.end >= boundary:
        return True
    while i + 1 < len(all_lines):
        nxt = all_lines[i + 1]
        gap = _gap_beats(line, nxt, beats, bpm)
        if gap is None or gap >= max_gap_beats:
            return False
        if nxt.end >= boundary:
            return True
        line = nxt
        i += 1
    return False


def _lead_in_bars(
    idx: int, sections: list[Section], all_lines: list[Line],
    beats: list[BeatRow], bpm: float | None,
) -> dict:
    """The downbeat the section's first line resolves on (after its own
    pickup), in whole bars relative to the section's boundary bar. 0 = the
    line lands on the hit; -1 = a bar early. Handles a short Fill/Pre-Drop
    section sitting directly in front of the boundary: among lines whose
    resolve downbeat falls within
    `[boundary - LEAD_IN_SEARCH_BARS_BEFORE, boundary + LEAD_IN_SEARCH_BARS_AFTER)`
    bars, takes the EARLIEST one whose chain of consecutive lines (gaps under
    `LEAD_IN_MAX_GAP_BARS`) is vocally continuous into the boundary."""
    section = sections[idx]
    boundary = section.start
    boundary_pos = _position(boundary, beats)
    boundary_bar = boundary_pos["bar"] if boundary_pos else None
    if boundary_bar is None:
        return {
            "bars": None, "line_id": None, "resolve_time_s": None,
            "resolve_position": None, "reason": "section boundary has no resolvable bar",
        }

    window_lo = boundary_bar - LEAD_IN_SEARCH_BARS_BEFORE
    window_hi = boundary_bar + LEAD_IN_SEARCH_BARS_AFTER

    resolved = [(i, l, _resolve_downbeat(l, beats)) for i, l in enumerate(all_lines)]
    candidates = [
        (i, l, db) for i, l, db in resolved
        if db is not None and window_lo <= db.bar < window_hi
    ]
    candidates.sort(key=lambda c: c[1].start)

    for i, line, db in candidates:
        if _chain_reaches_boundary(i, all_lines, boundary, beats, bpm):
            return {
                "bars": db.bar - boundary_bar,
                "line_id": line.line_id,
                "resolve_time_s": round(db.time, 3),
                "resolve_position": _position(db.time, beats),
                "reason": None,
            }

    reason = (
        "no line resolves on a downbeat in the search window" if not candidates
        else "no candidate line is vocally continuous into the boundary"
    )
    return {
        "bars": None, "line_id": None, "resolve_time_s": None,
        "resolve_position": None, "reason": reason,
    }


def _rests_and_held_notes(
    idx: int, spillover_line: Line | None, owned: dict[int, list[Line]],
    beats: list[BeatRow], bpm: float | None,
) -> tuple[list[dict], list[dict]]:
    lines = list(owned.get(idx, []))
    if spillover_line is not None:
        lines = [spillover_line] + lines

    rests: list[dict] = []
    for a, b in zip(lines, lines[1:]):
        gap = _beats_between(a.end, b.start, beats, bpm)
        if gap is not None and gap >= MIN_REST_BEATS:
            rests.append({"start_s": round(a.end, 3), "length_beats": round(gap, 3)})

    held: list[dict] = []
    for line in lines:
        for onset in line.onsets:
            length = _beats_between(onset.start, onset.end, beats, bpm)
            if length is not None and length >= MIN_HELD_NOTE_BEATS:
                held.append({"start_s": round(onset.start, 3), "length_beats": round(length, 3)})
    return rests, held


def _tokens_per_bar(
    idx: int, spillover_line: Line | None, owned: dict[int, list[Line]], beats: list[BeatRow],
) -> list[dict]:
    lines = list(owned.get(idx, []))
    if spillover_line is not None:
        lines = [spillover_line] + lines
    onsets = [o for line in lines for o in line.onsets]
    if not onsets:
        return []
    counts: dict[int, int] = {}
    for o in onsets:
        pos = _position(o.start, beats)
        bar = pos["bar"] if pos else None
        if bar is not None:
            counts[bar] = counts.get(bar, 0) + 1
    return [{"bar": bar, "tokens": counts[bar]} for bar in sorted(counts)]


def _match(
    query: list[PatternOnset], candidate: list[PatternOnset], offset_beats: float, beat_period_s: float,
) -> tuple[float, int, float | None]:
    """Greedy nearest-match of `query` onsets against `candidate` onsets
    shifted by `offset_beats`. `fraction` is over `len(query)` — the section
    being explained is the denominator."""
    if not query:
        return 0.0, 0, None
    tolerance_beats = (MATCH_TOLERANCE_MS / 1000.0) / beat_period_s
    shifted = sorted(candidate, key=lambda p: p.rel_beats)
    used = [False] * len(shifted)
    errors_ms: list[float] = []
    matched = 0
    for q in query:
        best_i, best_d = None, None
        for i, c in enumerate(shifted):
            if used[i]:
                continue
            d = abs(q.rel_beats - (c.rel_beats + offset_beats))
            if d <= tolerance_beats and (best_d is None or d < best_d):
                best_i, best_d = i, d
        if best_i is not None:
            used[best_i] = True
            matched += 1
            errors_ms.append(best_d * beat_period_s * 1000.0)
    fraction = matched / len(query)
    median_error = statistics.median(errors_ms) if errors_ms else None
    return fraction, matched, median_error


def _cadence_repeats(
    sections: list[Section], patterns: list[list[PatternOnset]], bpm: float | None,
) -> list[list[dict]]:
    """For each section, every EARLIER section whose onset pattern it
    repeats above `CADENCE_MATCH_THRESHOLD`, over `BAR_OFFSET_RANGE` whole
    bars. Approximated with a single song-wide beat period (corpus is
    near-constant BPM — CLAUDE.md)."""
    if not bpm:
        return [[] for _ in sections]
    beat_period_s = 60.0 / float(bpm)

    out: list[list[dict]] = []
    for i, query in enumerate(patterns):
        candidates: list[dict] = []
        for j in range(i):
            candidate = patterns[j]
            if not candidate or not query:
                continue
            best = None
            for k in BAR_OFFSET_RANGE:
                offset_beats = k * BEATS_PER_BAR
                fraction, matched, median_err = _match(query, candidate, offset_beats, beat_period_s)
                key = (fraction, -abs(k))
                if best is None or key > best[0]:
                    best = (key, k, fraction, matched, median_err)
            if best is not None and best[2] >= CADENCE_MATCH_THRESHOLD:
                _, k, fraction, matched, median_err = best
                candidates.append({
                    "section_id": sections[j].section_id,
                    "bar_offset": k,
                    "match_fraction": round(fraction, 4),
                    "onsets_matched": matched,
                    "onsets_total": len(query),
                    "median_error_ms": round(median_err, 2) if median_err is not None else None,
                    "best": False,
                })
        if candidates:
            best_candidate = max(candidates, key=lambda c: (c["match_fraction"], -abs(c["bar_offset"])))
            best_candidate["best"] = True
        out.append(candidates)
    return out


# ------------------------------------------------------------------ publish

def publish_vocal_cadence(paths: SongPaths, bpm: float | None = None) -> str:
    """Writes top-level `vocal_cadence.json`. Always written (D1.1) — no
    lyrics tier yields `source: null`, empty arrays, a `reason`.

    `bpm` is normally left `None`, which reads it off the published
    `info.json`. The full pipeline runs this stage before `info.json` is
    written (both derive from the same in-memory `timing["bpm"]`), so
    `pipeline.py` passes it explicitly there; a single-stage rerun (where
    `info.json` already exists) omits it.
    """
    raw_tokens, tier = _load_lyrics(paths)

    if raw_tokens is None:
        field_sources = validate_field_sources(
            {"lines": "unknown", "sections": "unknown", "calls": "unknown"},
            ("lines", "sections", "calls"),
            file="vocal_cadence.json",
            exempt=("source", "reason"),
        )
        payload = {
            "schema_version": SCHEMA_VERSION,
            "song_name": paths.song_name,
            "field_sources": field_sources,
            "source": None,
            "reason": (
                f"{paths.song_name}: no reference/human/lyrics.json and no "
                "reference/moises/lyrics.json — vocal_cadence needs an aligned "
                "lyric transcript; nothing to infer this from."
            ),
            "lines": [],
            "sections": [],
            "calls": [],
        }
        write_json(paths.vocal_cadence_output_path, payload)
        return str(paths.vocal_cadence_output_path)

    lines = _build_lines(raw_tokens)
    beats = _load_beats(paths)
    if bpm is None:
        bpm = _load_bpm(paths)
    sections = _load_sections(paths)

    owned = _lines_by_section(lines, sections)

    patterns: list[list[PatternOnset]] = []
    spillover_lines: list[Line | None] = []
    for i in range(len(sections)):
        pattern, spillover_line = _section_pattern(i, sections, owned, beats, bpm)
        patterns.append(pattern)
        spillover_lines.append(spillover_line)

    repeats = _cadence_repeats(sections, patterns, bpm)
    line_blocks = [_line_record(l, beats, bpm) for l in lines]

    section_blocks = []
    for i, section in enumerate(sections):
        rests, held = _rests_and_held_notes(i, spillover_lines[i], owned, beats, bpm)
        lead_in = _lead_in_bars(i, sections, lines, beats, bpm)
        section_blocks.append({
            "section_id": section.section_id,
            "start_s": round(section.start, 3),
            "end_s": round(section.end, 3),
            "lead_in_bars": lead_in["bars"],
            "lead_in_line_id": lead_in["line_id"],
            "lead_in_resolve_time_s": lead_in["resolve_time_s"],
            "lead_in_resolve_position": lead_in["resolve_position"],
            "lead_in_reason": lead_in["reason"],
            "rests": rests,
            "held_notes": held,
            "tokens_per_bar": _tokens_per_bar(i, spillover_lines[i], owned, beats),
            "cadence_repeats": repeats[i],
        })

    calls = []
    for line in lines:
        for c in line.calls:
            calls.append({"time_s": round(c.time, 3), "position": _position(c.time, beats)})
    calls.sort(key=lambda c: c["time_s"])

    field_sources = validate_field_sources(
        {"lines": tier, "sections": tier, "calls": tier},
        ("lines", "sections", "calls"),
        file="vocal_cadence.json",
        exempt=("source", "reason"),
    )
    payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": paths.song_name,
        "field_sources": field_sources,
        "source": tier,
        "reason": None,
        "lines": line_blocks,
        "sections": section_blocks,
        "calls": calls,
    }
    write_json(paths.vocal_cadence_output_path, payload)
    return str(paths.vocal_cadence_output_path)
