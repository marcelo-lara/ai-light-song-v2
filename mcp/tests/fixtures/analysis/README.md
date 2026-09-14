# MCP regression fixtures

Committed, deliberately small, and **top-level files only** — no `artifacts/`,
no `reference/`. A fixture containing an inner folder would hide an exposure
violation instead of exposing it. Regenerate with:

    python mcp/tests/fixtures/build_fixtures.py

They describe a 24 s, 120 BPM song so the dense files (`loudness.json` at the
20 ms floor, `drum_events.json`) stay a few hundred rows.

| Fixture | Represents |
| --- | --- |
| `McpFull - Fixture` | **the primary baseline.** Fully populated: 3 sections with function fields, one complete `approach→build→tension→impact→release` gesture (`gesture-001`), a verse→chorus transition, a human hint with a `lighting_hint`, and every one of the 9 required top-level files (`info`, `beats`, `hints`, `sections`, `song_event_timeline`, `genre`, `drum_events`, `loudness`, `arrangement_state`). |
| `McpDegenerate - Fixture` | honest-uncertainty path: `function_status: "unknown"` on every section, every beat `confidence` null, empty gesture/hint lists, genre below its floor. Still carries all 9 required files — `arrangement_state.json` has no degraded/absent path any more (v3.6 item 9). |
| `McpPartial - Fixture` | explicit-error path: the required top-level `sections.json` is absent; every other one of the 9 required files is present. |

`beats.json` and `sections.json` are **objects** — `{ "field_sources": {…},
"beats": [...] }` / `{ "field_sources": {…}, "sections": [...] }` — since v3.1
item 2. Every top-level file carries a `field_sources` header (default producer
per field, closed vocabulary), and the beats `confidence` field is
`downbeat_confidence`.

**v3.6 item 9** rebuilt every fixture to the item-8 top-level schema:
`beats.json` rows drop `chord`; `sections.json` rows drop
`label`/`description`/`chord_progression`; `hints.json` is a flat `hints[]`
(no `sections[]` wrapper, no per-row `source` — every hint is human by
construction, declared once in `field_sources`); `genre.json` drops
`top_predictions`/`guidance`; `drum_events.json` collapses per-event
`confidence` to one file-level `confidence: null` + `confidence_reason`;
`loudness.json` flattens `interval_ms`/`source_order` out of a `metadata`
wrapper (and drops `sources[]`); `song_event_timeline.json` drops
`section_name`/`summary`/`evidence_summary`/file-level `generated_from`.
`arrangement_state.json` became a required top-level file (no more optional/
pre-v3.2-absent path) — every fixture now carries it. `schema_version` is
`"3.6"` on the files this item touched, `"3.0"` on the two it left alone
(`info.json`, and `sections.json`/`beats.json`'s inner objects, which carry no
`schema_version` field at all).
