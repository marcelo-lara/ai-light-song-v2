# Implementation plan — v3.1

Builds the `mcp/` song-comprehension server defined in
[`mcp-definition.md`](mcp-definition.md), and the delivery surface it needs.

There is no `product-refinement-v3.1.md`: the requirements came directly from
the operator rather than from a refinement pass. The definition doc carries them.

## Ordering, and why

**Phase A is the scaffold**, first and alone: create `mcp/` and prove the
plumbing — SDK, stdio, Compose service, song discovery, the exposure guard —
before any data work. A wrong transport or container shape is far cheaper to
find in item 1 than after six items of publishing.

**Phase B publishes the delivery surface.** Four signals live only under
`artifacts/` today, plus two host-path leaks and the attribution convention that
every published value needs. The exposure rule makes these hard
prerequisites for the tools: the server cannot read `artifacts/`, so until
phase 4 publishes them there is nothing to serve.

**Phase C builds the two tools. Phase D closes the release.**

### The tool surface is expected to change

`get_song_overview` and `get_detail` will be reshaped in this refinement or the
next one. The plan is ordered and the module is structured so that churn is
cheap:

- **Split stable from volatile inside `mcp/`.** `loaders.py` — song discovery,
  reading top-level files, enforcing the exposure rule — is stable and is built
  in item 1. `serializers.py` — the response shapes — is volatile and is not
  written until items 9–10. A tool-surface change should touch `serializers.py`
  and its snapshots, and nothing else.
- **Tools come last**, so they are written once against a finished delivery
  surface rather than twice.
- **Golden snapshots are regenerated, not defended.** When the response shape
  changes deliberately, re-record them in the same commit with a one-line
  justification. They exist to catch *unintended* drift, and a snapshot churning
  on an intended change is the system working.
- Keep the delivery surface (Phase B) free of anything that exists only to suit
  today's response shape. Top-level files are the durable contract; the tools
  are a view over them.

### Dependencies

| Item | Needs | Notes |
| --- | --- | --- |
| 1 scaffold | nothing | reads the five top-level files that already exist |
| **2 attribution convention** | — | **every publishing item below depends on it**; also carries the `SCHEMA_VERSION` bump |
| 3 sections fuse | 2 | fuses allin1 boundaries/labels with the harmonic stage's `key` / `chord_progression` |
| 4 `gesture_id` | 2 | items 9 and 10 both need it, so it lands early |
| 5 `genre.json` | 2 | single producer today; published with attribution so a second can join |
| 6 `drum_events.json` | 2 | |
| 7 `loudness.json` | 2 | |
| 8 `info.json` paths | 1, 2 | must not remove `bpm`/`duration`; the deepest `ui/` change |
| 9 `get_song_overview` | 3, 4, 5 | |
| 10 `get_detail` | 4, 6, 7 | |
| 11 closure | all | |

Item 2 is the phase's gate: it defines how a published value says where it came
from, and items 3–8 all apply that convention. Items 3–8 are mutually
independent of each other and may be reordered or parallelised; the sequence
given puts the largest first and the deepest `ui/` change last.

---

## How this plan is worked

**Validate each item, then push it on its own.** Work one plan item at a time.
When an item is complete, run its tests the way this project requires — in the
container, `docker compose run --rm test` — and only if they pass, tick its
checkboxes, then commit and push that item by itself before starting the next.
Name the commit after the plan item as this plan writes it — for example
``9. `get_song_overview` ``. One commit per item, never a single batch commit at
the end: a later failure then cannot strand the validated work in front of it,
and the history reads as this plan's own sequence.

**Use the recommendation; only a genuinely blocking decision stops an item.** An
open question that surfaces mid-implementation is resolved by adopting the best
recommendation and continuing — do not idle waiting to ask. The exception is a
decision where proceeding under any assumption would make the work wrong or
wasted. In that case write the decision and its options into this plan as a new
`D` item, then **continue with the next item**, skipping only those that
genuinely depend on the blocked one. A single unresolved question must never
stall the whole run; everything independent of it still gets built.

---

## Status

| | |
| --- | --- |
| Items | 11 (1 scaffold, 7 delivery surface, 2 tools, 1 closure) |
| Items with a Visual QA block | 4 (items 2, 3, 4, 8) |
| MCP regression | `smoke-test` from item 1 onward; `full-regression` at item 11 ([`reference/mcp-regression.md`](reference/mcp-regression.md)) |
| Done | 5 |
| Contract-change note | `docs/contract-change-v3.1.md` — created in item 2, extended by items 3–8 |
| Blocking decisions (`D`) | none open |

---

## Standing rules for every item

- **Docker only.** Nothing runs on the host. Tests: `docker compose run --rm test`.
  Pipeline: `docker compose run --rm app ./analyze …`.
- **`mcp/` never reads `artifacts/` or `reference/`.** Not once, not as a
  fallback, not "just for this field". If a serializer needs a value that is not
  in a top-level file, the fix is a phase-4 change, not a deeper path.
- **No absolute host paths in any top-level file.** Every path-bearing field on
  the delivery surface is either removed or made relative to the song directory.
- **No silent fallbacks.** A serializer that cannot produce an honest value emits
  `null` or omits the key — never a plausible default.
- **Delete the docs with their subject.** Every item that invalidates a line in
  `docs/` fixes it in its own commit. Item 11 is the sweep for leftovers, not a
  place to defer to.
- **`SCHEMA_VERSION`** in `src/analyzer/models.py` is bumped once, in item 2, the
  first item that reshapes a projected file.
- **`smoke-test` is the gate on every item from item 1 onward.** An item whose
  own tests pass but which breaks the smoke suite is not done.
- Phase B items each append their section to `docs/contract-change-v3.1.md`, the
  handoff note for the external `ai-dmx-light-render` consumer.

### MCP regression — `smoke-test` and `full-regression`

Runbook: [`reference/mcp-regression.md`](reference/mcp-regression.md). It is not
tied to this release; it governs this implementation and every future one.

| Suite | When |
| --- | --- |
| **`smoke-test`** | after **every** item from item 1 onward, and before every commit touching `mcp/` |
| **`full-regression`** | item 11, before handoff, and after any change to the tool surface or the delivery surface |

Two consequences for this plan:

- **Item 1 builds the harness**, not just the server: the frozen fixtures under
  `mcp/tests/fixtures/analysis/`, the two named suite entry points, and the
  initial snapshots. Later items then have something to run.
- **Generated analysis is not committed** (`.gitignore` keeps
  `data/analysis/*/**` except `reference/`), so the suites run against committed
  fixtures, exactly as the UI suite does. A suite pointed at a local
  `data/analysis/` compares against whatever the last pipeline run produced,
  which is not a regression test.

Phase B items change the delivery surface the server reads, so each of them
re-runs `smoke-test` after regenerating fixtures — a published-file change is
precisely what breaks a loader quietly.

### UI touch points

Four items reshape a file the debugger reads. None of them is *intended* to
change a pixel, which makes the visual baselines a strong check: **an unchanged
baseline is the pass condition, and any diff is an unintended regression.**

Full runbook: [`reference/ui-regression.md`](reference/ui-regression.md).

| Item | File | UI work |
| --- | --- | --- |
| 2 | every top-level file | **the big one.** `beats.json` / `sections.json` become objects, so `parsers.ts` must unwrap them; `confidence` becomes `downbeat_confidence`; `types.ts` gains `field_sources` / `source`; `parsers.test.ts` updated; fixtures rebuilt; baselines re-verified |
| 3 | `sections.json` | `types.ts` gains the four fields; fixtures rebuilt; baselines re-verified |
| 4 | `song_event_timeline.json` | `types.ts` gains `gesture_id`; fixtures rebuilt; baselines re-verified |
| 8 | `info.json` | `types.ts`, **`ui/src/data/parsers.ts`** (drops `song_path`, `artifacts`, `outputs`), **`ui/src/data/parsers.test.ts`** (its `expect(info.outputs).not.toBeNull()` assertion); fixtures rebuilt; baselines re-verified |

The shared steps for each of those items:

1. `ui/src/data/types.ts` — the shape the UI declares must match what the
   pipeline now writes, even for fields nothing renders. A stale type is how the
   next reader learns the wrong contract.
2. `python3 tests/ui-visual/fixtures/build-fixtures.py` — the frozen fixtures
   under `tests/ui-visual/fixtures/analysis/` carry `info.json`, `sections.json`
   and `song_event_timeline.json`. A reshape leaves them stale, and stale
   fixtures make the visual suite assert against a contract that no longer
   exists.
3. Re-run the visual suite and confirm the baselines under
   `tests/ui-visual/__screenshots__/` are **unchanged**. Do not re-record them:
   none of these items should alter a rendered pixel, so a diff is a finding,
   not a baseline to bless.
4. `docker compose run --rm --no-deps --entrypoint sh ui -c "npm run build && npm test"`.

**Items 4, 5 and 6 add new top-level files the debugger does not read** — it
reads the `artifacts/` originals. Do **not** add them to the fixture list in
`build-fixtures.py`; `loudness.json` alone would add ~9 MB per fixture song for
no coverage.

---

## Phase A — the scaffold

### 1. Module skeleton, Compose service, song discovery, and a proven round-trip

**First item deliberately.** It creates `mcp/` and proves the plumbing — SDK,
stdio, Compose service, song discovery, the exposure guard — before any data
migration work. If the transport or the container shape is wrong, that is far
cheaper to find now than after six items of publishing work.

It serves no musical content yet beyond song discovery. That is the point: the
basics are testable on their own.

- [x] `mcp/` at the repo root: `pyproject.toml` (or `requirements.txt`, matching
      repo convention), `mcp/server.py`, `mcp/loaders.py`, `mcp/tests/`.
      Unit tests live **inside** `mcp/`, colocated, not in the root `tests/`.
      **No `serializers.py` yet** — response shaping is items 9–10. Keeping the
      volatile half out of this item is what makes a later tool-surface change
      cheap.
- [x] Official `mcp` SDK, stdio transport, read-only. The server never writes,
      and holds no state between calls.
- [x] `mcp/loaders.py` resolves a song by directory name under
      `data/analysis/` and loads top-level `*.json` only. It must expose **no**
      function capable of reaching into `artifacts/` or `reference/`.
- [x] Implement **`list_songs()`** in full — every analysable song directory with
      its `song_name`, `bpm` and `duration` from `info.json`. It is small, it is
      genuinely needed (a client cannot guess directory names), and it makes the
      round-trip provable without stubbing anything.
- [x] Register `get_song_overview` and `get_detail` as declared tools that return
      an explicit "not implemented yet" error. A declared-but-unimplemented tool
      is honest; a tool returning a plausible empty payload is not.
- [x] A song directory missing a required top-level file produces an explicit
      error naming the file — never a partial response with silent gaps.
- [x] `docker-compose.yml`: an `mcp` service on its own image. It must not reuse
      the analyzer image, and it mounts `./data:/data` **read-only** — the mount
      itself enforces the read-only rule rather than trusting the code.
- [x] **The invocation contract.** This is a stdio server: the *client* spawns
      it, so `docker compose up mcp` is not how it runs. The client's config
      names `docker compose run --rm -T mcp` as its command — `-T` is required,
      since without it Compose allocates a TTY and corrupts the stdio framing.
      Document the exact client-config snippet in `docs/mcp-definition.md`, and
      accept per-session container startup as the cost of keeping the runtime in
      Docker.
- [x] `mcp/tests/test_exposure.py`: a guard test that greps the module's own
      source for `artifacts/` and `reference/` and fails on any hit. This makes
      the exposure rule a failing test rather than a convention.
- [x] **Build the regression harness** per
      [`reference/mcp-regression.md`](reference/mcp-regression.md): the three
      committed fixtures under `mcp/tests/fixtures/analysis/`
      (`McpFull`, `McpDegenerate`, `McpPartial`) and their generator script, plus
      `smoke-test` and `full-regression` as **named entry points** an executor
      can invoke by name. Keep the fixtures small — a short song, so
      `loudness.json` at the 20 ms floor is a few thousand frames.
- [x] Fixtures carry the top-level file set **only** — no `artifacts/`, no
      `reference/`. A fixture containing them would hide an exposure violation
      rather than expose it.
- [x] Tick the harness boxes in `reference/mcp-regression.md` "Outstanding
      harness work" as they land.
- [x] `docs/mcp-definition.md`: change the status banner from "specified, not
      built" to "scaffold built; `get_song_overview` and `get_detail` pending".

**Tests — this is the "basics work" gate.** In the container:

1. `docker compose build mcp` succeeds.
2. The server starts over stdio and completes an MCP initialize handshake.
3. `tools/list` returns exactly three tools: `list_songs`, `get_song_overview`,
   `get_detail`.
4. `list_songs()` against the **fixture root** returns the three committed
   fixtures, each with a non-null `song_name`, `bpm` and `duration`. The suites
   run against fixtures, never against a local `data/analysis/` — see
   [`reference/mcp-regression.md`](reference/mcp-regression.md) "Fixtures and
   determinism".
5. `list_songs()` on an empty analysis root returns an empty list, not an error.
6. Optional, developer-local only: pointed at a populated `data/analysis/`,
   `list_songs()` returns every song directory present. Not a suite check —
   the count depends on what that machine has run.
7. Requesting an unknown song name errors with the name in the message.
8. Calling `get_song_overview` returns the explicit not-implemented error.
9. `mcp/tests/test_exposure.py` passes.
10. Writing to the mount fails — confirm the read-only bind actually holds.

Then run the suite itself: **`smoke-test` passes all eleven checks**, reported
with observed values. From this item onward it is the gate on every item.

**Note for item 8.** Check 4 pins `bpm` and `duration` as a shipped contract.
Item 8 strips fields from `info.json` and must not touch those two.

---

## Phase B — publish the delivery surface

Closes the open issue "Delivery surface — four MCP-projected signals still live
inside `artifacts/`" in [`issues.md`](issues.md). Delete that entry in item 11.

### 2. Establish the attribution convention

Every later publishing item depends on this existing, so it comes first in the
phase. It writes no new file — it defines how a published value says where it
came from, and applies it to the files that already ship.

Rationale and the two-part encoding:
[`reference/artifacts.md`](reference/artifacts.md) "Attribution on the delivery
surface".

- [x] Bump `SCHEMA_VERSION` in `src/analyzer/models.py` — this is the release's
      single bump, and this is the first item to reshape a projected file.
- [x] `src/analyzer/models.py`: a closed producer vocabulary — `essentia`,
      `allin1`, `harmonic`, `omnizart`, `demucs`, `gestures`, `genre`, `human`,
      `inference`, `unknown`. An unrecognised producer is an error, not a
      passthrough string.
- [x] Every top-level file gains a `field_sources` header: the default producer
      per field, declared once. A row carries its own `source` **only** where it
      departs from that default — so the common case costs one small block, and
      a departure is visible precisely because it is the only kind of row that
      carries one.
- [x] **`beats.json` and `sections.json` are bare JSON arrays today and become
      objects** — `{ "field_sources": {…}, "beats": [ … ] }` and
      `{ "field_sources": {…}, "sections": [ … ] }`. An array cannot carry a
      header, and a file that cannot say where its values came from defeats the
      convention. `info.json`, `hints.json` and `song_event_timeline.json` are
      already objects and need no reshaping.
- [x] This is the **widest-blast-radius change in the release.** Every consumer
      that iterates those two files breaks: `ui/src/data/parsers.ts` and its
      tests, the fixture builder, and the external cue-authoring server. Update
      the first three here; the last gets a prominent
      `docs/contract-change-v3.1.md` entry.
- [x] **Fix `beats.json`'s ambiguous confidence.** Its `confidence` describes
      the downbeat phase (allin1, 0.226 F1), not the beat time (essentia,
      trusted). Rename it `downbeat_confidence` so the field says what it
      measures. This is the clearest present instance of a fused row whose
      numbers read as belonging to the wrong producer.
- [x] **Do not** add a per-row source map to `beats.json`. At ~500 rows a
      repeated identical map is pure token cost against the very budget the
      `mcp/` server exists to protect.
- [x] Fusion reads **generated artifacts only**. Add a test asserting no
      publishing code path reads `reference/` — it stays validation-only, and
      this item is exactly where that could quietly slip.
- [x] `docs/reference/artifacts.md` — the per-file `field_sources` values.
- [x] `docs/contract-change-v3.1.md` — create it; first section records
      `field_sources`, the `source` override, the `confidence` →
      `downbeat_confidence` rename, and the **array → object** reshaping of
      `beats.json` and `sections.json`. Flag the reshaping first and loudest: it
      is the change most likely to break a downstream consumer silently, because
      a consumer that iterates the file will see an object and read nothing
      rather than error.

**Tests:** rebuild the MCP fixtures, then `smoke-test`; plus
`docker compose run --rm test`, the UI suite, and all four gold songs. Assert per song: every top-level file has a `field_sources` header whose
keys cover every field it emits; every `source` value is in the vocabulary; no
`beats.json` row carries a bare `confidence`; the `reference/` guard passes.

**Visual QA — item 2**

- Surface: `/?song=RegFull - Fixture`, after rebuilding fixtures.
- V1. No `console.error` or `console.warn` during load.
- V2. No `pageerror` or unhandled rejection.
- V3. No failed network response for a file the page expects.
- V4. The **Beats** grid still renders downbeats at the same positions; state the
  observed downbeat count. The container and field names change; **no value
  does**, so an empty or shifted grid means the unwrapping is wrong.
- V5. Every baseline under `tests/ui-visual/__screenshots__/` diffs **clean**
  against its committed image. A non-zero diff fails the item.

### 3. Merge the section function fields into top-level `sections.json`

A fusion item as well as a join fix: the published row already combines allin1
(boundaries, `function`, `confidence`) with the harmonic stage (`key`,
`chord_progression`), and `chord_progression`'s `null` gate comes from a
different producer's confidence than the row's own `confidence` field. Item 2's
`field_sources` header is what makes that legible.

The join fix as much as the exposure fix. Today `sections.json` and
`artifacts/section_segmentation/sections.json` are matched **by array index** —
same count, same order — and a mismatch silently misaligns every section's label
and confidence across the whole song.

- [x] `src/analyzer/stages/ui_data.py`: add `function`, `function_confidence`,
      `function_status` and `same_label_as` to each top-level `sections.json`
      row, read from the segmentation artifact at build time.
- [x] Keep `label`, `description`, `key`, `chord_progression`, `confidence`,
      `section_id`, `start`, `end` exactly as they are. `label` stays a display
      convenience; the numeric `function_confidence` is now on the row beside it.
- [x] Delete the index-matching assumption from the join: rows are built from the
      segmentation list directly, so there is no second list to misalign. Keep
      and extend `tests/test_ui_data_section_join.py`.
- [x] `docs/reference/artifacts.md`: update the `sections.json` row.
- [x] `docs/contract-change-v3.1.md`: create it; first section records the four
      added fields, the before/after row, and an explicit note that a consumer
      may now read section names from the top-level file alone and **must stop
      reading `artifacts/section_segmentation/sections.json`.**

**Tests:** rebuild the MCP fixtures, then `smoke-test`; plus
`docker compose run --rm test`, the UI suite, and all four gold songs. Assert per song: every top-level row carries `function` and
`function_status`; the `section_id` sequence still matches the segmentation
artifact one-for-one; a song flagged degenerate (`_test_song`) has
`function_status: "unknown"` on every row.

**Visual QA — item 3**

- Surface: `/?song=RegFull - Fixture`, after rebuilding fixtures.
- V1. No `console.error` or `console.warn` during load.
- V2. No `pageerror` or unhandled rejection.
- V3. No failed network response for a file the page expects.
- V4. The **Sections** lane renders the same block count as before the change; state the
  observed count.
- V5. Every baseline under `tests/ui-visual/__screenshots__/` diffs **clean**
  against its committed image. A non-zero diff fails the item — this change is
  not supposed to alter a rendered pixel.


### 4. Add `gesture_id` to `song_event_timeline.json`

`get_detail`'s `gesture_id` scope and `get_song_overview`'s gesture grouping
both depend on this, so it lands early in the phase rather than late.

- [x] `src/analyzer/stages/gestures.py`: assign every phase row belonging to one
      composite gesture a shared `gesture_id` (e.g. `"gesture-003"`), and leave
      section-pair transition rows without one. Today the file is 58 flat rows
      with 31 impacts and no grouping key, so "a drop's five-phase envelope"
      cannot be read without the server re-deriving the grouping — which would
      put gesture assembly logic in two places.
- [x] `docs/reference/artifacts.md` — the `song_event_timeline.json` row.
- [x] `docs/contract-change-v3.1.md` — `gesture_id` added.

**Tests:** rebuild the MCP fixtures, then `smoke-test`; plus
`docker compose run --rm test`, the UI suite, and all four gold songs. Assert: every gesture-phase row has a `gesture_id`; grouping by it yields
runs whose phases are time-ordered and non-overlapping; transition rows have
none. Extend `tests/test_gestures.py`.

**Visual QA — item 4**

- Surface: `/?song=RegFull - Fixture`, after rebuilding fixtures.
- V1. No `console.error` or `console.warn` during load.
- V2. No `pageerror` or unhandled rejection.
- V3. No failed network response for a file the page expects.
- V4. The **Gestures** lane renders the same block count as before the change; state the
  observed count.
- V5. Every baseline under `tests/ui-visual/__screenshots__/` diffs **clean**
  against its committed image. A non-zero diff fails the item — this change is
  not supposed to alter a rendered pixel.


### 5. Publish top-level `genre.json`

- [x] `ui_data.py` writes `data/analysis/{song}/genre.json` carrying
      `genres`, `confidence`, `top_predictions[]`, `guidance[]`, minus
      `generated_from` host paths, plus the `field_sources` header from item 2
      (`genre` for every field today).
- [x] `artifacts/genre.json` stays where it is; the analyzer and the UI keep
      reading it. This publishes a fused view, it does not move the artifact.
- [x] **Write the selection as a fusion even though there is one producer.** The
      publisher asks "which producer wins this field" and today gets one answer.
      A `genre.json` written as a straight copy is a publisher a second producer
      cannot be added to without a rewrite.
- [x] `docs/reference/artifacts.md`: add the top-level row.
- [x] `docs/contract-change-v3.1.md`: new-file entry.

**Tests:** rebuild the MCP fixtures, then `smoke-test`; plus
`docker compose run --rm test` and one gold song. Assert the top-level file
exists, parses, and contains no string beginning `/data/`.

### 6. Publish top-level `drum_events.json`

- [ ] `ui_data.py` writes `data/analysis/{song}/drum_events.json` with
      `events[] { time, event_type, confidence }` and the summary counts.
      600 KB / ~1,164 events per song is acceptable as-is; no decimation.
- [ ] Strip `generated_from` host paths; add the item-2 `field_sources` header
      (`omnizart` today). Same fusion-shaped selection as item 5.
- [ ] `docs/reference/artifacts.md` + `docs/contract-change-v3.1.md`.

**Tests:** as item 5 (including the fixture rebuild and `smoke-test`), plus:
event count and per-type counts equal the artifact's.

### 7. Publish top-level `loudness.json` at a 20 ms floor

The one item with a real size decision, already made: **20 ms** (~9 MB/song;
250 frames × 5 sources at the 5 s window cap). `interval_ms` is a *request*
parameter and the server decimates per read, so 20 ms is the finest a caller may
ask for, not what every read returns.

- [ ] `ui_data.py` writes `data/analysis/{song}/loudness.json` by
      decimating `artifacts/essentia/rms_loudness.json` from 10 ms to 20 ms.
      Decimate by **averaging pairs**, not by dropping every other frame — a
      dropped-frame series loses transient peaks, which is exactly what a drop
      impact is.
- [ ] `metadata.interval_ms: 20`, and `sources[]` reduced to
      `{ id, label, kind }` — **the `path` field is dropped**, it is the host-path
      leak. Note the name collision: this file's `sources[]` means *stems*, not
      producers. Keep the item-2 producer attribution in `field_sources` and do
      not overload `sources[]`.
- [ ] The 10 ms artifact is unchanged and stays the UI's source.
- [ ] `docs/reference/artifacts.md` + `docs/contract-change-v3.1.md`.

**Tests:** rebuild the MCP fixtures, then `smoke-test`; plus
`docker compose run --rm test` and one gold song. Assert: frame count is within
one frame of half the artifact's; `metadata.interval_ms == 20`;
successive frame times differ by 0.020 ± 0.001; no `path` key anywhere; the file
contains no string beginning `/data/`. Add `tests/test_loudness_publish.py`.

### 8. Strip host paths from `info.json`

The deepest UI change in the plan, and nothing downstream depends on it — so it
sits last in the phase where a problem cannot block anything else. Unlike items
2 and 3 this one **removes** fields the debugger actively parses.

- [ ] `ui_data.py`: `info.json` drops `song_path`, `artifacts`, `outputs`,
      `debug` and `generated_from`, or replaces them with paths relative to the
      song directory. **`song_name`, `bpm`, `duration` and `schema_version`
      stay** — item 1's `list_songs()` reads `bpm` and `duration`, and removing
      them would break a shipped, tested capability.
- [ ] `ui/src/data/parsers.ts` — remove the `song_path`, `artifacts` and
      `outputs` extractions from `parseInfo`. They are defensive
      (`stringOr(..., "")`, `o.artifacts ?? {}`), so the parser will not throw on
      the new shape, but leaving them declares a contract that no longer exists.
- [ ] `ui/src/data/parsers.test.ts` — drop
      `expect(typeof info.artifacts).toBe("object")` and
      `expect(info.outputs).not.toBeNull()`. These fail once the fixture's
      `info.json` is rebuilt, and they are the reason this item cannot be a
      pipeline-only change.
- [ ] `ui/src/data/types.ts` — remove the three fields from the info type.
- [ ] `docs/reference/artifacts.md` — the `info.json` row.
- [ ] `docs/contract-change-v3.1.md`. Flag this one prominently: it is the only
      item in the release that **removes** fields a consumer may read today.

**Tests:** rebuild the MCP fixtures, then `smoke-test`; plus
`docker compose run --rm test`, the UI suite
(`docker compose run --rm --no-deps --entrypoint sh ui -c "npm run build && npm test"`),
and all four gold songs. Assert: `info.json` contains no string
beginning `/data/`; `list_songs()` still returns non-null `bpm` and `duration`
for all 21 songs; `parseInfo` accepts the new shape and its test no longer
asserts on removed fields.

**Visual QA — item 8**

- Surface: `/?song=RegFull - Fixture`, after rebuilding fixtures.
- V1. No `console.error` or `console.warn` during load.
- V2. No `pageerror` or unhandled rejection.
- V3. No failed network response for a file the page expects.
- V4. The song loads and the header shows a non-empty song name and a non-zero
  duration — `info.json` is what feeds them, and this item edits it. State both
  observed values.
- V5. Every baseline under `tests/ui-visual/__screenshots__/` diffs **clean**
  against its committed image. A non-zero diff fails the item — this change is
  not supposed to alter a rendered pixel.


---

## Phase C — the tool surface

Both items write `mcp/serializers.py`. Neither touches `mcp/loaders.py` beyond
adding a read of a file item 1 did not need.

### 9. `get_song_overview`

- [ ] Implement the response defined in
      [`mcp-definition.md`](mcp-definition.md) "The tool surface": identity,
      grid (with the honest downbeat note), sections, gestures **grouped by
      `gesture_id`**, transitions, human hints.
- [ ] Never emit the full beat list — the grid block is a summary. Report how
      many downbeats carry `downbeat_confidence: null` (the field item 2 renames)
      so a caller knows whether bar numbers are usable on this song.
- [ ] Surface `function_status: "unknown"` explicitly, and carry the
      "label repetition, not acoustic identity" caveat wherever `same_label_as`
      groups sections.
- [ ] **Token budget:** assert the serialized overview for
      `Armin - Revolution` (7 sections, 58 event rows) is **under 6 KB**. If it
      is not, cut prose fields before cutting structure — the times, confidences
      and section ids are the payload; sentences are not.
- [ ] Replace the item-1 not-implemented error with the real handler.
- [ ] Golden snapshot per gold song in `mcp/tests/__snapshots__/`.

**Tests:** `smoke-test`, then the `mcp` suite. Assert: snapshot equality;
31 impact rows on `Armin - Revolution` collapse to the gesture count, not 31
entries; the size assertion above.

### 10. `get_detail`

- [ ] The three scopes — `section_id`, `gesture_id`, `start_ms`+`end_ms` —
      exactly one required. Two or zero is an error, not a precedence rule.
- [ ] **Dense cap: 5 s, a maximum not a default.** A resolved span over 5 s
      returns the structural view and withholds dense frames, stating that it
      did and naming the cap. Never truncate, never silently downsample to fit.
- [ ] `interval_ms` is caller-chosen; the server decimates the published 20 ms
      series. A request finer than 20 ms is an error naming the floor, not a
      silent upsample.
- [ ] `sources` narrows the stem set; default all five.
- [ ] Replace the item-1 not-implemented error with the real handler, and update
      the status banner in `docs/mcp-definition.md` — with this item the server
      is built, not scaffolded.
- [ ] Golden snapshots for: a section scope, a gesture scope, a 3 s window at
      20 ms, the same window at 100 ms, and an over-cap span.

**Tests:** `smoke-test`, then the `mcp` suite. Assert: the over-cap response
contains no dense frames and does contain the stated reason; `interval_ms=100` returns one fifth
the frames of `interval_ms=20` over the same window; `interval_ms=10` errors;
decimation preserves the window's peak value (the pair-averaging property
from item 7).

---

## Phase D — closure

### 11. Docs sweep and issue closure

- [ ] Delete the "Delivery surface — four MCP-projected signals" entry from
      [`issues.md`](issues.md); items 3–8 close it. Any part still outstanding
      stays as a narrowed entry rather than being deleted wholesale.
- [ ] `CLAUDE.md`: add `mcp/` to "Where things live" and to the module list;
      update the top-level file set (now eight files, not five).
- [ ] `README.md`: add the `mcp` service to the quick-start block and the layout
      table.
- [ ] `docs/reference/artifacts.md`: the layout tree gains `genre.json`,
      `drum_events.json`, `loudness.json`.
- [ ] `docs/reference/source-map.md`: add the `mcp/` module — `server.py`,
      `loaders.py`, `serializers.py` — and note that `src/` never imports it.
- [ ] `docs/reference/docker.md`: add the `mcp` service to the services table
      and its build command.
- [ ] `docs/analysis-definition.md`: remove the "phase 4 does not yet publish
      everything" note added when the exposure rule landed.
- [ ] `docs/contract-change-v3.1.md`: final read-through as the handoff note to
      `ai-dmx-light-render`. Deliver it, then delete it in the change that closes
      the release.
- [ ] Archive or delete this plan per the release-closure rule — one plan in
      `docs/` at a time.

- [ ] `docs/reference/mcp-regression.md`: close every box in "Outstanding
      harness work", or narrow the ones that remain rather than deleting them.

**Tests — the handoff gate.** `docker compose run --rm test`, the UI suite, and
a full `--all-songs` run to confirm the eight-file contract holds across all 21
songs. Then **`full-regression`** — all of `smoke-test` plus F1–F4, each check
reported with its observed value. The server is not handed off on a green
`smoke-test` alone.

---

## Decisions (`D`)

None open. Decisions already taken and folded into the items above:

| | Decision |
| --- | --- |
| D1 | `loudness.json` floor interval is **20 ms**, decimated by pair-averaging. |
| D2 | The dense-series window cap is **5 s**, a maximum rather than a default; over-cap requests get the structural view plus an explicit withholding notice. |
| D3 | `interval_ms` is a request parameter, not a publish-time constant. |
| D4 | Genre, drum events and loudness are **published views**, not moves — the artifacts stay for the analyzer and the UI. Each is written through the fusion path even where one producer wins today, so a second producer can be added without a rewrite. |
| D5 | `gesture_id` is assigned by `gestures.py` in phase 4, not re-derived by the server, so gesture assembly lives in one place. |
| D6 | `mcp/` splits `loaders.py` (stable) from `serializers.py` (volatile), so an expected tool-surface change touches one file and its snapshots. |
| D7 | Attribution is a **file-level `field_sources` header plus a per-row `source` only on rows that depart from it** — not a per-row map. On a ~500-row `beats.json` a repeated identical map is pure token cost against the budget `mcp/` exists to protect. |
| D9 | `beats.json` and `sections.json` **become objects** so they can carry a `field_sources` header. Self-description beats compatibility here, and both files are already being reshaped this release. |
| D10 | The server is invoked by its client as **`docker compose run --rm -T mcp`** over stdio. `-T` is mandatory — a TTY corrupts stdio framing. |
| D8 | `beats.json`'s `confidence` is renamed **`downbeat_confidence`**. It measures allin1's downbeat phase (0.226 F1), not essentia's beat time (trusted), and the unqualified name invites reading it as the wrong producer's number. |
| D11 | (item 1, resolved) `mcp==2.1.1` is the official SDK — the v2 stable line on PyPI; its API is snake_case (`from mcp.server import MCPServer`, `server.run(transport="stdio")`). No import shim: `mcp/` has no `__init__.py`, so the site-packages `mcp` package wins `import mcp`, and `server.py` runs as a script so `import loaders` resolves locally. `server_sdk.py`, `server_impl.py`, `mcp/client/` deleted as dead. |
| D12 | (item 1, resolved) The not-implemented tools raise `mcp.server.mcpserver.exceptions.ToolError` (a deep, non-re-exported import) so the message survives to the client as `is_error=True`; a bare exception is laundered by the SDK and the text is lost. Both tools validate `song` first, so unknown-song / missing-file are real testable errors from item 1 onward. |
| D13 | (item 1, resolved) Required top-level files today = `info/beats/sections/song_event_timeline/hints`. `genre/drum_events/loudness` are present in the Full/Degenerate fixtures but not yet required (mid-migration; items 5–7 publish them). `McpPartial - Fixture` omits `sections.json`. |
| D14 | (item 1, resolved) Item-1 fixtures use the **current committed shape** (bare arrays for `beats`/`sections`) to keep item 1 isolated; item 2 rebuilds them into the `field_sources`-header object shape. Noted in the fixture README. |
| D16 | (item 2, resolved) `field_sources` coverage is checked as **header ⊇ emitted keys** (coverage, not strict equality), so a field that appears on only some rows — `gesture_id` on gesture-phase rows but not transition rows — does not break the check. Four keys are reserved and need no entry: `schema_version`, `generated_from`, `field_sources`, `song_name` (identity/provenance metadata, not fused values). |
| D17 | (item 2, resolved) `info.json`'s `field_sources` covers `bpm` / `duration` (→ `essentia`) only. `song_path` / `artifacts` / `outputs` / `debug` are orchestration metadata, not fused delivery-surface values, and are passed as an explicit `exempt` set to the validator rather than force-fit to a producer — item 8 removes them outright. |
| D18 | (item 3, resolved) The top-level → `section_segmentation` **array-index match was already gone** — `ui_data.build_ui_data` builds section rows straight from the segmentation list joined on `section_id` (v1.1 item 3.2 guard). Item 3's fix is therefore to **emit `function` / `function_confidence` / `function_status` / `same_label_as` on the top-level row** so no consumer ever needs to open the artifact; the UI's `sectionsContent` still accepts the segmentation list as an optional second arg (a `section_id` join, not index) and is left as-is since the UI may read `artifacts/`. |
| D19 | (item 3, resolved) `function_status` on a top-level row defaults to `"unknown"` when the segmentation row omits it (honest default, matches how `_format_section_label` already reads it) — never a guessed `"known"`. |
| D20 | (item 4, resolved) The pre-existing exact-`(type, start, end)` dedup in `build_gestures` can collapse a primitive shared by two nearby impacts into one row, so a gesture may lose a phase; grouping by `gesture_id` then yields time-ordered, non-overlapping runs (verified on all four gold songs) but not always all five phases. That is existing dedup behaviour, not introduced here. |
| D21 | (items 5-7, resolved) `field_sources` coverage on the new list/frame files (`drum_events.json`, `loudness.json`) is checked against the **repeating row/frame keys** — matching the `beats.json` precedent — while file-level aggregate blocks (`summary`, `supported_event_types`, `metadata`, `sources`) are provenance-exempt, like `schema_version`. They describe the file, not a fused per-row value. |
| D23 | (items 5-7, resolved) `genre` / `drum_events` / `loudness` stay **optional** in `mcp/loaders.py`'s `REQUIRED_TOP_LEVEL_FILES` this release (as D13 set): the fixtures carry them, but a degenerate real song may lag a pipeline rerun, and a missing-file hard error there would be a worse failure than their absence. Revisit when the tools (items 9-10) actually consume them. |
| D15 | (item 1, resolved) smoke-test checks S2.6 / S2.7 (and full-regression F2–F4) are reported `DEFER` with the observed not-implemented error text — never pass, never silently skipped — until serializers land in items 9–10. Recorded in `docs/reference/mcp-regression.md` under S2. |

Still open, deliberately deferred out of this release:

| | Question |
| --- | --- |
| Q1 | Whether the delivery surface keeps all five loudness sources or drops to mix + drums. Revisit once real token costs are measured against item 9's budget. |
