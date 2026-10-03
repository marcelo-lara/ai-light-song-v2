"""Phase-4 stage `publish-light-changes` (v3.12 item 33): the texture and light-change facts
reach the delivery surface.

Reads `artifacts/light_changes/{light_changes,bar_features}.json` (item 32) and the PUBLISHED
`sections.json` / `song_event_timeline.json`; never audio, never `reference/`. Writes:

* `song_event_timeline.json` (rewritten): every prior `light_change` row is dropped and one
  row per point is appended, `{type: "light_change", role, start_time, end_time: start_time,
  confidence, section_id}`. `confidence` is `null` (the point's pooled score is uncalibrated;
  D5) and stays a separate field. `section_id` is the published section containing the point, `null` in a gap between sections.
  Idempotent; re-running `build-gestures` rewrites the file without these rows, so this stage
  must run after it (the full pipeline does).
* `bar_features.json` (new, required): `{schema_version, song_name, field_sources, bars[]}`,
  each bar `{bar, start, end, irregular, brightness, transient_density, kick_present,
  sweep_state, light_change_role}`. `transient_density` is the artifact's `transient_mean`
  (mean FFT transient strength over the bar). `light_change_role` is the role of the point in
  that bar (the bar containing the point's time), `null` when none (two points in one bar: the earlier one).

A missing or malformed input raises; there is no default. Deterministic.
"""
from __future__ import annotations

from analyzer.exceptions import AnalysisError
from analyzer.io import read_json, write_json
from analyzer.models import SCHEMA_VERSION, validate_field_sources
from analyzer.paths import SongPaths

BAR_COLUMNS = {"brightness": "brightness", "transient_density": "transient_mean"}


def _need(path):
    if not path.exists():
        raise AnalysisError(f"publish-light-changes input missing: {path}")
    return read_json(path)


def _section_id(time_s: float, sections: list[dict]) -> str | None:
    """Containing published section; `None` inside a gap between sections (reviewed segments
    can leave one, e.g. Armin 66.77-81.76) — no nearest-section guess."""
    for s in sections:
        if float(s["start"]) <= time_s < float(s["end"]):
            return s["section_id"]
    if sections and time_s >= float(sections[-1]["start"]):
        return sections[-1]["section_id"]
    return None


def light_change_rows(points: list[dict], sections: list[dict]) -> list[dict]:
    return [
        {
            "type": "light_change",
            "role": p["role"],
            "start_time": p["time"],
            "end_time": p["time"],
            "confidence": p["confidence"],
            "section_id": _section_id(float(p["time"]), sections),
        }
        for p in points
    ]


def bar_feature_rows(bars: list[dict], points: list[dict]) -> list[dict]:
    # Matched on time, not bar number: `bar` labels can repeat across a grid slip. The point's
    # `time` is where the change starts (up to one beat before its detection bar's edge), so the
    # role sits on the bar that contains it, the same bar/beat the timeline row reports.
    role_by_start: dict[float, str] = {}
    for p in sorted(points, key=lambda p: p["time"]):
        for b in bars:
            if b["start_s"] <= p["time"] < b["end_s"]:
                role_by_start.setdefault(b["start_s"], p["role"])
                break
        else:
            raise AnalysisError(f"publish-light-changes: point t={p['time']} is in no bar of bar_features.json")
    rows = []
    for b in bars:
        for col in ("kick_present", "sweep_state", *BAR_COLUMNS.values()):
            if col not in b:
                raise AnalysisError(f"publish-light-changes: artifact bar {b.get('bar')} has no {col!r} — rerun light-changes")
        rows.append({
            "bar": b["bar"],
            "start": b["start_s"],
            "end": b["end_s"],
            "irregular": bool(b["irregular"]),
            "brightness": b["brightness"],
            "transient_density": b["transient_mean"],
            "kick_present": b["kick_present"],
            "sweep_state": b["sweep_state"],
            "light_change_role": role_by_start.get(b["start_s"]),
        })
    return rows


def publish_light_changes(paths: SongPaths) -> dict:
    points = _need(paths.artifact("light_changes", "light_changes.json"))["points"]
    bars = _need(paths.artifact("light_changes", "bar_features.json"))["bars"]
    sections = _need(paths.sections_output_path)["sections"]
    timeline = _need(paths.timeline_output_path)

    kept = [e for e in timeline["events"] if e.get("type") != "light_change"]
    events = kept + light_change_rows(points, sections)
    events.sort(key=lambda e: (e["start_time"], e["end_time"]))      # stable: gestures first on ties
    emitted = {k for e in events for k in e}
    sources = dict(timeline["field_sources"])
    sources["role"] = "light_changes"
    timeline_payload = {
        "schema_version": SCHEMA_VERSION,
        "song_name": paths.song_name,
        "field_sources": validate_field_sources(sources, emitted, file="song_event_timeline.json"),
        "events": events,
    }
    write_json(paths.timeline_output_path, timeline_payload)

    rows = bar_feature_rows(bars, points)
    bar_sources = validate_field_sources(
        {
            "bar": "essentia", "start": "essentia", "end": "essentia",
            "brightness": "essentia", "transient_density": "essentia",
            "irregular": "light_changes", "kick_present": "light_changes",
            "sweep_state": "light_changes", "light_change_role": "light_changes",
        },
        {k for r in rows for k in r},
        file="bar_features.json",
    )
    write_json(paths.bar_features_output_path, {
        "schema_version": SCHEMA_VERSION,
        "song_name": paths.song_name,
        "field_sources": bar_sources,
        "bars": rows,
    })
    return {"light_changes": len(points), "bars": len(rows)}
