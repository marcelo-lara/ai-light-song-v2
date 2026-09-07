# Implementation plan — v3.2

Promotes the `arrangement_state` experiment
([`experiments/arrangement_state/README.md`](../experiments/arrangement_state/README.md))
into the production pipeline as a phase-3 stage, and publishes its output as a
new top-level delivery-surface file `arrangement_state.json`.

There is no `product-refinement-v3.2.md`: the requirements came directly from
the operator in the promotion conversation, and the experiment README carries
the measured evidence. This plan records the three decisions taken there:

1. **Reach test resolved as a new top-level file.** The signal lands in its own
   `data/analysis/{song}/arrangement_state.json`, not as new rows in
   `sections.json`. The file is shaped so the CLAP character layer
   ([`experiments/clap/README.md`](../experiments/clap/README.md)) can fuse a
   *feel* field into the same rows later without a rewrite — "the stems say what
   is playing; CLAP says how it feels."
2. **Promote on `_test_song` evidence alone.** On the one densely
   texture-labelled gold song the detector scores F1 0.59 @0.5 s (median hit
   error 0.07 s) where `sections.json` scores 0.00. Corpus-wide it sits at the
   noise floor of the labels (32 of 47 gold hints are drop stages `gestures.py`
   owns). The stage ships with an honest `margin_db`-derived confidence and
   emits `null` where a block has no measured margin — it never inflates a weak
   block to keep a row populated.
3. **This is a delivery-surface contract change.** The external
   `ai-dmx-light-render` consumer has not yet migrated to the v3.1 surface, so
   this change is folded into the still-pending
   [`contract-change-v3.1.md`](contract-change-v3.1.md) as a new section rather
   than opening a second handoff note — the consumer migrates once, not twice
   (D2).

## Ordering, and why

The stage cannot reach the model until phase 4 publishes it, and the MCP
server and UI both read the published file — so the sequence is
**produce → publish → expose → surface in the debugger → retire the
experiment**.

| Item | Produces | Needs |
| --- | --- | --- |
| 1 `detect-arrangement-state` stage | `artifacts/arrangement_state.json` | reads the already-published `loudness.json`, so it runs **after** `build-ui-data` (D4) |
| 2 `publish-arrangement-state` stage | the top-level file + `field_sources` + `§9` of the contract note | 1 |
| 3 MCP exposure | overview `arrangement` block, `get_detail` block list | 2 |
| 4 UI lane promotion | the "Arrangement State" lane reads the top-level file, badge removed | 2 |
| 5 retire the experiment + docs sweep | `experiments/arrangement_state/` deleted, entry archived | 1–4 |

Items 3 and 4 are independent of each other and may be reordered. Item 5 is
last: the experiment code stays runnable until the production path is proven.

**Where the two new stages sit in the run.** `build-ui-data` (7.2) is what
writes the top-level `loudness.json` the detector reads, so both new stages run
*after* it:

```
… → build-gestures → generate-section-hints → build-ui-data
  → detect-arrangement-state (3.2) → publish-arrangement-state (7.3)
  → build-human-hints-alignment
```

Execution order has never followed id order — `segment-sections` (3.1) already
runs before `extract-drum-events` (2.5) and `derive-energy-layer` (4.1). The id
labels the documentation phase, not the position. Reasoning and the rejected
alternatives: **D4**.

### Publishing stays in `ui_data.py`, even though a new stage calls it

`build-ui-data` (7.2) assembles most top-level files, but not all: stage 6.2
(`generate-section-hints`) already writes `hints.json` itself, with its own
`validate_field_sources` call. Item 2 follows that existing split — the
publisher `publish_arrangement_state` lives in
[`ui_data.py`](../src/analyzer/stages/ui_data.py) beside `_publish_genre` /
`_publish_loudness` and goes through the same `_fuse` selection even though one
producer (`arrangement_state`) answers every field today, and the new
`publish-arrangement-state` stage is what calls it. Keeping the function in
`ui_data.py` is what lets a CLAP `feel` field slot in later as a second `_fuse`
candidate without touching its caller (the v3.1 plan's own D4 pattern).

---

## How this plan is worked

**Validate each item, then push it on its own.** Work one plan item at a time.
When an item is complete, run its tests the way this project requires — in the
container: `docker compose run --rm test` for the analyzer,
`docker compose run --rm ui npm run test && docker compose run --rm ui npm run build`
for `ui/`, and the MCP suites per
[`reference/mcp-regression.md`](reference/mcp-regression.md) — and only if they
pass, tick its checkboxes, then commit and push that item by itself before
starting the next. Name the commit after the plan item as this plan writes it —
for example ``2. Publish top-level arrangement_state.json``. One commit per
item, never a single batch commit at the end: a later failure then cannot
strand the validated work in front of it, and the history reads as this plan's
own sequence.

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
| Items | 5 (1 stage, 1 publish, 1 MCP, 1 UI, 1 closure) |
| Items with a Visual QA block | 1 (item 4) |
| Analyzer tests | `docker compose run --rm test` on every item that touches `src/` |
| MCP regression | `smoke-test` on item 3; `full-regression` on items 3 and 5 |
| UI tests | `npm run test` + `npm run build` on item 4 |
| Done | 1 (item 1) |
| Contract-change note | [`contract-change-v3.1.md`](contract-change-v3.1.md) — extended by item 2 (new `§9`) |
| New pipeline stages | 2 — `detect-arrangement-state` (3.2), `publish-arrangement-state` (7.3) |
| Blocking decisions (`D`) | none open — D1–D4 all resolved in this document |

---

## Standing rules for every item

- **Docker only.** Nothing runs on the host. Analyzer tests
  `docker compose run --rm test`; pipeline
  `docker compose run --rm app ./analyze --song "/data/songs/_test_song.mp3"`;
  single stage `--stage detect-arrangement-state`.
- **No silent fallbacks.** A block with no measured `margin_db` (the leading
  span before the first change) carries `confidence: null` and `margin_db:
  null` — never a filled-in default. If `loudness.json` is missing the stage
  fails explicitly; it does not fall back to reading the artifact.
- **`src/` never imports from `experiments/`.** Item 1 *ports* `detector.py`
  into `src/analyzer/stages/`; it does not import it. The experiment stays
  independent until item 5 deletes it.
- **Determinism.** Same `loudness.json` + engine version ⇒ byte-identical
  `arrangement_state.json`. The detector is pure arithmetic with no randomness
  and no I/O beyond reading the one published file.
- **Fusion reads generated artifacts only.** `publish_arrangement_state` reads
  `artifacts/arrangement_state.json` and nothing under `reference/` — the
  existing fusion test that enforces this must cover the new publisher.
- **Delete the docs with their subject.** Every item that invalidates a line in
  `docs/`, `CLAUDE.md`, or a lane comment fixes it in its own commit. Item 5 is
  the sweep for leftovers, not a place to defer to.
- **`mcp/` never reads `artifacts/` or `reference/`.** The server reads the
  top-level `arrangement_state.json` only, and treats it as optional (a song
  analysed before this release will not have it) — an absent file degrades the
  response, it is not an error.

---

## Item 1 — `detect-arrangement-state` stage (phase 3)

- [x] **Port the detector.** New `src/analyzer/stages/arrangement_state.py`,
  carrying `detect()` and `blocks()` from
  [`experiments/arrangement_state/detector.py`](../experiments/arrangement_state/detector.py)
  and their module constants (`WINDOW_S`, `PRESENT_DB_BELOW_P98`,
  `PRESENT_FRACTION`, `HOLD_S`, `HOLD_AGREEMENT`). **Drop `detect_smoothed()`** —
  it is a documented ablation, not production code; its finding stays recorded in
  the experiment README until item 5 archives it.
- [x] **Read the published series, not the artifact.** The stage reads
  `data/analysis/{song}/loudness.json` (the 20 ms published file), proving a
  phase-3 stage can produce this without touching audio. Use `SongPaths`
  (`paths.loudness_output_path`), not the experiment's bare `paths` helper.
  The stage's own docstring carries its measured numbers, per repo convention.
- [x] **Emit the artifact.** Write `artifacts/arrangement_state.json`:
  `schema_version`, `generated_from` (naming `loudness.json` as the input and
  the engine string), and `blocks` from `blocks()` — each block
  `{start_s, end_s, playing, entered, left, margin_db}`. This is the
  intermediate; item 2 builds the fused top-level view from it.
- [x] **Register the stage.** In [`src/analyzer/pipeline.py`](../src/analyzer/pipeline.py):
  add `"detect-arrangement-state": "3.2"` to `STAGE_PIPELINE_IDS`; import
  `detect_arrangement_state`; add the `run_phase_1` call **immediately after
  `build-ui-data`** — that stage is what writes the top-level `loudness.json`
  this one reads, so any earlier position fails on the first analysis of a song
  (D4).
- [x] **Single-stage branch.** `--stage detect-arrangement-state` needs the
  top-level `loudness.json`, which `_required_artifact_payload` cannot express
  (it resolves under `artifacts/`). Add a sibling helper
  `_required_output_payload(paths, stage_name, path)` that raises the same
  explicit `AnalysisError`, naming `loudness.json` and telling the caller to run
  `build-ui-data` first. No fallback to `artifacts/essentia/rms_loudness.json`.
- [x] **`docs/reference/cli.md`** — insert `detect-arrangement-state | 3.2`
  after the `segment-sections` row (the table is id-ordered), and add one
  sentence under the table: the table is ordered by id, and run order differs —
  `detect-arrangement-state` runs after `build-ui-data`, which publishes the
  `loudness.json` it reads.
- [x] **Add the producer.** `Producer.ARRANGEMENT_STATE = "arrangement_state"`
  in [`src/analyzer/models.py`](../src/analyzer/models.py), extending the closed
  vocabulary. Update the vocabulary list wherever it is restated in prose
  (`contract-change-v3.1.md §2`, `reference/artifacts.md`).

**Validation**

- [x] `docker compose run --rm test` green.
- [x] **New unit test `tests/test_arrangement_state.py`, on a synthetic
  `loudness.json`.** `data/analysis/**` is gitignored (only `reference/human/`
  is tracked), so there is no committed `_test_song` input a test can read —
  build the frames in-process in a `tempfile` song dir, the way
  `tests/test_loudness_publish.py` builds its RMS artifact. Pin the three
  behaviours that carry the result: a flip that does not hold for `HOLD_S`
  produces no block; a flip that does is reported at the **unsmoothed** edge,
  not the window centre; a flip on the `mix` channel alone produces no block.
- [x] **Pin the port against the experiment once, by hand, before item 5 deletes
  it.** Run the experiment and the stage on `_test_song` and confirm the stage
  reproduces these nine edges (experiment README, Measurement 2) to the frame:

  | edge (s) | change |
  | --- | --- |
  | 22.25 | `+drums` |
  | 25.00 | `+vocals -bass` |
  | 29.75 | `+bass -vocals` |
  | 36.50 | `+drums` |
  | 42.50 | `-bass` |
  | 43.25 | `+vocals` |
  | 44.50 | `+bass -vocals` |
  | 47.00 | `+vocals` |
  | 55.25 | `-vocals` |

  Record the observed edges in the item-1 commit message. This table is the only
  check the port has against the experiment's own numbers once
  `experiments/arrangement_state/` is gone.
- [x] `docker compose run --rm app ./analyze --song "/data/songs/_test_song.mp3"`
  runs end to end and the validation report is not regressed.

---

## Item 2 — `publish-arrangement-state` stage, top-level `arrangement_state.json`

- [ ] **`paths.py` accessor.** `arrangement_state_output_path` on `SongPaths`,
  beside `loudness_output_path`.
- [ ] **`publish_arrangement_state(paths)`** in
  [`src/analyzer/stages/ui_data.py`](../src/analyzer/stages/ui_data.py), beside
  `_publish_genre` / `_publish_loudness`. Public, not `_`-prefixed, because a
  second module calls it — it is **not** called from `build_ui_data`, which has
  already run by this point in the pipeline (D4). It reads
  `artifacts/arrangement_state.json` and writes:

  ```json
  {
    "schema_version": "3.0",
    "song_name": "...",
    "field_sources": {
      "start_s": "arrangement_state", "end_s": "arrangement_state",
      "playing": "arrangement_state", "entered": "arrangement_state",
      "left": "arrangement_state", "margin_db": "arrangement_state",
      "confidence": "arrangement_state"
    },
    "stems": ["bass", "drums", "harmonic", "vocals"],
    "blocks": [
      { "start_s": 0.0, "end_s": 22.25, "playing": ["bass","drums","harmonic","vocals"],
        "entered": [], "left": [], "margin_db": null, "confidence": null },
      { "start_s": 22.25, "end_s": 25.0, "playing": ["bass","drums","harmonic"],
        "entered": ["drums"], "left": [], "margin_db": 6.1, "confidence": 0.64 }
    ]
  }
  ```

- [ ] **Register `publish-arrangement-state` (7.3)** in
  [`pipeline.py`](../src/analyzer/pipeline.py), immediately after
  `detect-arrangement-state`, calling `publish_arrangement_state`. Its
  single-stage branch requires `artifacts/arrangement_state.json` through the
  existing `_required_artifact_payload`. Insert
  `publish-arrangement-state | 7.3` after the `build-ui-data` row of the
  `docs/reference/cli.md` stage table.
- [ ] **Confidence per D1** — `confidence = round(1 - exp(-margin_db / 6.0), 3)`
  when `margin_db` is a number, `null` when it is `null`. `stems` is a
  file-level aggregate (the stem vocabulary), provenance-exempt like
  `schema_version`.
- [ ] **Fuse, don't copy.** Build `field_sources` through `_fuse(...)` with one
  candidate producer per field, so a later CLAP `feel` field is a second
  candidate, not a rewrite. Run it through `validate_field_sources`.
- [ ] **Contract note — new `§9`** in
  [`contract-change-v3.1.md`](contract-change-v3.1.md): "New top-level file:
  `arrangement_state.json`". State the shape, that `confidence` measures dB
  headroom at the stem flip (not a tuned score), that a block with `margin_db:
  null` is the leading span and carries `confidence: null`, and that the file is
  **optional** — a song analysed before v3.2 will not have it, and the consumer
  must treat its absence as "no arrangement-state read", never an error. Update
  the "What changed, shortest form" list and the "Three new top-level files"
  line (now four).
- [ ] **`reference/artifacts.md`** — add the `arrangement_state.json` entry
  (every field, its type, its meaning) and its row in the "`field_sources` per
  file" table. Note the intended CLAP `feel` extension point.

**Validation**

- [ ] `docker compose run --rm test` green, including the fusion-never-reads-
  `reference/` test extended to the new publisher.
- [ ] New test in `tests/test_publish_views.py` (or a new
  `tests/test_arrangement_state_publish.py`): on a synthetic
  `artifacts/arrangement_state.json` written into a `tempfile` song dir — same
  construction as `tests/test_loudness_publish.py`, since no analysis data is
  committed — `publish_arrangement_state` emits every block, `confidence` is
  monotone in `margin_db`, and the leading block carries
  `margin_db: null` / `confidence: null`.
- [ ] Full pipeline run on `_test_song` writes
  `data/analysis/_test_song/arrangement_state.json` and it validates against the
  documented shape.

---

## Item 3 — MCP exposure

- [ ] **Load it optionally — `loaders.py` needs no change.** Do **not** add
  `arrangement_state.json` to `REQUIRED_TOP_LEVEL_FILES` in
  [`mcp/loaders.py`](../mcp/loaders.py): that list is a hard gate and every
  pre-v3.2 song would start erroring. Read the file through the existing
  `_maybe_load(song_dir, filename)` helper in
  [`mcp/serializers.py`](../mcp/serializers.py) — the one `genre.json` uses,
  which returns `None` on `FileNotFoundError`.
- [ ] **`get_song_overview`** — a new compact `arrangement` block in
  [`mcp/serializers.py`](../mcp/serializers.py): the block count, and one row
  per block with `start`, `end`, `playing`, `entered`, `left`, `confidence`.
  Carry the file's `field_sources` summary once (per the honesty rule — `source`
  is never dropped). Omit the block entirely when the file is absent. Keep it
  compact — this rides in context for the whole session.
- [ ] **`get_detail`** — for a resolved span, list the `arrangement_state`
  blocks that overlap it (structural, not dense — it is already block data, no
  decimation). Include it in the structural view returned even when the 5 s
  dense cap withholds frames.
- [ ] **Fixtures.** The MCP fixtures are hand-synthesized, not copied from a
  real run: add an `arrangement_state(song_name)` builder to
  [`mcp/tests/fixtures/build_fixtures.py`](../mcp/tests/fixtures/build_fixtures.py)
  beside `loudness` / `drum_events`, and write it **only in `build_full()`**.
  Leave `McpDegenerate - Fixture` and `McpPartial - Fixture` without the file —
  that absence is what exercises the optional-file path, and it is the fixture
  the last validation bullet below needs. Give the full fixture at least three
  blocks, one of them a leading block with `margin_db: null` /
  `confidence: null`, so the honest-`null` path is in a snapshot. Re-run the
  builder and commit the regenerated fixtures.
- [ ] **Snapshots + expectations.** Re-record the golden snapshots
  (`get_song_overview__*`, `get_detail__*`) in this commit with a one-line
  justification per changed file, per
  [`reference/mcp-regression.md`](reference/mcp-regression.md) §F1 — they are
  regenerated, not defended. Update `mcp/tests/test_overview.py`,
  `test_detail.py`, `test_exposure.py`, `test_server_tools.py` and
  `mcp/tests/run.py`'s expectations.
- [ ] **`mcp-definition.md`** — add `arrangement` to the `get_song_overview`
  returns list and the `get_detail` structural view; note the file is optional.
  Update the status banner's "eight top-level files" to nine.

**Validation**

- [ ] `docker compose run --rm --no-deps -T --entrypoint python mcp mcp/tests/run.py smoke-test` — no failures, no deferrals.
- [ ] `full-regression` per [`reference/mcp-regression.md`](reference/mcp-regression.md) green.
- [ ] A fixture song with **no** `arrangement_state.json` still returns a valid
  overview and detail (the block is simply absent).

---

## Item 4 — promote the "Arrangement State" UI lane

The lane already exists as an experiment lane
([`ui/src/timeline/laneState.ts`](../ui/src/timeline/laneState.ts) row
`arrangementState`). Promotion repoints it at the published file and drops the
flask badge — it stays a sparse lane, so this is not a Recipe B removal. Follow
[`reference/ui-development.md`](reference/ui-development.md) Recipe D rows plus:

- [ ] **`ui/src/data/paths.ts`** — repoint `artifactPaths.arrangementState` from
  `analysis(song, "reference", "proposals", "arrangement_state.json")` to the
  top-level `analysis(song, "arrangement_state.json")`. Update the comment (no
  longer "Written by experiments/…").
- [ ] **`ui/src/data/sparseArtifacts.ts`** — the parser now reads the published
  shape: `doc["blocks"]` with `start_s`/`end_s` (not the experiment's key
  names if they differ), `playing`, `entered`, `left`, `margin_db`,
  `confidence`. Keep it tolerant (never throw; missing optional → stated gap).
  Update the `asObject(...)` label string and the header-comment mention.
- [ ] **`ui/src/data/loaders.ts`** — `loadArrangementState` must still map 404 →
  empty (a pre-v3.2 song has no file), per invariant 1.
- [ ] **`tests/ui-visual/fixtures/build-fixtures.py`** — add
  `"arrangement_state.json"` to `NEEDED`. It is block data, so do **not** add it
  to `DENSE`. Regenerate the three fixture songs; their source songs must have
  been analysed with items 1-2 in place, or the file will simply be absent and
  the 200-check below fails. The lane has never had fixture data at all — the
  experiment's `reference/proposals/arrangement_state.json` is not in `NEEDED`
  either, which is why this bullet is new work rather than a repoint.
- [ ] **`ui/src/timeline/laneState.ts`** — remove `experiment: "arrangement_state"`
  from the `arrangementState` `LANE_DEFS` row (this removes the flask badge and
  the "not promoted" tooltip); rewrite `sub` to a production caption, e.g.
  `"arrangement_state · who is playing, per-stem RMS state changes"`. Do **not**
  change the lane `id`.
- [ ] **`ui/src/timeline/laneContent.ts`** — update `arrangementStateContent`'s
  `summary` string: drop `experiments/arrangement_state (no model)` framing,
  describe it as the published `arrangement_state.json`. Keep the
  `arrangementStateSparse` tint for single-stem blocks.
- [ ] **`ui/src/timeline/laneContent.test.ts`** — update the `describe` block for
  the new shape / summary text.
- [ ] **Docs** — Recipe A step 9's four doc touchpoints, in reverse: remove the
  lane from any "experiment lanes" enumeration in `ui-definition.md`; add it to
  the production-lane list.

### Visual QA — item 4

Executor contract, fixtures, viewport/DPR, readiness gate, fonts/animation
pinning: [`reference/ui-regression.md`](reference/ui-regression.md). Run
**every** check below and report each as pass/fail with the observed value.

- **Surface:** `http://localhost:9090`, primary fixture song loaded (`song-full`,
  the fully-populated fixture named in
  [`reference/ui-regression.md`](reference/ui-regression.md) §2 as the primary
  baseline), timeline
  scrolled to `t = 0`, the **Arrangement State** lane expanded.
- **Runtime assertions (fail the run on any):** no `console.error` /
  `console.warn`; no `pageerror` / unhandled rejection; the network request for
  `data/analysis/<fixture>/arrangement_state.json` returns **200** (not 404 —
  the fixture must carry the file); no other failed request for an expected
  resource.
- **Binary checks:**
  - The lane head shows label **"Arrangement State"** and **no flask badge**
    icon (the experiment badge element is absent from the lane head DOM).
  - The lane sub-caption text is the new production caption, not one containing
    the word "experiment".
  - The lane body renders **≥ 2** block rects for the primary fixture (observed
    count reported).
  - The lane's rightmost non-empty block ends within **4 px** of the timeline
    content's right edge at the current zoom (full-extent check — content
    reaches the same far edge as the ruler).
  - Hovering the first block after `t = 0` shows a tooltip whose text contains
    `arrangement_state` and does **not** contain
    `not promoted to the pipeline`.
- **Baseline diff:** diff the full-timeline screenshot against the committed
  baseline for this surface under `tests/`, pixel threshold per the guide. The
  lane-head region changes (badge removed, caption reworded) — update that
  baseline in this commit with the one-line justification
  "arrangement_state lane promoted: badge removed, caption reworded". Mask the
  waveform and RMS canvases as the guide already specifies.

**Validation**

- [ ] `docker compose run --rm ui npm run test` green.
- [ ] `docker compose run --rm ui npm run build` clean.
- [ ] `docker compose run --rm test` — analyzer baseline unchanged.
- [ ] `grep -rn "arrangement_state" ui/src` shows no remaining
  `reference/proposals` path and no `experiment:` wiring for the lane.
- [ ] Visual QA block above: every check passes; the updated baseline is in the
  commit.

---

## Item 5 — retire the experiment and sweep the docs

**Order matters inside this item: archive first, delete second.** The bullets
below are sequenced, not a set. `experiments/arrangement_state/README.md` holds
content that exists nowhere else, and deleting it before lifting that content
out destroys measured evidence permanently.

- [ ] **Archive the queue entry — and lift the README's findings into it.** Move
  the [`docs/experiments.md`](experiments.md) "Arrangement state" section to
  [`docs/archive/experiments_promoted.md`](archive/experiments_promoted.md),
  rewritten in the past
  tense, keeping its measured tables.

  Match the shape the file actually has. It holds promoted experiments only, so
  entries carry **no disposition label**: each is a `## <name>` section whose
  first paragraph opens with a bold **Promoted** sentence saying where the code
  went and what it deleted. Copy the two entries already there. This one opens:

  > **Promoted** in v3.2 plan items 1-2 → `src/analyzer/stages/arrangement_state.py`
  > (detection) and `publish_arrangement_state` in `ui_data.py` (the top-level
  > `arrangement_state.json`). Replaced nothing — the pipeline had no
  > arrangement-state stage. Unlike the other two entries there is **no
  > surviving `experiments/` README**: it was deleted in the same change, so
  > everything worth keeping is reproduced here.

  That last clause is why this bullet runs first. **Copy the README's "Negative
  results worth not rediscovering" list into the archived entry verbatim**
  ([`experiments/arrangement_state/README.md`](../experiments/arrangement_state/README.md),
  the `## Negative results worth not rediscovering` heading): smoothing is the
  failure mode; `margin_db` is a confidence, not a gate; the mix channel must
  never trigger a change; do not score a texture detector against drop labels.
  This list is **not** in the queue entry today — it exists only in the README
  that the next bullet deletes. Copy anything else in that README that the queue
  entry does not already carry, most importantly Measurement 1 (smoothing halves
  F1: 0.59 → 0.27, and displaces a hand-marked boundary by 6 s), which the CLAP
  entry cites.

  Note in the archived entry that texture hints on `Hideaway` / `Armin` /
  `Titanium` are still unmarked, so the corpus number stays uninformative, and
  point at the [`issues.md`](issues.md) entry the next-but-one bullet creates.
  Remove the section from `docs/experiments.md`.
- [ ] **Add the headline row** to the summary table at the top of
  [`experiments_promoted.md`](archive/experiments_promoted.md), in its existing
  `experiment | replaced | headline` shape:

  ```
  | Arrangement state | nothing — new stage | `_test_song` F1 **0.59** @0.5 s vs `sections.json` **0.00** |
  ```

  A reader who only reads that table must still see that this entry exists.
- [ ] **Delete `experiments/arrangement_state/`** in full — `detector.py`,
  `export.py`, `score.py`, `run.py`, `paths.py`, `__init__.py`, `out/`,
  `README.md`. **Only after the bullet above has landed the README's findings in
  the archive.** The commit message states where the content now lives:
  `src/analyzer/stages/arrangement_state.py` (detection), the top-level
  `arrangement_state.json` (delivery surface), and
  `docs/archive/experiments_promoted.md` (the measured record).
- [ ] **`docs/issues.md`** — add a pending issue: "Texture hints missing on
  three gold songs — `arrangement_state` corpus F1 measures the label absence,
  not the detector" with the success condition (texture blocks marked, corpus
  re-scored). Give it the counted table from `docs/experiments.md`
  "Loose ends" — 12 non-drop hints across the gold set, 10 of them inside the
  58-second synthetic `_test_song`.
- [ ] **`docs/experiments.md` "Loose ends"** — the ground-truth gap now has one
  home, and it is `issues.md`. Replace the "The gold set has almost no non-drop
  ground truth" subsection's body with a one-line pointer to that issue, keeping
  the sentence that says the gap still blocks the **CLAP character layer**
  entry, which is why the loose end does not disappear when this entry leaves
  the queue.
- [ ] **`docs/experiments.md` — the Vocal-phrase entry's `[OPEN]` status.** It
  already says `arrangement_state` is "promoted into the pipeline in v3.2 as the
  `detect-arrangement-state` stage" and hangs its whole decision path on that
  experiment's Measurement 1. Repoint that citation at the archived entry in
  `experiments_promoted.md` — the README it implicitly leans on is gone — and
  make the tense match reality (shipped, not pending). Do **not** change the
  decision the entry records.
- [ ] **`CLAUDE.md`** — add the phase-3 `detect-arrangement-state` stage to the
  "Current state" table (a new row: *"informative on `_test_song` (F1 0.59 vs
  0.00), unmeasured elsewhere; honest `null` confidence off the margin"*); update
  the `mcp/` row to "nine top-level files" and add `arrangement_state` to the
  list.
- [ ] **`CLAUDE.md` — the four-phases table.** Phase 3's "Reads" cell says
  *"phase 2 only, **never audio**"*. `detect-arrangement-state` reads
  `loudness.json`, a **phase-1** published series, so that cell becomes
  *"phases 1-2, **never audio**"*. The load-bearing half of the rule is "never
  audio" and it still holds — the stage touches no audio, no spectrogram and no
  model. Make this edit; do not treat the mismatch as a blocker.
- [ ] **`docs/analysis-definition.md`** — document the new stage: what it reads
  (`loudness.json`), what it asserts (who is playing, and where that changes),
  how it measures (`_test_song` F1 0.59 @0.5 s / 0.75 @1.0 s vs `sections.json`
  0.00; corpus at the label noise floor), and that `confidence` is dB headroom
  at the stem flip, not a trained score. Place it in phase 3 beside
  `segmentation.py`.
- [ ] **`docs/mcp-definition.md`** — confirm the status banner and file count
  match items 2–3 (fold in here if item 3 left anything).
- [ ] **`ui/src/timeline/laneState.ts` comment** — the block comment listing
  "experiment lanes still left" no longer includes `arrangementState`; verify
  item 4 removed it and fix here if not.

**Validation**

- [ ] `docker compose run --rm test` green.
- [ ] `docker compose run --rm ui npm run test && docker compose run --rm ui npm run build` clean.
- [ ] `full-regression` for `mcp/` green.
- [ ] `grep -rn "arrangement_state\|arrangementState" experiments` returns
  nothing.
- [ ] **Evidence survived the delete.** `grep -n "Negative results worth not
  rediscovering" docs/archive/experiments_promoted.md` matches, and the four
  findings
  under it are present. This check exists because the delete is irreversible and
  the list had exactly one copy before this item ran.
- [ ] `grep -rn "implementation-plan-v3.2" docs/ CLAUDE.md` returns nothing
  outside the plan file itself — no doc may link a plan that is deleted when the
  release closes.
- [ ] The ground-truth gap appears in `docs/issues.md` and is *pointed at*, not
  restated, from `docs/experiments.md` "Loose ends".
- [ ] `docker compose run --rm app ./analyze --song "/data/songs/_test_song.mp3"`
  end to end; `arrangement_state.json` present and valid; validation report not
  regressed.

---

## Decisions

### D1 — how `confidence` is derived from `margin_db` — resolved as: bounded exponential

`margin_db` is the smallest dB headroom among the stems that flipped at a block
boundary — a measured distance from the decision boundary, not a score. The
operator asked for an "honest `margin_db`-derived confidence", `null` where
there is no margin.

**Resolved:** `confidence = round(1 - exp(-margin_db / 6.0), 3)`, and `null`
when `margin_db` is `null` (the leading block, which has no flip). 6 dB is
roughly one clearly-audible step, so a flip with 6 dB of headroom lands at
≈ 0.63 and a marginal 1–2 dB flip stays low. This is a monotone report of the
measured headroom, not a tuned filter — the experiment's `margin-sweep`
measurement already showed `margin_db` fails as a precision gate, so the plan
does not gate on it, only reports it. The raw `margin_db` stays on every row so
a consumer can apply its own threshold.

*Not blocking* — any monotone squashing is defensible; this one is recorded so
the implementer does not stop to invent one.

### D2 — version label and which handoff note — resolved as: v3.2 plan, v3.1 note extended

v3.1 formally closed in git history (the implementation plan was deleted at
commit `2af08b8`), so this is a new plan: `implementation-plan-v3.2.md`. But
`contract-change-v3.1.md` is still pending — the `ai-dmx-light-render` consumer
has not migrated. Opening a separate `contract-change-v3.2.md` would force that
consumer through two migrations for one not-yet-consumed surface.

**Resolved:** extend `contract-change-v3.1.md` in place with `§9`. When the
handoff finally lands, the note covers the whole undelivered surface (v3.1 +
this file) and is deleted in one go. If the operator prefers a clean v3.2 note,
splitting `§9` out later is a five-minute move.

*Not blocking.*

### D3 — overview placement: separate `arrangement` block vs. folding into `sections` — resolved as: separate block

`sections.json` rows are 8-bar allin1 arrangement labels (`verse`, `chorus`).
`arrangement_state` blocks are sub-section stem-state spans from a different
producer at a finer grain — often several per section, sometimes shorter than a
bar. Folding them into the sections block would blur two different claims and
two different confidences.

**Resolved:** a dedicated `arrangement` block in `get_song_overview`, parallel
to `sections` and `gestures`. This also matches the reach-test decision (its own
top-level file), and leaves room for the CLAP `feel` field to appear in the
same block later.

*Not blocking.*

### D5 — item-1 implementation notes (non-blocking, resolved in place)

- **Artifact `schema_version`** is `"3.0"` (`models.SCHEMA_VERSION`), matching
  every other generated file. `generated_from` is
  `{engine, reads: "loudness.json", window_s, present_db_below_p98,
  present_fraction, hold_s, hold_agreement}`.
- **`_required_output_payload(paths, stage_name, path)`** is written generic over
  the top-level filename (`path.name`), not hard-coded to `loudness.json`, so a
  future top-level-reading stage reuses it. Its `AnalysisError` names the file
  and says "Run 'build-ui-data' first".
- **Two existing tests updated** (in scope — adding a producer + a stage):
  `tests/test_field_sources_convention.py` closed-vocabulary set gains
  `arrangement_state`; `tests/test_console_markers.py`
  `test_run_phase_1_never_substitutes_moises_reference_when_it_exists` patches
  `analyzer.pipeline.detect_arrangement_state` alongside the other stage patches.
- **Port verified byte-identical** to `experiments/arrangement_state` on
  `_test_song`: all 17 detected edges (18 blocks) reproduce exactly, including
  the plan's nine-edge table. `detect_smoothed()` and the experiment's bare
  `paths` helper were dropped; `_windows`/`detect` now take `SongPaths`.

### D4 — where the two new stages run — resolved as: both after `build-ui-data`, publish in its own stage

The detector reads the **published** `loudness.json`, and that file is written by
`_publish_loudness` *inside* `build-ui-data` (7.2). So this plan's original
placement — `detect-arrangement-state` after `segment-sections` and before
`build-ui-data` — cannot work on the first analysis of a song: `loudness.json`
does not exist yet, and the stage's own no-fallback rule makes that a hard
failure, not a skip. Symmetrically the publisher cannot be a call inside
`build_ui_data`, because by the time the artifact exists that stage has already
finished.

**Resolved: two stages, both after `build-ui-data`.**
`detect-arrangement-state` (3.2) writes `artifacts/arrangement_state.json`, then
`publish-arrangement-state` (7.3) writes the top-level file through
`ui_data.publish_arrangement_state`. Stage 6.2 already publishes its own
top-level file (`hints.json`), so publishing outside `build-ui-data` is an
existing pattern rather than a new one, and run order has never matched id
order.

Rejected:

- **Read `artifacts/essentia/rms_loudness.json` and keep the early position.**
  That is a different input series — the artifact holds the 10 ms pre-decimation
  frames — so every measured number behind the promotion would have to be
  re-measured first, and the stage would stop demonstrating the thing the
  experiment set out to demonstrate.
- **Re-decimate the artifact inside the stage** with `_decimate_loudness_pairs`.
  Same series, but two code paths would then have to stay byte-identical
  forever, for no gain.
- **Hoist `_publish_loudness` into its own earlier stage.** Refactors shipped,
  green publishing code to accommodate a new consumer. The two-stage answer
  touches nothing that already works.
