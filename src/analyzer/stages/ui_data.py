from __future__ import annotations

import re

from analyzer.io import read_json, write_json
from analyzer.models import round_schema_float
from analyzer.paths import SongPaths

# Item 13 (docs/implementation-plan-v3.0.md) — thresholds for projecting a
# compact harmonic form into sections.json.
#
# Measured on the four gold songs (docs/contract-change-v3.0.md #13): exact
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
    trustworthy (constitution §2 — an honest `unknown` beats a confident wrong
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
    `None` when confidence is too low to state one honestly (constitution
    §2 — never an empty string or a placeholder). Gated by
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
            "confidence": beat.get("confidence"),
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
                "confidence": section.get("confidence"),
                "key": song_key,
                "chord_progression": _section_chord_progression(start, end, chord_events),
            }
        )

    beats_output_path = paths.beats_output_path
    sections_output_path = paths.sections_output_path
    write_json(beats_output_path, beat_rows)
    write_json(sections_output_path, section_rows)
    return {
        "beats": str(beats_output_path),
        "sections": str(sections_output_path),
    }
