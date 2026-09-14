"""Generate the committed MCP regression fixtures.

Deterministic and idempotent: running this produces byte-identical files every
time (no randomness, no timestamps, stable key order). Re-run it whenever the
top-level file shapes change, and commit the result.

    python mcp/tests/fixtures/build_fixtures.py

Fixtures carry the top-level file set ONLY — never `artifacts/` or `reference/`,
because a fixture containing those would hide an exposure violation instead of
exposing it. They describe a deliberately short 24 s song so the dense files
stay small.

v3.6 item 9 rebuilt every fixture to the item-8 top-level schema (see
docs/reference/artifacts.md): `beats.json` drops `chord`; `sections.json` drops
`label`/`description`/`chord_progression`; `hints.json` is a flat `hints[]`
(no `sections[]` wrapper, every row human by construction); `genre.json` drops
`top_predictions`/`guidance`; `drum_events.json` collapses per-event
`confidence` to one file-level `confidence`/`confidence_reason` pair;
`loudness.json` flattens `interval_ms`/`source_order` out of a `metadata`
wrapper and drops `sources[]`; `song_event_timeline.json` drops
`section_name`/`summary`/`evidence_summary`/`generated_from`.
`arrangement_state.json` is now a required top-level file (no more pre-v3.2
degraded/absent path) — every fixture carries it.

    McpFull - Fixture        fully populated baseline (the primary target)
    McpDegenerate - Fixture  honest-uncertainty path: function_status "unknown"
                             on every section, every beat confidence null
    McpPartial - Fixture     a required top-level file (sections.json) absent
                             — every other required file is present, per
                             loaders.REQUIRED_TOP_LEVEL_FILES
"""

from __future__ import annotations

import json
import math
from pathlib import Path

FIXTURE_ROOT = Path(__file__).resolve().parent / "analysis"

DURATION_S = 24.0
BPM = 120.0
BEAT_S = 60.0 / BPM  # 0.5 s
BEATS_PER_BAR = 4


def _write(song: str, filename: str, payload: object) -> None:
    song_dir = FIXTURE_ROOT / song
    song_dir.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    (song_dir / filename).write_text(text, encoding="utf-8")


def _round(value: float, places: int = 3) -> float:
    return round(value + 0.0, places)


BEATS_FIELD_SOURCES = {
    "time": "essentia",
    "beat": "essentia",
    "bar": "essentia",
    "type": "essentia",
    "downbeat_confidence": "allin1",
}

SECTIONS_FIELD_SOURCES = {
    "section_id": "allin1",
    "start": "allin1",
    "end": "allin1",
    "confidence": "allin1",
    "key": "harmonic",
    "function": "allin1",
    "function_confidence": "allin1",
    "function_status": "allin1",
    "same_label_as": "allin1",
}


def beats(*, all_confidence_null: bool) -> dict:
    rows: list[dict] = []
    n = int(DURATION_S / BEAT_S)  # 48
    for i in range(n):
        beat_in_bar = i % BEATS_PER_BAR
        is_downbeat = beat_in_bar == 0
        if all_confidence_null or not is_downbeat:
            confidence = None
        else:
            # Stable pseudo-value derived from position, not randomness.
            confidence = _round(0.3 + 0.05 * ((i // BEATS_PER_BAR) % 5), 6)
        rows.append(
            {
                "time": _round(i * BEAT_S, 3),
                "beat": beat_in_bar + 1,
                "bar": i // BEATS_PER_BAR + 1,
                "type": "downbeat" if is_downbeat else "beat",
                "downbeat_confidence": confidence,
            }
        )
    return {"field_sources": BEATS_FIELD_SOURCES, "beats": rows}


def sections(*, degenerate: bool) -> dict:
    spec = [
        ("section-001", 0.0, 8.0, "intro", None),
        ("section-002", 8.0, 16.0, "verse", None),
        ("section-003", 16.0, 24.0, "chorus", None),
    ]
    rows: list[dict] = []
    for idx, (sid, start, end, function, same_label_as) in enumerate(spec):
        if degenerate:
            function_value = None
            function_confidence = None
            function_status = "unknown"
            confidence = None
        else:
            function_value = function
            function_confidence = _round(0.6 + 0.1 * idx, 3)
            function_status = "known"
            confidence = _round(0.55 + 0.1 * idx, 3)
        rows.append(
            {
                "section_id": sid,
                "start": start,
                "end": end,
                "function": function_value,
                "function_confidence": function_confidence,
                "function_status": function_status,
                "same_label_as": same_label_as,
                "confidence": confidence,
                "key": "C major",
            }
        )
    return {"field_sources": SECTIONS_FIELD_SOURCES, "sections": rows}


def _phase_event(gesture_id: str, phase: str, start: float, end: float,
                 intensity: float, section_id: str) -> dict:
    return {
        "type": phase,
        "gesture_id": gesture_id,
        "start_time": _round(start, 3),
        "end_time": _round(end, 3),
        "confidence": 0.8,
        "intensity": _round(intensity, 3),
        "section_id": section_id,
    }


TIMELINE_FIELD_SOURCES = {
    "type": "gestures",
    "start_time": "gestures",
    "end_time": "gestures",
    "confidence": "gestures",
    "intensity": "gestures",
    "gesture_id": "gestures",
    "section_id": "allin1",
}


def timeline(song_name: str, *, degenerate: bool) -> dict:
    if degenerate:
        events: list[dict] = []
    else:
        # One complete gesture: approach -> build -> tension -> impact -> release.
        g = "gesture-001"
        events = [
            _phase_event(g, "approach", 9.0, 10.0, 0.30, "section-002"),
            _phase_event(g, "build", 10.0, 12.0, 0.55, "section-002"),
            _phase_event(g, "tension", 12.0, 13.5, 0.75, "section-002"),
            _phase_event(g, "impact", 13.5, 14.0, 0.95, "section-002"),
            _phase_event(g, "release", 14.0, 16.0, 0.40, "section-002"),
            {
                "type": "verse → chorus",
                "start_time": 16.0,
                "end_time": 16.0,
                "confidence": 0.7,
                "section_id": "section-003",
            },
        ]
    return {
        "schema_version": "3.6",
        "song_name": song_name,
        "field_sources": TIMELINE_FIELD_SOURCES,
        "events": events,
    }


HINTS_FIELD_SOURCES = {
    "section_id": "human",
    "title": "human",
    "text": "human",
    "start_time": "human",
    "end_time": "human",
    "lighting_hint": "human",
}


def hints(song_name: str, *, degenerate: bool) -> dict:
    if degenerate:
        rows: list[dict] = []
    else:
        rows = [
            {
                "section_id": "section-002",
                "title": "Breath",
                "text": "Vocal - no intense section",
                "start_time": 8.5,
                "end_time": 15.5,
                "lighting_hint": "soft motion of moving heads. parcans slow violet waves.",
            }
        ]
    return {
        "schema_version": "3.6",
        "song_name": song_name,
        "field_sources": HINTS_FIELD_SOURCES,
        "hints": rows,
    }


def info(song_name: str) -> dict:
    # No absolute host paths — a delivery-surface file must not embed them.
    return {
        "schema_version": "3.0",
        "song_name": song_name,
        "field_sources": {"bpm": "essentia", "duration": "essentia"},
        "bpm": BPM,
        "duration": DURATION_S,
    }


GENRE_FIELD_SOURCES = {
    "genres": "genre",
    "confidence": "genre",
}

DRUM_FIELD_SOURCES = {"time": "omnizart", "event_type": "omnizart"}

LOUDNESS_FIELD_SOURCES = {
    "time": "essentia",
    "values": "essentia",
    "normalized_values": "essentia",
}


def genre(song_name: str, *, degenerate: bool) -> dict:
    if degenerate:
        return {
            "schema_version": "3.6",
            "song_name": song_name,
            "field_sources": GENRE_FIELD_SOURCES,
            "genres": ["unknown"],
            "confidence": 0.11,
        }
    return {
        "schema_version": "3.6",
        "song_name": song_name,
        "field_sources": GENRE_FIELD_SOURCES,
        "genres": ["house", "dance"],
        "confidence": 0.62,
    }


ARRANGEMENT_STATE_FIELD_SOURCES = {
    "start_s": "arrangement_state",
    "end_s": "arrangement_state",
    "playing": "arrangement_state",
    "entered": "arrangement_state",
    "left": "arrangement_state",
    "margin_db": "arrangement_state",
    "confidence": "arrangement_state",
}

ARRANGEMENT_STEMS = ["bass", "drums", "harmonic", "vocals"]


def _arr_confidence(margin_db: float) -> float:
    # Matches the publisher: round(1 - exp(-margin_db / 6.0), 3).
    return round(1 - math.exp(-margin_db / 6.0), 3)


def arrangement_state(song_name: str) -> dict:
    # Leading block: no measured margin -> margin_db / confidence stay null.
    blocks = [
        {
            "start_s": 0.0,
            "end_s": 8.0,
            "playing": list(ARRANGEMENT_STEMS),
            "entered": [],
            "left": [],
            "margin_db": None,
            "confidence": None,
        },
        {
            "start_s": 8.0,
            "end_s": 16.0,
            "playing": ["bass", "drums", "harmonic"],
            "entered": [],
            "left": ["vocals"],
            "margin_db": 6.0,
            "confidence": _arr_confidence(6.0),
        },
        {
            "start_s": 16.0,
            "end_s": 24.0,
            "playing": list(ARRANGEMENT_STEMS),
            "entered": ["vocals"],
            "left": [],
            "margin_db": 12.5,
            "confidence": _arr_confidence(12.5),
        },
    ]
    return {
        "schema_version": "3.6",
        "song_name": song_name,
        "field_sources": ARRANGEMENT_STATE_FIELD_SOURCES,
        "stems": list(ARRANGEMENT_STEMS),
        "blocks": blocks,
        "vocals_phrase": None,
        "vocals_sibilance_song_mean": None,
    }


def loudness(song_name: str) -> dict:
    interval_ms = 20
    n = int(DURATION_S * 1000 / interval_ms)  # 1200 frames at the 20 ms floor
    frames = []
    for i in range(n):
        t = _round(i * interval_ms / 1000.0 + interval_ms / 2000.0, 4)
        base = 0.2 + 0.5 * (t / DURATION_S)
        bump = 0.3 if 13.0 <= t <= 14.0 else 0.0
        mix = _round(base + bump, 6)
        frames.append(
            {
                "time": t,
                "values": [mix, _round(mix * 0.6, 6), _round(mix * 0.8, 6),
                           _round(mix * 0.5, 6), _round(mix * 0.3, 6)],
                "normalized_values": [_round(min(1.0, mix * 1.1), 6)] * 5,
            }
        )
    return {
        "schema_version": "3.6",
        "song_name": song_name,
        "field_sources": LOUDNESS_FIELD_SOURCES,
        "interval_ms": interval_ms,
        "source_order": ["mix", "bass", "drums", "harmonic", "vocals"],
        "frames": frames,
    }


def drum_events(song_name: str) -> dict:
    events = []
    step = 0.5
    n = int(DURATION_S / step)
    kick = snare = 0
    for i in range(n):
        t = _round(i * step, 3)
        events.append({"time": t, "event_type": "kick"})
        kick += 1
        if i % 2 == 1:
            events.append({"time": t, "event_type": "snare"})
            snare += 1
    return {
        "schema_version": "3.6",
        "song_name": song_name,
        "field_sources": DRUM_FIELD_SOURCES,
        "summary": {
            "event_count": len(events),
            "kick_count": kick,
            "snare_count": snare,
            "hat_count": 0,
            "unresolved_count": 0,
        },
        "supported_event_types": ["kick", "snare", "hat", "crash", "unresolved"],
        "confidence": None,
        "confidence_reason": (
            "omnizart emits no per-hit confidence signal — every event in the "
            "fixture (as in the full corpus) carries null confidence; stated "
            "once here rather than repeated on every row"
        ),
        "events": events,
    }


def _write_common(song: str, *, degenerate: bool) -> None:
    _write(song, "info.json", info(song))
    _write(song, "beats.json", beats(all_confidence_null=degenerate))
    _write(song, "sections.json", sections(degenerate=degenerate))
    _write(song, "song_event_timeline.json", timeline(song, degenerate=degenerate))
    _write(song, "hints.json", hints(song, degenerate=degenerate))
    _write(song, "genre.json", genre(song, degenerate=degenerate))
    _write(song, "loudness.json", loudness(song))
    _write(song, "drum_events.json", drum_events(song))
    _write(song, "arrangement_state.json", arrangement_state(song))


def build_full() -> None:
    _write_common("McpFull - Fixture", degenerate=False)


def build_degenerate() -> None:
    _write_common("McpDegenerate - Fixture", degenerate=True)


def build_partial() -> None:
    # Required top-level file `sections.json` is deliberately absent; every
    # other required file (loaders.REQUIRED_TOP_LEVEL_FILES) is present.
    song = "McpPartial - Fixture"
    _write(song, "info.json", info(song))
    _write(song, "beats.json", beats(all_confidence_null=False))
    _write(song, "song_event_timeline.json", timeline(song, degenerate=False))
    _write(song, "hints.json", hints(song, degenerate=False))
    _write(song, "genre.json", genre(song, degenerate=False))
    _write(song, "loudness.json", loudness(song))
    _write(song, "drum_events.json", drum_events(song))
    _write(song, "arrangement_state.json", arrangement_state(song))


def main() -> None:
    build_full()
    build_degenerate()
    build_partial()
    print(f"fixtures written under {FIXTURE_ROOT}")


if __name__ == "__main__":
    main()
