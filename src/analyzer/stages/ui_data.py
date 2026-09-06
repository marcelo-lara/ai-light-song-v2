from __future__ import annotations

import re

from analyzer.io import read_json, write_json
from analyzer.models import SCHEMA_VERSION, round_schema_float, validate_field_sources
from analyzer.paths import SongPaths

# Thresholds for projecting a compact harmonic form into sections.json.
#
# Measured on the four gold songs (docs/analysis-definition.md): exact
# root+quality agreement with Moises is 1.00 (_test_song) / 0.69 (Titanium) /
# 0.51 (Armin - Revolution) / 0.38 (Hideaway - Kiesza). Per-song *mean* chord
# confidence and the whole-song *global_key* confidence both cluster in a tight
# band (0.73-0.80 and 0.75-0.85 respectively) across all four songs regardless
# of that agreement spread, so neither discriminates a trustworthy song from an
# untrustworthy one. What does separate them is the *minimum* per-chord-event
# confidence within a song's low-agreement stretches: Hideaway dips to 0.459,
# Armin to 0.531, while _test_song's minimum is 0.850 and Titanium's (0.685)
# sits in between.
#
# CHORD_EVENT_CONFIDENCE_THRESHOLD gates chord_progression with a "weakest
# link" rule: a section's progression is only stated if every essentia chord
# event overlapping it clears this floor. One unreliable chord inside an
# otherwise-clean run makes the whole stated sequence untrustworthy — stating
# "Am-F-C-G" when one of those four is a coin flip is worse than saying
# nothing. 0.70 is chosen because it sits inside the gap between _test_song's
# floor (0.850, never gated out) and the bulk of Titanium's per-section minima
# (0.685-0.778, roughly half pass), while gating out most of Armin's and
# Hideaway's low-confidence stretches (mins as low as 0.531 / 0.459). Verified
# empirically below to produce a null-rate ordering that tracks the measured
# agreement: _test_song 0% null, Titanium ~50%, Armin and Hideaway both
# meaningfully higher (~60-85%).
CHORD_EVENT_CONFIDENCE_THRESHOLD = 0.70

# KEY_CONFIDENCE_THRESHOLD gates the section-level `key` string against
# essentia's whole-track HPCP key estimate (`global_key.confidence`). Unlike
# per-chord confidence, this value does not track the measured chord-agreement
# spread at all — it clusters 0.75-0.85 across all four gold songs, including
# the 1.00-agreement _test_song. That is expected: global key is a single,
# more robust estimate aggregated over the entire track, not a per-beat label,
# so it is evaluated on its own scale rather than tied to the local
# chord-progression gate above (a key claim is not automatically unsupported
# just because one section's local chords are shaky). 0.70 is a real floor —
# low enough that all four gold songs pass it (0.749-0.851), but not zero, so
# a genuinely weak key estimate on a future song is still honestly `null`
# rather than a silent default.
KEY_CONFIDENCE_THRESHOLD = 0.70

# Cap on the number of distinct chords shown in a chord_progression string
# when no short repeating cycle is found (see _dominant_cycle). Real sections
# on the gold songs run 5-16 distinct consecutive chords; 8 keeps the string
# short enough to read as a "progression" rather than a chord-by-chord log.
MAX_CHORD_PROGRESSION_CHORDS = 8


def _resolve_chord_for_time(time_s: float, chord_events: list[dict]) -> str | None:
    previous_label: str | None = None
    for event in chord_events:
        start_s = float(event["time"])
        end_s = float(event["end_s"])
        label = str(event["chord"])
        if start_s <= time_s < end_s:
            return label
        if time_s >= start_s:
            previous_label = label
        if time_s < start_s:
            break
    return previous_label or (str(chord_events[0]["chord"]) if chord_events else None)


def _section_index_prefix(section_id: str | None) -> str:
    if not section_id:
        return ""
    match = re.search(r"(\d+)", str(section_id))
    return f"{match.group(1)} " if match else ""


def _format_section_label(section: dict) -> str:
    """`<index> <Label> (<confidence>)`, e.g. `"003 Chorus (0.80)"`.

    `function_status == "unknown"` means allin1's name for this section is not
    trustworthy (an honest `unknown` beats a confident wrong
    label), so the raw, un-title-cased label token is shown with an explicit
    `[unverified]` marker rather than a polished name that would read as
    confident. `function_confidence` still displays — it is what made the name
    untrustworthy in aggregate, not a claim being retracted here.
    """
    prefix = _section_index_prefix(section.get("section_id"))
    function = section.get("function")
    confidence = section.get("function_confidence")

    suffix = ""
    if confidence is not None:
        try:
            suffix = f" ({round_schema_float(float(confidence)):.2f})"
        except (TypeError, ValueError):
            suffix = ""

    if section.get("function_status") == "unknown":
        label_text = f"{function or 'unlabeled'} [unverified]"
        return f"{prefix}{label_text}{suffix}"

    label_text = str(function).replace("_", " ").title() if function else "Unlabeled"
    return f"{prefix}{label_text}{suffix}"


def _ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _section_description(section: dict, occurrence: int) -> str:
    """One sentence built only from this section's own measured fields — its
    functional label, its position among same-labelled sections, its duration,
    and `same_label_as` — never an invented mood or energy claim."""
    function = section.get("function")
    try:
        duration_s = round(float(section["end"]) - float(section["start"]), 1)
    except (TypeError, ValueError, KeyError):
        duration_s = None
    duration_text = f"{duration_s:.1f}s" if duration_s is not None else "of unknown length"

    if not function or section.get("function_status") == "unknown":
        return f"Unverified section, {duration_text} — allin1's label for this song is not trustworthy."

    label_text = str(function).replace("_", " ")
    ordinal = _ordinal(occurrence)
    if section.get("same_label_as") is None:
        return f"The {ordinal} {label_text}, {duration_text} long."
    return f"The {ordinal} {label_text}, {duration_text} long, same label as the first {label_text}."


def _overlapping_chord_events(start_s: float, end_s: float, chord_events: list[dict]) -> list[dict]:
    """Chord events with any overlap with `[start_s, end_s)` — not just events
    fully contained in it, since a section can start or end mid-chord."""
    return [event for event in chord_events if float(event["time"]) < end_s and float(event["end_s"]) > start_s]


def _distinct_consecutive_chords(events: list[dict]) -> list[str]:
    """Chord labels in time order, collapsing immediate repeats (e.g. a chord
    split across a section boundary should not repeat itself in the string)."""
    labels: list[str] = []
    for event in events:
        label = str(event["chord"])
        if not labels or labels[-1] != label:
            labels.append(label)
    return labels


def _dominant_cycle(labels: list[str], max_len: int) -> list[str]:
    """The shortest repeating cycle that reproduces `labels` exactly (allowing
    a trailing partial repeat), e.g. `[Cm, D#, A#, Cm, D#, A#, Cm]` -> `[Cm,
    D#, A#]`. This is what "dominant repeating chord sequence" means for a
    section that loops a short progression many times. If no such cycle
    exists (the section doesn't loop cleanly), fall back to the first
    `max_len` distinct chords rather than printing every change."""
    n = len(labels)
    for period in range(1, n):
        # Require at least half a cycle of confirmation beyond the first full
        # cycle, so a single coincidental match at the far end of the list
        # (e.g. the last chord happening to equal the first) is not mistaken
        # for a genuine loop.
        trailing = n - period
        if trailing < period / 2:
            continue
        if all(labels[i] == labels[i % period] for i in range(n)):
            return labels[:period]
    return labels[:max_len]


def _section_chord_progression(start_s: float, end_s: float, chord_events: list[dict]) -> str | None:
    """The section's dominant repeating chord sequence, e.g. `"Am–F–C–G"`, or
    `None` when confidence is too low to state one honestly (no silent fallbacks
    no silent fallbacks — never an empty string or a placeholder). Gated by
    CHORD_EVENT_CONFIDENCE_THRESHOLD with a weakest-link rule: every chord
    event overlapping the section must individually clear the floor, not just
    the section's average. See the threshold comment above for the
    measurement this is based on."""
    overlapping = _overlapping_chord_events(start_s, end_s, chord_events)
    if not overlapping:
        return None
    for event in overlapping:
        confidence = event.get("confidence")
        if confidence is None or float(confidence) < CHORD_EVENT_CONFIDENCE_THRESHOLD:
            return None
    labels = _distinct_consecutive_chords(overlapping)
    cycle = _dominant_cycle(labels, MAX_CHORD_PROGRESSION_CHORDS)
    return "–".join(cycle)


def _song_key(global_key: dict | None) -> str | None:
    """The whole-song key label (e.g. `"C# major"`), or `None` when
    essentia's HPCP key confidence is too low to state one. `global_key` is a
    single value for the whole song (not per-section), so every section
    either carries this same string or `None` — see the threshold comment
    above for why this is gated independently of the per-chord floor."""
    if not global_key:
        return None
    label = global_key.get("label")
    confidence = global_key.get("confidence")
    if not label or confidence is None:
        return None
    try:
        if float(confidence) < KEY_CONFIDENCE_THRESHOLD:
            return None
    except (TypeError, ValueError):
        return None
    return str(label)


# v3.1 items 5-7 — publish top-level views of three signals that live only under
# artifacts/ today (genre, drum events, loudness). These are FUSED VIEWS, not
# moves: the artifact stays put for the analyzer and the debugger, and the
# top-level file is rebuilt from it each run with a `field_sources` header and no
# host paths. The selection goes through `_fuse` — "which producer wins this
# field" — even though one producer answers every field today, so a second
# producer can be added without rewriting the publisher (plan D4).


def _fuse(field_candidates: dict[str, list[tuple[str, bool]]]) -> dict[str, str]:
    """For each field, the first candidate producer whose value is present wins.

    `field_candidates` maps a field name to an ordered list of
    `(producer, is_available)` pairs. Today every list has one entry; the shape
    is what lets a higher-confidence second producer slot in later. A field with
    no available producer resolves to `"unknown"` — an honest gap, never a guess.
    """
    return {
        field: next((producer for producer, available in candidates if available), "unknown")
        for field, candidates in field_candidates.items()
    }


def _publish_genre(paths: SongPaths) -> str:
    artifact = read_json(paths.artifact("genre.json"))

    def _present(key: str) -> bool:
        return artifact.get(key) is not None

    field_sources = validate_field_sources(
        _fuse(
            {
                "genres": [("genre", _present("genres"))],
                "confidence": [("genre", _present("confidence"))],
                "top_predictions": [("genre", _present("top_predictions"))],
                "guidance": [("genre", _present("guidance"))],
            }
        ),
        ("genres", "confidence", "top_predictions", "guidance"),
        file="genre.json",
    )
    payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": paths.song_name,
        "field_sources": field_sources,
        "genres": artifact.get("genres"),
        "confidence": artifact.get("confidence"),
        "top_predictions": artifact.get("top_predictions"),
        "guidance": artifact.get("guidance"),
    }
    write_json(paths.genre_output_path, payload)
    return str(paths.genre_output_path)


def build_ui_data(paths: SongPaths) -> dict[str, str]:
    beats_payload = read_json(paths.artifact("essentia", "beats.json"))
    harmonic_payload = read_json(paths.artifact("layer_a_harmonic.json"))
    sections_payload = read_json(paths.artifact("section_segmentation", "sections.json"))

    # v1.1 item 3.2 (B5) — validate the join key up front. The top-level section
    # list must be joinable to the segmentation list on section_id, never on
    # array position.
    raw_sections = list(sections_payload.get("sections", []))
    section_ids = [section.get("section_id") for section in raw_sections]
    if any(not section_id for section_id in section_ids):
        raise ValueError("section_segmentation/sections.json has a section without a section_id; cannot build a joinable UI section list")
    if len(set(section_ids)) != len(section_ids):
        raise ValueError(f"section_segmentation/sections.json has duplicate section_id values: {section_ids}")

    chord_events = harmonic_payload.get("chords", [])
    beat_points = beats_payload.get("beats", [])
    beat_rows = [
        {
            "time": round_schema_float(float(beat["time"])),
            "beat": int(beat["beat_in_bar"]),
            "bar": int(beat["bar"]),
            "chord": _resolve_chord_for_time(float(beat["time"]), chord_events),
            "type": str(beat["type"]),
            "downbeat_confidence": beat.get("confidence"),
        }
        for beat in beat_points
    ]

    song_key = _song_key(harmonic_payload.get("global_key"))

    occurrence_counts: dict[str, int] = {}
    section_rows = []
    for section in raw_sections:
        function = section.get("function")
        if function:
            occurrence_counts[function] = occurrence_counts.get(function, 0) + 1
        start = float(section["start"])
        end = float(section["end"])
        section_rows.append(
            {
                "section_id": section["section_id"],
                "start": round_schema_float(start),
                "end": round_schema_float(end),
                "label": _format_section_label(section),
                "description": _section_description(section, occurrence_counts.get(function, 0)),
                # v3.1 item 3 — the allin1 section-function fields are now on the
                # top-level row. A consumer reads section names from here alone
                # and never opens artifacts/section_segmentation/sections.json.
                # The row is built directly from the segmentation list (joined on
                # section_id, never array position), so there is no second list
                # to misalign.
                "function": function,
                "function_confidence": section.get("function_confidence"),
                "function_status": section.get("function_status", "unknown"),
                "same_label_as": section.get("same_label_as"),
                "confidence": section.get("confidence"),
                "key": song_key,
                "chord_progression": _section_chord_progression(start, end, chord_events),
            }
        )

    # v3.1 item 2 — the attribution convention. Each top-level file carries a
    # `field_sources` header: the default producer per field, declared once. A
    # row overrides it with its own `source` only where it departs from the
    # default (no beats.json row does — a repeated per-row map would be pure
    # token cost against the budget the mcp/ server exists to protect).
    #
    # `downbeat_confidence` (renamed from the ambiguous `confidence`) measures
    # allin1's downbeat-phase strength (0.226 F1), not essentia's trusted beat
    # time — the name now says which producer's number it is.
    beats_field_sources = validate_field_sources(
        {
            "time": "essentia",
            "beat": "essentia",
            "bar": "essentia",
            "chord": "harmonic",
            "type": "essentia",
            "downbeat_confidence": "allin1",
        },
        beat_rows[0].keys() if beat_rows else (),
        file="beats.json",
    )
    sections_field_sources = validate_field_sources(
        {
            "section_id": "allin1",
            "start": "allin1",
            "end": "allin1",
            "label": "human",
            "description": "human",
            "function": "allin1",
            "function_confidence": "allin1",
            "function_status": "allin1",
            "same_label_as": "allin1",
            "confidence": "allin1",
            "key": "harmonic",
            "chord_progression": "harmonic",
        },
        section_rows[0].keys() if section_rows else (),
        file="sections.json",
    )
    beats_output = {"field_sources": beats_field_sources, "beats": beat_rows}
    sections_output = {"field_sources": sections_field_sources, "sections": section_rows}

    beats_output_path = paths.beats_output_path
    sections_output_path = paths.sections_output_path
    write_json(beats_output_path, beats_output)
    write_json(sections_output_path, sections_output)

    # v3.1 item 5 — publish a top-level fused view of genre. The artifact under
    # artifacts/ is untouched.
    genre_output = _publish_genre(paths)

    return {
        "beats": str(beats_output_path),
        "sections": str(sections_output_path),
        "genre": genre_output,
    }
