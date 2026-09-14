# MCP regression fixtures

Committed, deliberately small, and **top-level files only** — no `artifacts/`,
no `reference/`. A fixture containing an inner folder would hide an exposure
violation instead of exposing it. Regenerate with:

    python mcp/tests/fixtures/build_fixtures.py

They describe a 24 s, 120 BPM song so the dense files (`loudness.json` at a
50 ms interval, `drum_events.json`) stay a few hundred rows.

| Fixture | Represents |
| --- | --- |
| `McpFull - Fixture` | **the primary baseline.** Fully populated: 3 sections with function fields, one complete `approach→build→tension→impact→release` gesture (`gesture-001`), a verse→chorus transition, a human hint with a `lighting_hint`, and every top-level file (`info`, `beats`, `sections`, `song_event_timeline`, `hints`, `genre`, `loudness`, `drum_events`). |
| `McpDegenerate - Fixture` | honest-uncertainty path: `function_status: "unknown"` on every section, every beat `confidence` null, empty gesture/hint lists, genre below its floor. |
| `McpPartial - Fixture` | explicit-error path: the required top-level `sections.json` is absent. |

`beats.json` and `sections.json` are **objects** — `{ "field_sources": {…},
"beats": [...] }` / `{ "field_sources": {…}, "sections": [...] }` — since v3.1
item 2. Every top-level file carries a `field_sources` header (default producer
per field, closed vocabulary), and the beats `confidence` field is
`downbeat_confidence`. `schema_version` is `"3.0"`.
