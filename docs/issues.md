# Open issues

**Pending issues only** (a queue, not a history). Solving one means deleting its
entry in the same change; write anything durable into the relevant definition
doc first. An empty queue is not a claim that the analysis is in good shape —
see [`analysis-definition.md`](analysis-definition.md) "Known gaps".

Scope each entry to one problem, one validation target, and one success
condition — and make the success condition mean the *stage* improved, not that
one song stopped complaining.

Current focus song: `_test_song`
(`reference/human/human_hints.json`, `reference/moises/chords.json`,
`artifacts/validation/phase_1_report.json`).

## Open queue

### `gestures` — per-primitive precision has never been audited by ear

- **Status:** `pending`
- **Raised:** 2026-09-05, on closing the v3.0 release docs. This was the one
  risk the release accepted and did not discharge, and it is the largest
  unmeasured risk in the shipped pipeline.
- **Problem:** the gestures stage is scored on impact *recall* against seven
  hand-clicked impacts. A phantom primitive — a riser, a build or a tension
  span asserted where the music has none — does not move that metric at all,
  yet it fires a cue that contradicts the song. Nothing currently measures how
  often that happens.
- **Evidence to use:** every gesture phase in `song_event_timeline.json`
  carries its per-primitive evidence string, so the audit is possible against
  the shipped artifacts without re-running anything.
- **Validation target:** the four gold songs (`Titanium - David Guetta ft Sia`,
  `Armin - Revolution`, `Hideaway - Kiesza`, `_test_song`), auditioned in the
  debugger against the waveform.
- **Success condition:** a per-primitive precision figure exists for each
  gesture phase across the gold set, and either the false-positive rate is
  written into `CLAUDE.md` as a known bound, or the primitives responsible for
  the phantoms are tightened until it is.

### `ui-visual` — three items left open from the regression-suite handoff

- **Status:** `pending`
- **Raised:** 2026-09-05, on trimming the suite's own checklist out of
  [`reference/ui-regression.md`](reference/ui-regression.md).
- **Open items:**
  1. Decide the `_test_song` audio question. Interim: `RegFull` / `RegPartial`
     ship the real mp3; `_test_song` has none, so its baseline is the
     beat-pulse fallback. The open call is whether `RegFull` keeps the mp3 or
     moves to a pre-decoded peaks JSON.
  2. Fold the smoke-check list from `ui/README.HELPER_UI.md` into explicit
     assertions, so the README checklist and the suite cannot drift apart.
  3. Corner-pixel checks on `humanHints` / `sections` blocks; re-diff
     `song-full` after squaring the block corners.
- **Success condition:** all three resolved, or the suite's scope explicitly
  narrowed to exclude them.

### Delivery surface — four MCP-projected signals still live inside `artifacts/`

- **Status:** `pending`
- **Raised:** 2026-09-05, when the operator set the exposure rule: MCP-exposed
  JSON lives only at `data/analysis/<Song - Artist>/*.json`, and `artifacts/` /
  `reference/` are readable by the analyzer and the debugger UI alone.
- **Problem:** phase 4 does not yet publish everything the projection needs, so
  [`mcp-definition.md`](mcp-definition.md) currently documents the target rather
  than what the pipeline emits. Four signals are affected:

  | Signal | Today | Needs |
  | --- | --- | --- |
  | section `function`, `function_confidence`, `function_status`, `same_label_as` | `artifacts/section_segmentation/sections.json`, index-matched to the top-level row | merge onto the top-level `sections.json` row |
  | genre | `artifacts/genre.json` (4 KB, self-contained) | publish as top-level `genre.json` |
  | drum events | `artifacts/symbolic_transcription/drum_events.json` (600 KB, 1,164 events) | publish as top-level `drum_events.json` |
  | loudness | `artifacts/essentia/rms_loudness.json` — **18 MB/song**, 19,401 frames at 10 ms across 5 sources, and it embeds absolute host paths (`/data/songs/…`, `/data/analysis/…/stems/…`) | publish a top-level `loudness.json` at a chosen floor interval, with no host paths; never copy the 10 ms file to the delivery surface |

- **Why the merge is a win beyond compliance:** the top-level `sections.json`
  and the segmentation file are currently matched **by array index** — same
  count, same order. A mismatch silently misaligns every section's label and
  confidence across the whole song. Merging the fields dissolves that failure
  mode.
- **Decided:** the published floor for `loudness.json` is **20 ms** (~9 MB/song;
  250 frames x 5 sources at the 5 s window cap). `interval_ms` is a request
  parameter and the server decimates per read, so 20 ms is the finest a client
  may ask for, not what every read returns.
- **Open decision:** whether the stem set stays at five sources on the delivery
  surface.
- **Success condition:** the MCP server can satisfy every read in
  `mcp-definition.md` using only `data/analysis/<Song - Artist>/*.json`, and
  no top-level file embeds an absolute host path.
