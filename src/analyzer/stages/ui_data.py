from __future__ import annotations

import math
import re

from analyzer.exceptions import DependencyError
from analyzer.io import read_json, write_json
from analyzer.models import SCHEMA_VERSION, round_schema_float, validate_field_sources
from analyzer.paths import SongPaths
from analyzer.section_vocabulary import normalize_human_label

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

    # v3.6 item 8 — `top_predictions` (unread) and `guidance` (one identical
    # text across all 23 songs; moves into mcp/'s tool description, item 9)
    # are dropped from the top-level view. Both stay in the artifact.
    field_sources = validate_field_sources(
        _fuse(
            {
                "genres": [("genre", _present("genres"))],
                "confidence": [("genre", _present("confidence"))],
            }
        ),
        ("genres", "confidence"),
        file="genre.json",
    )
    payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": paths.song_name,
        "field_sources": field_sources,
        "genres": artifact.get("genres"),
        "confidence": artifact.get("confidence"),
    }
    write_json(paths.genre_output_path, payload)
    return str(paths.genre_output_path)


# v3.6 item 8 — every one of the 32,213 corpus drum events carries `null`
# confidence (CLAUDE.md: omnizart emits no per-hit confidence signal).
# Repeating that `null` on every row is pure token cost with no information;
# it is now stated once at file level, with the reason a reader would
# otherwise have to rediscover per event.
DRUM_EVENTS_CONFIDENCE_REASON = (
    "omnizart emits no per-hit confidence signal — every event in the corpus "
    "(32,213 events across 23 songs) carries null confidence; stated once "
    "here rather than repeated on every row"
)


def _publish_drum_events(paths: SongPaths) -> str:
    artifact = read_json(paths.artifact("symbolic_transcription", "drum_events.json"))
    events = [
        {
            "time": round_schema_float(float(event["time"]), 3),
            "event_type": str(event["event_type"]),
        }
        for event in artifact.get("events", [])
    ]
    row_keys = events[0].keys() if events else ("time", "event_type")
    field_sources = validate_field_sources(
        _fuse(
            {
                "time": [("omnizart", True)],
                "event_type": [("omnizart", True)],
            }
        ),
        row_keys,
        file="drum_events.json",
        exempt=("confidence", "confidence_reason"),
    )
    payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": paths.song_name,
        "field_sources": field_sources,
        # File-level aggregate blocks (counts, the supported-type list) are
        # provenance-exempt like `schema_version` — they describe the file, not a
        # fused per-row value. Every row is omnizart's (plan D21).
        "summary": artifact.get("summary"),
        "supported_event_types": artifact.get("supported_event_types"),
        # File-level, honest `null` — see DRUM_EVENTS_CONFIDENCE_REASON. Never
        # per-event: no silent fallback, no confident-looking repetition.
        "confidence": None,
        "confidence_reason": DRUM_EVENTS_CONFIDENCE_REASON,
        "events": events,
    }
    write_json(paths.drum_events_output_path, payload)
    return str(paths.drum_events_output_path)


def _decimate_loudness_pairs(frames: list[dict]) -> list[dict]:
    """10 ms → 20 ms by AVERAGING consecutive pairs, not dropping every other
    frame: a dropped-frame series loses transient peaks, which is exactly what a
    drop impact is. An unpaired trailing frame (odd source count) is dropped so
    every published interval is a clean 20 ms — at most 10 ms is lost at the very
    end of the song, never a mid-song transient."""
    out: list[dict] = []
    for i in range(0, len(frames) - 1, 2):
        pair = frames[i : i + 2]
        times = [float(f["time"]) for f in pair]
        values = [f["values"] for f in pair]
        normalized = [f["normalized_values"] for f in pair]
        out.append(
            {
                "time": round(sum(times) / len(times), 4),
                "values": [round(sum(col) / len(col), 6) for col in zip(*values)],
                "normalized_values": [round(sum(col) / len(col), 6) for col in zip(*normalized)],
            }
        )
    return out


def _publish_loudness(paths: SongPaths) -> str:
    # v3.6 item 8 — `sources[]` (stem identity list) and
    # `metadata.sample_rate/duration/total_frames/normalization_scope` are
    # unread; dropped from the top-level view. All stay in the artifact
    # (`artifacts/essentia/rms_loudness.json`), which the debugger UI reads
    # directly for stem identity and full metadata.
    artifact = read_json(paths.artifact("essentia", "rms_loudness.json"))
    frames = _decimate_loudness_pairs(artifact.get("frames", []))
    meta = artifact.get("metadata", {})
    field_sources = validate_field_sources(
        _fuse(
            {
                "time": [("essentia", True)],
                "values": [("essentia", True)],
                "normalized_values": [("essentia", True)],
            }
        ),
        frames[0].keys() if frames else ("time", "values", "normalized_values"),
        file="loudness.json",
    )
    payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": paths.song_name,
        "field_sources": field_sources,
        "interval_ms": 20,
        "source_order": meta.get("source_order"),
        "frames": frames,
    }
    write_json(paths.loudness_output_path, payload)
    return str(paths.loudness_output_path)


# --- the sibilance discriminator (v3.5 item 4, promoted 2026-09-13) --------
#
# `fft_bands.vocals.json` band ids, in order: sub, bass, low_mid, mid,
# upper_mid, presence (2.5-6 kHz), brilliance (6-16 kHz). The published split
# doesn't land exactly on the 4-10 kHz consonant band, so presence+brilliance
# is the documented proxy — no new FFT is taken off vocals.wav.
SIBILANCE_BAND_IDS = ("presence", "brilliance")
#: Score at zero transient strength — pure brightness, no burst.
SIBILANCE_BASELINE_WEIGHT = 0.4
#: Additional score a burst-like onset unlocks. A sung consonant is bright AND
#: transient; a bright sustained pad or a cymbal leak is only one of the two.
SIBILANCE_BURST_WEIGHT = 0.6


def _sibilance_curve(paths: SongPaths) -> tuple[list[float], list[float]]:
    """Per-frame sibilance over the vocal stem, on `fft_bands.vocals.json`'s own
    50 ms grid. Ported verbatim from `experiments/vocal_voiceness/features.py`'s
    `compute_sibilance` — `src/` never imports from `experiments/`.

    Measured (`experiments/vocal_voiceness/README.md`): of the experiment's
    three cues this is the only one worth keeping — separability against ground
    truth on `_test_song` / `ayuni` / `Queen of Kings` is AUC 0.990 / 0.959 /
    0.813, against vibrato's 0.700 / 0.815 / 0.656 and portamento's 0.718 /
    0.800 / 0.650. Vibrato and portamento are deliberately NOT promoted; the
    experiment's own noisy-OR diluted this cue with those two.

    **Known limit, carried across the promotion**: sibilance has a per-song
    noise floor — it reads 0.129 on the digitally near-silent stem in
    `What a Feeling - Courtney Storm` (level 0.0002). It discriminates *within*
    a song against that song's own mean; it cannot gate presence on its own,
    which is why it is published as per-phrase evidence next to a level-bearing
    detector rather than as a standalone vocal call.
    """
    doc = read_json(paths.artifact("essentia", "fft_bands.vocals.json"))
    band_ids = [band["id"] for band in doc["bands"]]
    idxs = [band_ids.index(b) for b in SIBILANCE_BAND_IDS if b in band_ids]

    times: list[float] = []
    values: list[float] = []
    for frame in doc["frames"]:
        levels = frame["levels"]
        spectral = min(max(sum(levels[i] for i in idxs) / len(idxs), 0.0), 1.0) if idxs else 0.0
        transient = min(max(float(frame.get("transient_strength", 0.0)), 0.0), 1.0)
        score = spectral * (SIBILANCE_BASELINE_WEIGHT + SIBILANCE_BURST_WEIGHT * transient)
        times.append(float(frame["time"]))
        values.append(min(max(score, 0.0), 1.0))
    return times, values


def _mean_in_span(times: list[float], values: list[float], start: float, end: float) -> float | None:
    """Mean of `values` over [start, end], or `None` when the span covers no
    frame — an honest gap, never a zero standing in for "no evidence"."""
    inside = [v for t, v in zip(times, values) if start <= t <= end]
    return round(sum(inside) / len(inside), 4) if inside else None


def _whisperx_vocal_phrase(paths: SongPaths) -> list[dict]:
    """`vocals_phrase` (v3.5 item 7 promotion; v3.6 item 2 promoted the
    `whisperx_vad` detector itself out of `experiments/` into its own
    pipeline service — the `whisperx` Compose service, `whisperx_vad/`).

    Reads `artifacts/whisperx-vad/whisperx_vad.json`, written by
    `docker compose run --rm whisperx --song <path>` before `./analyze` runs
    (whisperX pins torch~=2.8.0, incompatible with the `app` image's pinned
    torch==2.1.2 / `natten==0.15.1+torch210cu121`, so it cannot run inside
    `./analyze` itself). No silent fallback: when the artifact is absent this
    raises rather than returning a guess or an honest-looking `None` that a
    caller could mistake for "ran, found nothing" — a song must not silently
    publish `arrangement_state.json` without this signal.

    Every span's `confidence` is hardcoded `1.0`, not whisperX's own varying
    per-span value (0.56-0.98 in practice) — the operator's explicit call: "when
    'phrase' is detected the chances that it happens is true". This collapses
    the detector's own graded confidence in favour of asserting each detected
    phrase as certain; the graded per-frame curve stays in
    `artifacts/whisperx-vad/whisperx_vad.json` for anyone who wants it.
    """
    artifact_path = paths.artifact("whisperx-vad", "whisperx_vad.json")
    if not artifact_path.exists():
        raise DependencyError(
            f"missing {artifact_path} — run the whisperx service before ./analyze: "
            f"docker compose run --rm whisperx --song {paths.song_path}"
        )
    proposal = read_json(artifact_path)
    times, values = _sibilance_curve(paths)
    return [
        {
            "start_s": span["start"],
            "end_s": span["end"],
            "confidence": 1.0,
            # The stem-bleed discriminator, read against this song's own mean
            # (published alongside as `vocals_sibilance_song_mean`) — a phrase
            # far below the song mean is whisperX firing on instrument bleed,
            # the failure mode it has on plucked/rhythmic leaks.
            "sibilance": _mean_in_span(times, values, span["start"], span["end"]),
        }
        for span in proposal.get("vocal_phrase", [])
    ]


def publish_arrangement_state(paths: SongPaths) -> str:
    """v3.2 item 2 — publish the top-level fused view of
    `artifacts/arrangement_state.json` (phase-3 `detect-arrangement-state`, which
    reads only the published `loudness.json`).

    A pure fuse-and-strip step: every row field is `arrangement_state`'s today,
    but the selection goes through `_fuse` so a later CLAP `feel` field slots in
    as a second candidate without touching the caller. `confidence` is a monotone
    report of the dB headroom of the smallest stem flip at the block boundary
    (`1 - exp(-margin_db / 6)`), not a tuned gate — `margin_db` fails as a
    precision filter (experiment `margin-sweep`), so it is reported, never gated.
    The leading span before the first stem change has no flip: `margin_db` and
    `confidence` are both `null`, never a filled default.

    `vocals_phrase` (v3.5 item 7 promotion, see `_whisperx_vocal_phrase`) is a
    second, independent signal about the vocals stem — the `whisperx_vad`
    detector's phrase spans, run as its own pipeline service (v3.6 item 2) —
    published alongside `blocks` rather than folded into them, so a wrong call
    on one never masks the other.
    """
    artifact = read_json(paths.artifact("arrangement_state.json"))
    raw_blocks = artifact.get("blocks", [])

    def _confidence(margin_db: object) -> float | None:
        if isinstance(margin_db, (int, float)) and not isinstance(margin_db, bool):
            return round(1 - math.exp(-float(margin_db) / 6.0), 3)
        return None

    blocks = [
        {
            "start_s": block["start_s"],
            "end_s": block["end_s"],
            "playing": block["playing"],
            "entered": block["entered"],
            "left": block["left"],
            "margin_db": block["margin_db"],
            "confidence": _confidence(block["margin_db"]),
        }
        for block in raw_blocks
    ]

    vocals_phrase = _whisperx_vocal_phrase(paths)
    _, sibilance_values = _sibilance_curve(paths)
    sibilance_song_mean = (
        round(sum(sibilance_values) / len(sibilance_values), 4) if sibilance_values else None
    )

    row_keys = ("start_s", "end_s", "playing", "entered", "left", "margin_db", "confidence")
    field_sources = validate_field_sources(
        _fuse(
            {
                **{key: [("arrangement_state", True)] for key in row_keys},
                # Never `None` — `_whisperx_vocal_phrase` raises rather than
                # returning one (no silent fallback).
                "vocals_phrase": [("whisperx_vad", True)],
                # A `vocals_phrase` row fuses two producers: its span is
                # whisperX's, its `sibilance` is the promoted item-4 cue's. The
                # dotted key is the per-row override the flat header cannot
                # otherwise express.
                "vocals_phrase.sibilance": [
                    ("vocal_sibilance", sibilance_song_mean is not None)
                ],
                "vocals_sibilance_song_mean": [
                    ("vocal_sibilance", sibilance_song_mean is not None)
                ],
            }
        ),
        (*row_keys, "vocals_phrase", "vocals_sibilance_song_mean"),
        file="arrangement_state.json",
    )
    payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": paths.song_name,
        "field_sources": field_sources,
        # File-level aggregate (the stem vocabulary), provenance-exempt like
        # `schema_version` — it describes the file, not a fused per-row value.
        "stems": artifact.get("stems"),
        "blocks": blocks,
        "vocals_phrase": vocals_phrase,
        # The reference level every `vocals_phrase.sibilance` is read against.
        # Sibilance has a per-song noise floor, so the absolute value carries
        # far less than the distance from this mean.
        "vocals_sibilance_song_mean": sibilance_song_mean,
    }
    write_json(paths.arrangement_state_output_path, payload)
    return str(paths.arrangement_state_output_path)


def _load_section_contest(paths: SongPaths) -> dict[str, dict]:
    """`{section_id: contest_row}` for the rows the phase-3 contest flagged, or
    `{}` when `artifacts/section_function_contest.json` has not been written yet
    (a fresh run publishes `sections.json` first, then the contest stage
    re-fuses it — see `apply_section_function_contest`)."""
    artifact_path = paths.artifact("section_function_contest.json")
    if not artifact_path.exists():
        return {}
    doc = read_json(artifact_path)
    return {
        row["section_id"]: row
        for row in doc.get("sections", [])
        if row.get("contested")
    }


def apply_section_function_contest(paths: SongPaths) -> str:
    """v3.4 item 3 — re-fuse the published `sections.json` after the phase-3
    `contest-section-function` stage has written
    `artifacts/section_function_contest.json`.

    A flagged row gains two fields: `function_status: "contested"` (a NEW third
    enum value beside `known` / `unknown`) and `contested_by: "energy"`.
    `function` and `function_confidence` are untouched — the label is kept, only
    flagged (refinement D5; the phase-3 stage never mutates `sections.json`, the
    publisher fuses). A row the contest does not flag is byte-identical to
    `build_ui_data`'s output. The `function_status` producer goes through
    `_fuse`: `allin1`'s where the row is `known` / `unknown`,
    `section_function`'s where it is `contested`, so the header records which
    producer had the final say.
    """
    contested = _load_section_contest(paths)
    payload = read_json(paths.sections_output_path)
    rows = payload["sections"]
    any_contested = False
    for row in rows:
        if row["section_id"] in contested:
            row["function_status"] = "contested"
            row["contested_by"] = "energy"
            any_contested = True
        else:
            row.pop("contested_by", None)

    header = dict(payload.get("field_sources", {}))
    if any_contested:
        header.update(
            _fuse(
                {
                    "function_status": [("section_function", True), ("allin1", True)],
                    "contested_by": [("section_function", True)],
                }
            )
        )
    else:
        header.pop("contested_by", None)

    emitted_keys: set[str] = set()
    for row in rows:
        emitted_keys.update(row.keys())
    payload["field_sources"] = validate_field_sources(
        header, emitted_keys, file="sections.json"
    )
    write_json(paths.sections_output_path, payload)
    return str(paths.sections_output_path)


def _build_reference_override_rows(
    reference_rows: list[dict],
    raw_sections: list[dict],
    song_key: str | None,
    chord_events: list[dict],
    occurrence_counts: dict[str, int],
    confidence: float,
) -> tuple[list[dict], list[dict]]:
    """Shared whole-song-override builder for reference/human/segments.json
    and reference/moises/segments.json: same boundary/label shape, only the
    fixed `confidence` and the input rows differ per tier (see
    docs/reference/analysis.segments.md for the precedence and rationale).

    Returns `(section_rows, display_rows)` — `section_rows` is the trimmed
    top-level shape (v3.6 item 8: no `label` / `description` /
    `chord_progression`, which fold confidence into a display string or are
    unread); `display_rows` carries those three fields keyed by `section_id`
    for `artifacts/section_segmentation/sections_display.json`, which the
    debugger UI reads instead."""
    rows_sorted = sorted(reference_rows, key=lambda row: float(row["start"]))
    section_rows = []
    display_rows = []
    for index, reference_row in enumerate(rows_sorted):
        start = float(reference_row["start"])
        end = float(reference_row["end"])
        function = normalize_human_label(str(reference_row["label"]))
        section_id = f"section-{index + 1:03d}"

        # Inherit function_confidence/function_status/same_label_as from
        # whichever allin1 section this span overlaps most — never invented.
        # No overlap (shouldn't normally happen; allin1 covers the whole
        # song) is an honest null/"unknown", not a guess.
        best_match: dict | None = None
        best_overlap = 0.0
        for candidate in raw_sections:
            overlap = min(end, float(candidate["end"])) - max(start, float(candidate["start"]))
            if overlap > best_overlap:
                best_overlap = overlap
                best_match = candidate
        function_confidence = best_match.get("function_confidence") if best_match else None
        function_status = best_match.get("function_status", "unknown") if best_match else "unknown"
        same_label_as = best_match.get("same_label_as") if best_match else None

        if function:
            occurrence_counts[function] = occurrence_counts.get(function, 0) + 1
        label_source = {
            "section_id": section_id,
            "function": function,
            "function_confidence": function_confidence,
            "function_status": function_status,
        }
        description_source = {**label_source, "start": start, "end": end, "same_label_as": same_label_as}
        section_rows.append(
            {
                "section_id": section_id,
                "start": round_schema_float(start),
                "end": round_schema_float(end),
                "function": function,
                "function_confidence": function_confidence,
                "function_status": function_status,
                "same_label_as": same_label_as,
                "confidence": confidence,
                "key": song_key,
            }
        )
        display_rows.append(
            {
                "section_id": section_id,
                "label": _format_section_label(label_source),
                "description": _section_description(description_source, occurrence_counts.get(function, 0)),
                "chord_progression": _section_chord_progression(start, end, chord_events),
            }
        )
    return section_rows, display_rows


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
    # v3.6 item 8 — `chord` dropped: unread, and chord labels are "informative,
    # not settled" (CLAUDE.md). The harmonic stage's own chord events are the
    # source of truth (`artifacts/layer_a_harmonic.json`, still read above).
    beat_rows = [
        {
            "time": round_schema_float(float(beat["time"])),
            "beat": int(beat["beat_in_bar"]),
            "bar": int(beat["bar"]),
            "type": str(beat["type"]),
            "downbeat_confidence": beat.get("confidence"),
        }
        for beat in beat_points
    ]

    song_key = _song_key(harmonic_payload.get("global_key"))

    # reference/human/segments.json and reference/moises/segments.json are
    # OPTIONAL, per-song reference overrides (same tier as human_hints.json):
    # each a flat [{start, end, label}] list. Precedence — documented in
    # docs/reference/analysis.segments.md — is whole-song, never per-boundary:
    # human wins outright if present, else moises if present, else our own
    # segmentation. See section_vocabulary.py for the label-vocabulary
    # normalization this also applies.
    human_segments_path = paths.reference("human", "segments.json")
    has_human_segments = human_segments_path.exists()
    moises_segments_path = paths.reference("moises", "segments.json")
    has_moises_segments = moises_segments_path.exists()

    occurrence_counts: dict[str, int] = {}
    section_rows = []
    display_rows = []
    if has_human_segments:
        # Fixed at 0.8, independent of allin1's own confidence (inherited
        # below only for the function_* fields) — human mistakes are
        # plausible, but human is still the best available truth.
        section_rows, display_rows = _build_reference_override_rows(
            read_json(human_segments_path), raw_sections, song_key, chord_events, occurrence_counts, confidence=0.8
        )
    elif has_moises_segments:
        # Fixed at 0.6 — moises/segments.json carries no confidence field of
        # its own (Moises.ai gives no per-row confidence for segments, unlike
        # its word-level lyrics/chords) — moises is also an inferred
        # discriminator, one tier below a human.
        section_rows, display_rows = _build_reference_override_rows(
            read_json(moises_segments_path), raw_sections, song_key, chord_events, occurrence_counts, confidence=0.6
        )
    else:
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
                }
            )
            # v3.6 item 8 — `label` / `description` / `chord_progression`
            # dropped from the top-level row (display string with confidence
            # folded in; restates function+ordinal; unread) and written
            # instead to artifacts/section_segmentation/sections_display.json
            # for the debugger UI, joined by section_id.
            display_rows.append(
                {
                    "section_id": section["section_id"],
                    "label": _format_section_label(section),
                    "description": _section_description(section, occurrence_counts.get(function, 0)),
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
            "type": "essentia",
            "downbeat_confidence": "allin1",
        },
        beat_rows[0].keys() if beat_rows else (),
        file="beats.json",
    )
    # A genuine per-song producer switch, not a per-row override: precedence
    # is human, then moises, then allin1 (docs/reference/analysis.segments.md).
    # When a reference file exists, EVERY row's boundaries/confidence came
    # from it, so the file-level default itself moves to that producer for
    # this song. function's own value is also that producer's then
    # (normalize_human_label of its label text — shared by human and moises);
    # only function_confidence / function_status / same_label_as stay
    # allin1's regardless (inherited by overlap, never invented); key stays
    # the harmonic stage's either way.
    sections_field_sources = validate_field_sources(
        _fuse(
            {
                "section_id": [("human", has_human_segments), ("moises", has_moises_segments), ("allin1", True)],
                "start": [("human", has_human_segments), ("moises", has_moises_segments), ("allin1", True)],
                "end": [("human", has_human_segments), ("moises", has_moises_segments), ("allin1", True)],
                "function": [("human", has_human_segments), ("moises", has_moises_segments), ("allin1", True)],
                "function_confidence": [("allin1", True)],
                "function_status": [("allin1", True)],
                "same_label_as": [("allin1", True)],
                "confidence": [("human", has_human_segments), ("moises", has_moises_segments), ("allin1", True)],
                "key": [("harmonic", True)],
            }
        ),
        section_rows[0].keys() if section_rows else (),
        file="sections.json",
    )
    beats_output = {"field_sources": beats_field_sources, "beats": beat_rows}
    sections_output = {"field_sources": sections_field_sources, "sections": section_rows}

    beats_output_path = paths.beats_output_path
    sections_output_path = paths.sections_output_path
    write_json(beats_output_path, beats_output)
    write_json(sections_output_path, sections_output)

    # v3.6 item 8 — the display text dropped from sections.json (label,
    # description, chord_progression) is written to its own artifact for the
    # debugger UI, joined by section_id. Not provenance-tracked with
    # `generated_from` per-field (it's a straight publish-time projection,
    # like the top-level files it replaces a field of), but the file itself
    # carries `generated_from` like every other artifact.
    sections_display_path = paths.artifact("section_segmentation", "sections_display.json")
    write_json(
        sections_display_path,
        {
            "schema_version": SCHEMA_VERSION,
            "song_name": paths.song_name,
            "generated_from": {
                "source_song_path": str(paths.song_path),
                "engine": "ui_data.build_ui_data (publish-time section display text)",
                "dependencies": {
                    "sections_file": str(paths.sections_output_path),
                    "harmonic_file": str(paths.artifact("layer_a_harmonic.json")),
                },
            },
            "sections": display_rows,
        },
    )

    # v3.1 items 5-7 — publish top-level fused views of genre, drum events and
    # loudness. The artifacts under artifacts/ are untouched.
    genre_output = _publish_genre(paths)
    drum_events_output = _publish_drum_events(paths)
    loudness_output = _publish_loudness(paths)

    return {
        "beats": str(beats_output_path),
        "sections": str(sections_output_path),
        "genre": genre_output,
        "drum_events": drum_events_output,
        "loudness": loudness_output,
    }
