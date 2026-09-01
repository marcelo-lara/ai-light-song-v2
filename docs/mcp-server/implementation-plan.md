# Implementation Plan — MCP Server v1

Turns [product-definition.md](product-definition.md) into ordered, validated
work. Scope is the song-understanding surface only: `list_songs`,
`get_song_dynamics`, `get_drop_sequence`, `get_segment_detail`.

## How this plan is worked

**Validate each item, then push it on its own.** Work one plan item at a time.
When an item is complete, run its tests in the container as the item specifies;
only if they pass, tick its checkboxes, then commit and push that item by itself
before starting the next. Name the commit after the plan item as this plan
writes it — for example ``1.2 get_song_dynamics``. One commit per item, never a
single batch commit at the end: a later failure then cannot strand the validated
work in front of it, and the history reads as this plan's own sequence.

**Use the recommendation; only a genuinely blocking decision stops an item.** An
open question that surfaces mid-implementation is resolved by adopting the best
recommendation and continuing — do not idle waiting to ask. The exception is a
decision where proceeding under any assumption would make the work wrong or
wasted. In that case write the decision and its options into this plan as a new
`D` item, then **continue with the next item**, skipping only those that
genuinely depend on the blocked one. A single unresolved question must never
stall a whole run; everything independent of it still gets built.

## Status

| # | Item | State |
| --- | --- | --- |
| 0.1 | Package skeleton, config, read-only loader, `list_songs` | ☐ |
| 0.2 | Fixture set and test harness | ☐ |
| 1.1 | Projection serializers | ☐ |
| 1.2 | `get_song_dynamics` | ☐ |
| 2.1 | Dense-signal downsampler + `signal` block | ☐ |
| 2.2 | `get_drop_sequence` | ☐ |
| 2.3 | `get_segment_detail` | ☐ |
| 3.1 | Token-budget guards | ☐ |
| 3.2 | Server entrypoint, transport, error types | ☐ |
| 3.3 | Docs, README wiring, stdio smoke test | ☐ |

## Test approach

- **Fixtures, not live data.** A frozen copy of two analyzed songs under
  `tests/mcp/fixtures/analysis/` — one fully-populated real track (`_test_song`,
  which carries drop-sequence hints and a composite drop) and one deliberately
  sparse track (no drops, minimal hints) so a real bug is not mistaken for a
  thin fixture. QA never points at `data/analysis/`.
- **Contract tests** (`pytest`): every tool called against both fixtures, the
  response validated against a JSON schema and against golden snapshots checked
  into `tests/mcp/golden/`. Snapshot updates are a reviewed commit with a
  one-line reason.
- **Size assertions**: each golden snapshot test asserts `budget.approx_tokens`
  is under the item's stated ceiling, so a projection that regresses into
  verbosity fails.
- **stdio smoke test** (item 3.3): start the server, list tools, call each once,
  assert no error and a well-formed envelope.
- All runs in the container:
  `docker compose run --rm app python -m pytest tests/mcp/ -q`.

---

## Phase 0 — Skeleton

### 0.1 Package skeleton, config, read-only loader, `list_songs`

- [ ] `mcp/` package: `pyproject` (or wired into the existing one), entry point
      `als-mcp`, `mcp/src/als_mcp/` layout, colocated `mcp/src/als_mcp/tests/`
      or `tests/mcp/`.
- [ ] `AnalysisRoot` resolver: `ALS_ANALYSIS_ROOT` env / config arg, default
      `./data/analysis`. Fails loudly if the root does not exist.
- [ ] Read-only artifact loader: opens a named file under
      `<root>/<song>/…`, parses JSON, refuses any path that escapes the song
      directory, never opens for write. Small `(song, path, mtime)` cache.
- [ ] `list_songs()` tool: enumerate song directories, return
      `[{ song, duration_s, bpm, has_analysis }]` (`has_analysis` false when the
      seven top-level files are not all present).

**Test:** `tests/mcp/test_loader.py` — root resolution, path-escape rejection,
cache hit on unchanged mtime; `test_list_songs.py` against both fixtures.
**Commit:** `0.1 package skeleton and list_songs`

### 0.2 Fixture set and test harness

- [ ] Freeze `_test_song` and one sparse track into
      `tests/mcp/fixtures/analysis/`, including `reference/human/human_hints.json`
      for `_test_song`.
- [ ] `conftest.py` fixtures: an `AnalysisRoot` pointed at the frozen tree, an
      in-process server handle for direct tool calls.
- [ ] JSON-schema files for each tool response under `tests/mcp/schemas/`.
- [ ] Golden-snapshot helper: write-on-missing, diff-on-present, size assertion.

**Test:** the harness self-tests — schema files parse, golden helper round-trips.
**Commit:** `0.2 fixture set and test harness`

---

## Phase 1 — Whole-song dynamics

### 1.1 Projection serializers

Pure functions, `artifact dict → compact dict`, no tool or transport logic.

- [ ] `section_row(seg_row, top_row)` — joins the segmentation and top-level
      section entries **on `section_id`**; raises on a missing/duplicate id.
      Emits `section_id, start_s, end_s, form_role, form_role_confidence,
      energy_character, repetition_group, variant_of, description, confidence`.
- [ ] `event_row(event)` — overview form: `id, type, start_s, end_s, intensity,
      section_id, confidence, provenance`; composite drops collapse to one row
      with `composite, phase_count, impact_s`. No prose.
- [ ] `event_detail(event)` — full form with `summary`, `evidence_summary`,
      `musical_cue` (the `lighting_hint` run through a sanitiser that strips
      fixture phrasing or drops the field).
- [ ] `energy_arc(rms_loudness, sections)` — coarse `{ time_s, intensity }` per
      section (or per bar-group for long sections), from the mix source,
      hard-capped point count.
- [ ] `drop_index(events)` — `{ drop_id, impact_s, start_s, end_s, confidence,
      phase_count }` per composite drop; `drop_id` = `"drop-N"` in impact order.
- [ ] `character(info, genre, sections_artifact)` — `genre[], genre_confidence,
      genre_guidance[] (verbatim), form_family (+confidence), key, mode`.
- [ ] Confidence/provenance pass-through helper — pulls the numeric confidence
      from the segmentation row when the top-level only has it in `label`.

**Test:** `tests/mcp/test_serializers.py` — each serializer against fixture
fragments; the `section_row` join failure modes; the musical-cue sanitiser on
known fixture strings.
**Commit:** `1.1 projection serializers`

### 1.2 `get_song_dynamics`

- [ ] Compose `meta`, `character`, `sections[]`, `dynamics[]`, `energy_arc[]`,
      `drops[]` from the 1.1 serializers.
- [ ] No free-text field anywhere in the response (asserted in the test).
- [ ] `budget` block: `approx_tokens`, `rows`, `truncated`.

**Test:** `tests/mcp/test_get_song_dynamics.py` — golden snapshot for both
fixtures; assert no prose keys present; assert `approx_tokens` under the ceiling
(target: a 4-minute song's overview well under ~1.5k tokens — tighten to the
observed number once measured).
**Commit:** `1.2 get_song_dynamics`

---

## Phase 2 — Segment detail

### 2.1 Dense-signal downsampler + `signal` block

- [ ] `downsample(rms_loudness, start_s, end_s, target_interval_ms=250,
      max_frames)` — aggregates the 10 ms frames per source to the target
      interval, caps the frame count, returns the interval actually used.
- [ ] `drum_window(drum_events, start_s, end_s)` — onsets in the span, capped.
- [ ] `signal_block(...)` — `{ interval_ms, sources[], frames[], drum_onsets[],
      truncated }`, only built when `include_signal` and the span ≤ the dense cap
      (default 15 s).

**Test:** `tests/mcp/test_downsample.py` — frame math, interval reporting, cap
enforcement, span-too-wide rejection.
**Commit:** `2.1 dense-signal downsampler`

### 2.2 `get_drop_sequence`

- [ ] Resolve `drop_id` → the composite event (via `drop_index`).
- [ ] Emit `drop_id, section_id, start_s, end_s, confidence, intensity`,
      the ordered `phases[]` (`approach → build → tension → impact → release`,
      each `{ phase, start_s, end_s, intensity_start, intensity_end }`),
      `member_event_ids[]` + expanded members, and the `evidence` breakdown
      (`drop_evidence` metadata).
- [ ] If the export's composite has fewer than five phases (pre-v2.2 pipeline),
      return what exists and set `partial_envelope: true`.
- [ ] Optional `signal` block (item 2.1) over the gesture span.
- [ ] Unknown `drop_id` → typed `drop_not_found` listing the song's drop ids.

**Test:** `tests/mcp/test_get_drop_sequence.py` — golden snapshot for
`_test_song`'s drop; `partial_envelope` path on a trimmed fixture; `drop_not_found`;
`include_signal` on and off.
**Commit:** `2.2 get_drop_sequence`

### 2.3 `get_segment_detail`

- [ ] Accept `{ start_ms, end_ms }` or `{ section_id }` (resolved to the
      section's span). Reject a span wider than the detail cap (default 45 s).
- [ ] `events[]` — every event overlapping the span in `event_detail` form.
- [ ] `hints[]` — inference hints from `hints.json` plus merged human hints from
      `reference/human/human_hints.json` in the span, `{ source, category, text,
      start_s, end_s }`.
- [ ] `beats[]` — grid slice `{ time_s, type, bar, beat }`, downbeats flagged,
      row-capped.
- [ ] `sections_touched[]`, optional `signal` block, `budget` block.

**Test:** `tests/mcp/test_get_segment_detail.py` — golden snapshots for a
window query and a `section_id` query; span-too-wide rejection; human-hint merge
present for `_test_song`.
**Commit:** `2.3 get_segment_detail`

---

## Phase 3 — Budget, transport, docs

### 3.1 Token-budget guards

- [ ] Central `budget` accounting: approx token estimate (chars/4 or a tokeniser
      if cheap), row counts, `truncated` with a machine-readable reason and the
      follow-up call that would fetch the rest.
- [ ] Field caps: any string field over N chars is truncated with an ellipsis
      marker; overview responses reject prose keys structurally.
- [ ] Response ceiling: a tool whose composed response exceeds its hard ceiling
      truncates deterministically (drop optional blocks first, then oldest rows)
      and says so.

**Test:** `tests/mcp/test_budget.py` — a synthetic oversized fixture triggers
truncation; `truncated` names the right follow-up; overview prose-key guard.
**Commit:** `3.1 token-budget guards`

### 3.2 Server entrypoint, transport, error types

- [ ] `als-mcp` entry point: stdio server via the `mcp` SDK, registers the four
      tools with typed input schemas.
- [ ] Typed errors: `song_not_found`, `section_not_found`, `drop_not_found`,
      `artifact_missing`, `span_too_wide`, `stale_analysis` (warning, not fatal).
- [ ] Tool-name prefix `song.` on all four (`song.list`, `song.dynamics`,
      `song.drop_sequence`, `song.segment_detail`), marking this as the
      song-comprehension server so a host that also mounts the
      `ai-dmx-light-render` cue-authoring server keeps the two legible. No
      cue-authoring tool is ever added here (product-definition §2).

**Test:** `tests/mcp/test_server.py` — tool registration, each error type
raised by a crafted input.
**Commit:** `3.2 server entrypoint and error types`

### 3.3 Docs, README wiring, stdio smoke test

- [ ] `mcp/README.md` — run instructions, config, an example MCP client entry
      (`command`, `args`, `env`).
- [ ] Root `README.md` — add `mcp/` to the repository-layout section and the
      documentation map (pointer only).
- [ ] `docs/README.md` — add the `mcp-server/` folder to the documentation map.
- [ ] `docs/Implementation_Guide.md` — one row for the MCP component and its
      read surface.
- [ ] stdio smoke test in `tests/mcp/test_smoke.py`: launch, list tools, call
      each against the fixture root, assert clean envelopes.

**Test:** `pytest tests/mcp/ -q` green end to end; smoke test passes.
**Commit:** `3.3 docs and stdio smoke test`

---

## Contract direction (note for the analyzer side)

This song-comprehension server lives in this repo, so for it the contract-change
flow reverses: when an analyzer change reshapes an artifact it projects
(`sections.json`, `song_event_timeline.json`, `beats.json`, `hints.json`,
`genre.json`, `rms_loudness.json`, `drum_events.json`), the **same change**
updates the affected serializer in `mcp/` and its golden snapshots — the tests
fail if the projection drifts.

The separate `ai-dmx-light-render` cue-authoring server also consumes these
artifacts and is **not** in this tree, so a reshape that affects its read
surface still gets a `contract-change-vX.Y.md` note for it to absorb, exactly as
before.

Artifact shapes this server depends on that the analyzer does not yet guarantee
(the five-phase drop envelope becoming pipeline-wide; a first-class per-section
mood descriptor) are raised as refinement items against the analyzer, per
[product-definition.md](product-definition.md) §7 and §11.
