# Implementation plan — v3.6

**Status: not started.** Turns
[`product-refinement-v3.6.md`](product-refinement-v3.6.md) (the refinement doc
in the rest of this plan) into an ordered worklist for a Sonnet implementer in
batch mode. The refinement doc holds the evidence and decisions. This plan says
what each item builds, how it is checked, and what must not be undone.

**v3.6 answers:** per section, how fast and in what rhythm the music moves, and
how much energy and tension it carries. It publishes that answer in a short
top-level schema the MCP client can read without guessing.

## Item order

| # | Item | Refinement item | Kind | Depends on |
| --- | --- | --- | --- | --- |
| 0 | Pre-flight | — | checks only, no commit | — |
| 1 | Re-publish stale hints | Bug | test + data | — |
| 2 | WhisperX VAD as its own service | 1 | compose + new service + `src/` + `ui/` | — |
| 3 | `truth_common` scorer | 2 | `experiments/` | 1 |
| 4 | Segment seeds + segment editor | 6, 7 (editor) | `experiments/` + `ui/` | 2 |
| 5 | Energy / tension / rhythm producers | 6 | `experiments/` + lanes | 3, 4 |
| 6 | Verdict per open experiment | 3 | `experiments/` + docs | 3, 4, 5 |
| 7 | Delete what nothing reads | 4 | data + `ui/` + docs | 6 |
| 8 | Trim top-level publishers | 5 | `src/` + `ui/` + contract | 7 |
| 9 | MCP: no backwards compatibility, beats in `get_detail` | 5 | `mcp/` + contract | 8 |
| 10 | Publish energy / tension / rhythm | 6 | `src/` + `mcp/` + contract | 5, 6, 9 |
| 11 | Seed the whole corpus | 7 | data | 10 |
| 12 | Close-out | — | docs | 1–11 |

---

## How this plan is worked

**Validate each item, then commit it on its own.** One item at a time. When it
is complete, run its **Checks** in the container: `docker compose run --rm test`
(analyzer), `docker compose run --rm ui npm run test` and
`docker compose run --rm ui npm run build` (`ui/`), the visual suite
([`reference/ui-regression.md`](reference/ui-regression.md) §6), the MCP suites
(`docker compose run --rm --no-deps -T --entrypoint python mcp mcp/tests/run.py smoke-test`
/ `full-regression`). Only if they pass, tick the item's boxes and commit that
item alone, named as this plan writes it, e.g. ``2. WhisperX VAD as its own service``.
One commit per item, never a batch at the end. **Never push**: commits stay
local. Generated `data/analysis/*/**` outside `reference/` is gitignored, so data
runs are checked, not committed.

**Use the recommendation; only a genuinely blocking decision stops an item.**
Resolve a mid-item question by adopting the best recommendation, and record it
here as a resolved `D` item. Only where any assumption would make the work wrong
or wasted: write an **unresolved** `D` item, skip the items that depend on it,
and continue with the rest.

**Long runs** (`--all-songs`, the `whisperx` service over the corpus): start
them with `run_in_background` and wait for the completion notice. Never poll
with `sleep`/`pgrep` loops.

**A failure found after an item is committed:** an analysis defect goes to
`docs/issues.md`; a `ui/` defect to `docs/web-ui/ui-issues.md` (create it if
absent); a defect needing a design decision becomes a `BUG` in the refinement
doc, annotated "Addressed by item N". Never fix across item boundaries in one
commit.

---

## Status

| | |
| --- | --- |
| Done | 3 of 12 |
| Visual QA items | 2, 4, 5, 7, 8 |
| MCP full-regression | items 9, 10, 11, 12 (smoke-test on every item) |
| Contract changes (`docs/reference/downstream-contract.md`, written as current state in the item that makes the change) | 2, 8, 9, 10 |
| New services | `whisperx` (item 2) |
| New experiments | `truth_common`, `segment_seeds`, `rhythm_drum_ioi`, `rhythm_stem_autocorr`, `rhythm_vocal_onsets`, `energy_level`, `tension_shape` |
| Promotion approval | producers kept by item 6 are **pre-approved** for `src/` (operator, 2026-09-14: "unless something fails too far, just add it as a layer") |
| Pre-existing failures | analyzer tests, ui test+build, MCP smoke-test: all green on HEAD (7a58785). Visual suite: 39/44 specs failed pre-existing — screenshot-baseline drift in this environment (e.g. `timeline-zoom-max` expects 1280×1142, environment renders 1280×1304 — a systemic font/viewport rendering difference, not a code defect). Item 2 incidentally fixed two non-screenshot contributors (stale `human_hints.json`/`block_energy.json` fixture drift, and the `segments.json` 404 gap — see D2.2), dropping this to 23/44 failing, all pure screenshot-baseline drift now. Treat any per-item visual QA as DOM/data assertions; screenshot re-capture is skipped for the reason given in each item's Visual QA section — a human with a matching rendering environment should run `--update-snapshots` once and review the diff before trusting pixel baselines again. |
| Decisions | D2.1 (resolved), D2.2 (resolved), D10.1 (resolved) |

---

## 0. Pre-flight

- [x] Commit `docs/product-refinement-v3.6.md` and `docs/implementation-plan-v3.6.md` alone as ``0. v3.6 refinement and plan``, so no item commit sweeps them in.
- [x] Run every suite named in "How this plan is worked" on HEAD. List each failing test by name in Status → "Pre-existing failures". Later items are not blamed for these.
- [x] Expected: `tests/ui-visual/specs/experiment-badge.spec.ts` fails, because `BADGED` still lists the retired `reactiveBands` and `gridPhrase`. Item 2 fixes it.

---

## 1. Re-publish stale hints

Refinement doc → Bugs. `hints.json` predates the 09-14 re-marks. Publishing
already carries `lighting_hint`.

- [x] `tests/test_hints.py`: a hint in `reference/human/human_hints.json` with a non-empty `lighting_hint` appears in `hints.json` with `source: "human"` and the same `lighting_hint`.
- [x] For `Armin - Revolution`, `Cinderella - Ella Lee`, `Hideaway - Kiesza`, `In da name of love - Anita and Ray`, `Queen of Kings - Alessandra`, `Titanium - David Guetta ft Sia`, `What a Feeling - Courtney Storm`, `_test_song`, `ayuni`: run `./analyze --song "/data/songs/<song>.mp3" --stage <s>` for `generate-section-hints`, then `build-ui-data`, then `build-human-hints-alignment`.

**Checks**
- [x] `docker compose run --rm test` green.
- [x] Per song: `source == "human"` rows in `hints.json` == entries in `human_hints.json`. Expected: Armin 19, Cinderella 30, Hideaway 5, In da name of love 11, Queen of Kings 16, Titanium 15, What a Feeling 2, `_test_song` 13, ayuni 18. All 9 matched exactly.

**Note:** `tests/ui-visual/fixtures/analysis/**` shows unrelated pre-existing drift against `build-fixtures.py`'s output (last regenerated before this plan started, source songs since re-analyzed by other work). Left uncommitted/untouched — out of scope for this item; items 2/4/5 re-run `build-fixtures.py` anyway.

---

## 2. WhisperX VAD as its own service

Refinement item 1. Guard: the `app` image never gains torch 2.8 or a Docker
socket, and a missing artifact never becomes `null`.

- [x] New top-level `whisperx_vad/` (like `mcp/`; not named `whisperx`, which collides with the pip package): `Dockerfile` carried from `experiments/whisperx_vad/Dockerfile` with unchanged pins and checkpoint; the compute code from `experiments/whisperx_vad/{model,export,run}.py`; entry `python -m whisperx_vad --song <path>` / `--all-songs`.
- [x] `docker-compose.yml` service `whisperx`: profile `ondemand`, build context `.`, dockerfile `whisperx_vad/Dockerfile`, image `ai-light-song-v2-whisperx:dev`, the same three volumes as `app`, no `gpus`.
- [x] Output `data/analysis/{song}/artifacts/whisperx-vad/whisperx_vad.json`: today's proposal schema minus `generated_from.generated_at` and `generated_from.experiment` (determinism).
- [x] `src/analyzer/stages/ui_data.py::_whisperx_vocal_phrase` reads that path. When the file is absent it raises, and the message contains `docker compose run --rm whisperx --song`. The `None` branch is deleted.
- [x] Delete `experiments/whisperx_vad/` except `README.md` and `out/`. Delete every `reference/proposals/whisperx_vad.json` once that song's artifact exists.
- [x] `ui/src/data/paths.ts` `whisperxVad` → `artifacts/whisperx-vad/whisperx_vad.json`. `laneState.ts`: remove `experiment` from the `whisperxVad` row and `experiment · ` from its `sub`. `laneContent.ts`: drop the `experiments/whisperx_vad — ` summary prefix. Update the tests.
- [x] `tests/ui-visual/fixtures/build-fixtures.py` copies `Armin - Revolution`'s `artifacts/whisperx-vad/whisperx_vad.json` into `RegFull` (and so `RegPartial`). Re-curate the hand-curated fixture files the script's header names.
- [x] `experiment-badge.spec.ts`: `BADGED` = exactly the lanes that carry `experiment` in `laneState.ts` after this item; remove `reactiveBands` and `gridPhrase`; add `whisperxVad` to `NOT_BADGED`. Where a `BADGED` lane needs a proposal file to render, `build-fixtures.py` copies it from `Armin - Revolution`. **Note:** `reactiveBands`/`gridPhrase` were already gone from `laneState.ts` before this item (stale plan text); the actual `BADGED` gap was three lanes missing from the list entirely (`vocalVoiceness`, `svdTagger`, `voiceMultiplicity`) — added, and their proposal files added to `build-fixtures.py`'s `NEEDED` list so they render.
- [x] Run: `docker compose build whisperx`, then `docker compose run --rm whisperx --all-songs`, then `build-ui-data` for all 23 songs. `--stage` doesn't accept `--all-songs` together, so looped `--song` over `data/songs/*.mp3` for both `build-ui-data` and `publish-arrangement-state` (the stage that actually reads the whisperx artifact — see D2.1).
- [x] Docs: `docs/reference/docker.md` (service row, commands, "run `whisperx` before `./analyze`"); `docs/reference/cli.md` (run order); `CLAUDE.md` "Running things" and the `vocals` row; `docs/mcp-definition.md` and `downstream-contract.md` (`vocals_phrase` is never `null`, and the out-of-band wording is removed); `docs/archive/experiments_promoted.md` WhisperX entry ("Not part of `./analyze`" paragraph → its own service before `./analyze`); `docs/reference/ui-regression.md` §5.5 flask list = `BADGED`.

**Checks**
- [x] `whisperx --song "/data/songs/_test_song.mp3"` run twice → `cmp` of the two outputs reports identical.
- [x] `ls data/analysis/*/reference/proposals/whisperx_vad.json` → no matches (all 23 deleted once each song's new artifact existed).
- [x] **D2.1 (resolved):** the plan named `--stage build-ui-data` for this check, but `_whisperx_vocal_phrase` is only called from `publish-arrangement-state` (`src/analyzer/pipeline.py`) — `build-ui-data` doesn't reach it. Checked against `--stage publish-arrangement-state` instead: with `_test_song`'s artifact moved aside it exits 3 with `missing .../whisperx_vad.json — run the whisperx service before ./analyze: docker compose run --rm whisperx --song /data/songs/_test_song.mp3`. Artifact restored.
- [x] `_test_song/arrangement_state.json` `vocals_phrase` span count == `vocal_phrase` count in its artifact (6 == 6).
- [x] analyzer tests (156), ui test + build (400), MCP smoke-test (11) green.

**D2.2 (resolved):** `RegFull - Fixture` was missing `reference/moises/segments.json` (exists for `Armin - Revolution`, just not in `build-fixtures.py`'s `NEEDED` list — added) and has no `reference/human/segments.json` at all (only 4 real songs do, item 4's concern). Both are documented app-level-optional (`ui/src/data/loaders.ts`'s `loadHumanSegments`/`loadMoisesSections` resolve a 404 to `[]` unconditionally), so `tests/ui-visual/helpers.ts`'s `assertNoRuntimeErrors` now tolerates a 404 on either path the same way it already tolerates the missing mp3 — a pre-existing gap since the Moises segmentation feature landed, unrelated to this item, fixed here because it blocked this item's own Visual QA gate.

**Visual QA** (`/?song=RegFull - Fixture`, suite per `ui-regression.md` §6)
- [x] Runtime: no `console.error`/`console.warn`, no `pageerror`, no failed `/data/analysis/` response.
- [x] `.tl-lane-head[data-lane="whisperxVad"] .tl-lane-head__flask` count = 0.
- [x] `.tl-lane-head[data-lane="whisperxVad"]` count = 1.
- [x] No request URL contains `reference/proposals/whisperx_vad.json` (`page.on("request")`).
- [x] `experiment-badge.spec.ts` passes.
- [ ] `song-full` baseline re-captured — **skipped.** This environment's Playwright screenshots are systematically offset from the checked-in baselines regardless of any code change (`timeline-zoom-max` renders 1280×1304 vs the baseline's 1280×1142 — a font/viewport rendering difference, confirmed pre-existing in item 0's pre-flight run, present for specs this item never touches). Re-capturing here would bake this environment's rendering into the repo baseline rather than reflect this item's actual DOM change. Every DOM/data/network assertion above is verified directly instead. A human with a matching rendering environment should run `--update-snapshots` and review the diff before trusting the pixel baselines again.

---

## 3. `truth_common` scorer

Refinement item 2. Guard: the scorer reads truth only from `reference/human/`,
plus Moises lyrics files where every row is `"0.99"`.

- [ ] `experiments/truth_common/`, one module per family: `structure`, `drop_stages`, `vocal_presence` (port of `voiceness_common.scorer`), `texture`, `energy_tension`, `rhythm`, `vocal_rhythm` (word onsets, text ignored). Corpus, metrics and circularity rules exactly as in the refinement doc's item 2 tables.
- [ ] Seeds: `energy_tension` and `rhythm` read `reference/human/segments.json` (operator) and `segments.seed.json` (seed). Every row scored against a seed carries `provisional: true`.
- [ ] Repoint every importer of `experiments/voiceness_common`, then delete that directory.
- [ ] One unit test per family on a hand-built fixture under `experiments/truth_common/tests/`.
- [ ] Output: each caller writes `out/score.txt` with one row per truth song, one corpus row, and the same columns within a family.

**Checks**
- [ ] `docker compose run --rm test python -m pytest experiments/truth_common -q` green.
- [ ] whisperX rescored through `truth_common` on `ayuni`: frame_acc 0.9881 ± 0.0005, false_vocal 0.0056 ± 0.0005.
- [ ] `grep -rn voiceness_common experiments src` → no matches.

---

## 4. Segment seeds + segment editor

Refinement item 6 ("Seeds first", `rhythm` field) and item 7's editor part.
Guard: seeds never go into `segments.json`, and no operator value is ever
overwritten.

- [ ] `experiments/segment_seeds/seed.py --song <name>` / `--all-songs`: the seed rule table in refinement item 6, exactly. Spans: `segments.json` spans where that file exists, else `sections.json` spans. Writes `reference/human/segments.seed.json` as a bare array of `{start, end, label, energy, tension, rhythm: {drums, bass, harmonic, vocals}}`. Output is deterministic; floats round to 3 places. This is the one experiment that writes under `reference/human/`, and only to `*.seed.json`.
- [ ] Run it for `ayuni`, `Cinderella - Ella Lee`, `_test_song`, `What a Feeling - Courtney Storm`.
- [ ] `ui/src/data/saveHumanSections.ts`: optional `rhythm` object. Keys ∈ `drums|bass|harmonic|vocals`, values ∈ `half|quarter|eighth|sixteenth|eighth_triplet|none`. An unmarked source is omitted.
- [ ] `ui/src/data/paths.ts` gains `humanSectionsSeed` (`reference/human/segments.seed.json`). Segment editor, per field: the `segments.json` value if present, else the seed value shown as a draft. Save writes the drafts into `segments.json`. With no `segments.json`, the `humanSections` lane renders the seed spans, every field a draft, and Save creates `segments.json`.
- [ ] Test ids: the `segment-editor` root gains `data-segment-start`. Controls `segment-energy`, `segment-tension`, `segment-rhythm-drums`, `segment-rhythm-bass`, `segment-rhythm-harmonic`, `segment-rhythm-vocals` each carry `data-seed-draft="true|false"`.
- [ ] `build-fixtures.py` `inject_segments` (synthetic, like `inject_block_energy`):
  - `RegFull` `segments.json` = `[{start:40,end:60,label:"Build",energy:4},{start:60,end:80,label:"Drop"}]`; `segments.seed.json` = `[{start:40,end:60,label:"Build",energy:3,tension:4,rhythm:{drums:"sixteenth",vocals:"none"}},{start:60,end:80,label:"Drop",energy:5,tension:2,rhythm:{drums:"quarter",bass:"eighth"}}]`.
  - `RegPartial`: no `segments.json`; the same seed file.
  - `_test_song`: seed `[]`.
- [ ] New spec `tests/ui-visual/specs/segment-seeds.spec.ts` = the Visual QA below. It snapshots and restores `RegFull`'s `segments.json`, like `promote-hint.spec.ts`.

**Checks**
- [ ] The 4 seed files exist with 16 + 20 + 8 + 9 = 53 rows. Every `energy`/`tension` ∈ 1–5, every `rhythm` value ∈ the vocabulary.
- [ ] `git diff --stat -- 'data/analysis/*/reference/human/segments.json'` → empty.
- [ ] analyzer tests, ui test + build green.

**Visual QA**
- [ ] Runtime assertions as item 2.
- [ ] `RegFull`: click `lane-events-humanSections`, then the first `.lane-events__card` → `segment-editor` `data-segment-start="40"`; `segment-energy` value `4`, draft `false`; `segment-tension` `4`, draft `true`; `segment-rhythm-drums` `sixteenth`, draft `true`; `segment-rhythm-bass` empty, draft `false`; `segment-rhythm-vocals` `none`, draft `true`.
- [ ] `RegFull`: Save on that segment, reload, reopen → `segment-tension` `4`, draft `false`.
- [ ] `RegPartial`: `lane-events-humanSections` panel has exactly 2 `.lane-events__card`; the second card's editor shows `segment-energy` `5`, draft `true`.
- [ ] `song-full` baseline re-captured, justification "humanSections lane: fixture gained segments".

---

## 5. Energy / tension / rhythm producers

Refinement item 6, candidate producers. One experiment per producer, one lane
each (`docs/reference/ui-development.md` Recipe A), the lane title identical to
the experiment name.

| experiment | writes | method |
| --- | --- | --- |
| `rhythm_drum_ioi` | `rhythm.drums` | (a) dominant inter-onset interval of `drum_events.json` ÷ beat period |
| `rhythm_stem_autocorr` | `rhythm.{drums,bass,harmonic,vocals}` | (b) sub-beat autocorrelation of per-stem 20 ms loudness |
| `rhythm_vocal_onsets` | `rhythm.vocals` + `onsets_per_beat` | (c) word onsets from `experiments/acestep_transcriber/whisper_baseline.py` over the vocal stem |
| `energy_level` | `energy` | segment loudness level + `arrangement_state` stems playing |
| `tension_shape` | `tension` | energy slope + gesture `build`/`tension` overlap + Phrase Periodicity regime |

- [ ] Each follows the queue convention (`docs/reference/cli.md`, `experiments/queue.toml` header): `run.py compute --song <name>` then `export --song <name>`, plus one `[[experiment]]` row (`image = "app"`), run with `docker compose run --rm app ./experiment --song "/data/songs/<song>.mp3" --only <name>`. `rhythm_vocal_onsets` needs the ACE-Step image: its row says so and is skipped by the runner, and it is run with `experiments/acestep_transcriber/run_in_container.sh`. Export writes `reference/proposals/<name>.json` rows over segment spans (`segments.json`, else `sections.json`): `{start, end, <field>, confidence}`. Confidence is computed per row (e.g. the margin between the top two candidates), never a constant.
- [ ] Each is run on the 4 segment songs and on `Armin - Revolution` (the fixture source). Each is scored through `truth_common`, results marked provisional.
- [ ] Existing `clap` (character), `texture_novelty` and `phrase_periodicity` are scored as energy/tension producers through adapters in `truth_common` that read their existing proposals. Those experiments are not reworked.
- [ ] `docs/experiments.md`: one entry per new experiment (status OPEN, method, provisional scores).
- [ ] Fixtures: `build-fixtures.py` copies the five proposals from `Armin - Revolution` into `RegFull`/`RegPartial`. `experiment-badge.spec.ts` `BADGED` gains the five lane ids.

**Checks**
- [ ] Each producer run twice on `_test_song` → identical output (`cmp`).
- [ ] analyzer tests, ui test + build green.

**Visual QA** (`RegFull`)
- [ ] Runtime assertions as item 2.
- [ ] For each of the five lane ids: `.tl-lane-head[data-lane="<id>"]` count 1, flask count 1, and the `lane-events-<id>` panel `.lane-events__card` count == number of rows in that fixture proposal.
- [ ] `experiment-badge.spec.ts` passes.
- [ ] `song-full` baseline re-captured, justification "five producer lanes added".

---

## 6. Verdict per open experiment

Refinement item 3: its table, keep-by-default rule and ACE-Step paragraph.

- [ ] Score every row of refinement item 3's table through `truth_common`. ACE-Step: `Queen of Kings` + `_test_song` (onset F1 ±50 ms / ±100 ms, onsets per second per phrase, phrase edges); `Cinderella - Ella Lee` (three-class presence).
- [ ] For each entry, write a `**Verdict (v3.6):**` line into its `### Status` in `docs/experiments.md`: keep / archive / merge, plus the deciding number per truth song.
- [ ] Archive = no better than the family's trivial baseline, or contradicted by truth on most truth songs. Write the TLDR into `docs/archive/experiments_discarded.md` and delete the entry. **No energy/tension/rhythm producer is archived while its truth is seed-only.**
- [ ] `drop_detection`: archive and retire the Drop Proposals lane if `gestures.py` matches or beats it on the drop-stage family. Otherwise give it a queue entry.

**Checks**
- [ ] Every `## ` experiment entry in `docs/experiments.md` contains `**Verdict (v3.6):**`.
- [ ] analyzer tests green.

---

## 7. Delete what nothing reads

Refinement item 4.

- [ ] Delete `reference/proposals/{clap_voiceness,reactive_bands,grid,gestures}.json` on every song. Delete `reference/proposals/arrangement_state.json` after `grep -rn "proposals.*arrangement_state" src ui/src experiments mcp` returns no match.
- [ ] Retire the lane of every experiment item 6 archived (Recipe B). Remove those proposals from the fixtures and `build-fixtures.py`, their ids from `BADGED`, and their rows from `experiments/queue.toml`.
- [ ] Docs: `docs/analysis-definition.md` (4 songs with `human/segments.json`), `docs/experiments.md` "Vocal ground truth inventory" and "Loose ends" rewritten to refinement item 2's corpus table.

**Checks**
- [ ] Every `data/analysis/*/reference/proposals/*.json` basename is referenced in `ui/src/data/paths.ts` or in an `experiments/*/` reader.
- [ ] Every `experiment:` value in `laneState.ts` names an entry still open in `docs/experiments.md`.
- [ ] ui test + build green.

**Visual QA** (`RegFull`)
- [ ] Runtime assertions as item 2.
- [ ] For each retired lane id: `[data-lane="<id>"]` count 0.
- [ ] `experiment-badge.spec.ts` passes.
- [ ] `song-full` baseline re-captured, justification naming each removed lane.

---

## 8. Trim top-level publishers

Refinement item 5, the field table. Guard: no top-level file carries
`generated_from`, a display string, or a field `mcp/serializers.py` does not
read. Beat `time`/`type`/`bar`/`beat`/`downbeat_confidence` stay.

- [ ] Apply refinement item 5's drop table in the stages that write each top-level file (`src/analyzer/paths.py` lists them). `hints.json` becomes a flat, human-only `hints[]` with `section_id, title, text, start_time, end_time, lighting_hint`, and `source` declared once in `field_sources`. `drum_events.json` gets a file-level `confidence: null` with a `confidence_reason`. Bump `schema_version` in every changed file. `field_sources` lists surviving fields only.
- [ ] If a dropped field exists in no artifact, the producing stage first writes it under `artifacts/<producer>/`.
- [ ] `ui/src/data/parsers.ts` and the loaders read `chord`, `chord_progression`, `label`, `description`, `section_name`, `summary`, `evidence_summary` and `provenance` from those artifact files, never from top level.
- [ ] Update `tests/test_field_sources_convention.py`, `tests/test_publish_views.py` and any failing publish test to the new shapes.
- [ ] Re-publish all 23 songs from `build-ui-data` onward, then run `build-fixtures.py` (re-curating the hand-curated files).
- [ ] Contract: `docs/reference/downstream-contract.md` file-by-file, `docs/reference/artifacts.md`. `CLAUDE.md` "Provenance" rule → "every artifact carries `generated_from`; top-level files carry `field_sources`". Delete `docs/issues.md` "host paths" entry.

**Checks**
- [ ] `grep -l generated_from data/analysis/*/*.json` → no matches.
- [ ] Each published top-level file's key set equals refinement item 5's surviving set (script in the scratchpad, not the repo).
- [ ] analyzer tests, ui test + build green.

**Visual QA**
- [ ] Before the change, record `lane-events-chords` card count on `RegFull`. After: same count.
- [ ] The full visual suite passes **with no `--update-snapshots`**: the debugger must look identical.
- [ ] Runtime assertions as item 2.

---

## 9. MCP: no backwards compatibility, beats in `get_detail`

Refinement item 5 (MCP part, beats decision).

- [ ] `mcp/loaders.py` `REQUIRED_TOP_LEVEL_FILES` = all 9. Delete `serializers._maybe_load`, the "song analysed before v3.2" block and every `.get("function_status", "unknown")`-style default.
- [ ] Serializers stop reading dropped fields. The genre `guidance` text goes once into the `get_song_overview` tool description. The hints block reads the flat `hints[]`. The drum block carries the file-level confidence, not per row.
- [ ] `get_detail` structural view: `beats` block with every beat in the span (`time, bar, beat, downbeat_confidence`), undecimated, present past the 5 s cap, plus `field_sources`.
- [ ] Rebuild `mcp/tests/fixtures/analysis/*` to the item-8 schema (`McpPartial` omits one required file). Regenerate `mcp/tests/__snapshots__/` with one justification line each.
- [ ] `docs/reference/mcp-regression.md`: add checks for the `beats` block (count == beats in the fixture span) and for all 9 files required. Update `docs/mcp-definition.md` and `downstream-contract.md`.
- [ ] Record `get_song_overview("Titanium - David Guetta ft Sia")` bytes (`mcp/tests/measure_tokens.py`) in Status. Update or delete `docs/issues.md` "prose budget" entry against the 6 KB target.

**Checks**
- [ ] MCP smoke-test and full-regression green.
- [ ] `grep -n "_maybe_load\|before v3.2" mcp/*.py` → no matches.

---

## 10. Publish energy / tension / rhythm

Refinement item 6: fields, precedence, `review_warning`.

- [ ] Port every producer item 6 kept into `src/analyzer/stages/section_clues.py` (a phase-3 stage, never reads audio), registered in `STAGE_PIPELINE_IDS` before `build-ui-data`. Delete the ported experiment code, keeping `README.md`, and its `experiments/queue.toml` row. Pre-approved (Status).
- [ ] `sections.json` rows gain `energy`, `energy_confidence`, `tension`, `tension_confidence`, and `rhythm: {<source>: {subdivision, onsets_per_beat, confidence}}`. Per field, per section: `segments.json` (source `human`) → highest-confidence ported producer that clears its floor → `segments.seed.json` (source `seed_unreviewed`, confidence `null`) → field absent. `field_sources` declares the file default, with a per-row override where a row's source differs.
- [ ] `mcp/serializers.py`: overview and detail section rows carry the fields. `get_song_overview` adds `review_warning` (text in refinement item 6) with the `section_id`s of every row carrying a `seed_unreviewed` field, and omits it when there are none.
- [ ] Tests: precedence unit test (`human` > producer > seed), `review_warning` serializer test, MCP fixtures carry one `seed_unreviewed` row. Snapshots regenerated.
- [ ] Docs: `downstream-contract.md`, `docs/mcp-definition.md`, `docs/analysis-definition.md` (stage + provisional numbers), `docs/reference/source-map.md`, `docs/reference/artifacts.md`.

**D10.1 (resolved):** if `rhythm_vocal_onsets` is kept, its compute moves into
the `whisperx` service as a second output,
`artifacts/whisperx-vad/vocal_onsets.json`, using the same model the experiment
used. `section_clues` reads that file and fails explicitly when it is absent.

**Checks**
- [ ] analyzer tests, MCP smoke-test + full-regression green.
- [ ] `_test_song/sections.json`: every row has `energy`, `tension`, `rhythm` or an explicit absence. Every `seed_unreviewed` field has `confidence: null`.

---

## 11. Seed the whole corpus

Refinement item 7.

- [ ] Before anything: save every song's `sections.json` `[start, end]` list to the scratchpad.
- [ ] `segment_seeds --all-songs` (23 songs; seed files hold no operator values, so re-running is safe).
- [ ] Full run in order: `docker compose run --rm whisperx --all-songs`, then `docker compose run --rm app ./analyze --all-songs --device cuda`.

**Checks**
- [ ] 23 `reference/human/segments.seed.json` files. On the 19 songs without `segments.json`, `sections.json` `[start, end]` lists equal the saved copy.
- [ ] No `segments.json` created: `ls data/analysis/*/reference/human/segments.json | wc -l` → 4.
- [ ] Inside the `mcp` container, for all 23 songs: every `section_id` with a `seed_unreviewed` field appears in `get_song_overview`'s `review_warning`.
- [ ] MCP full-regression green.

---

## 12. Close-out

- [ ] `CLAUDE.md` "Current state" rows: `vocals` channel, structure (new clue fields, provisional), MCP surface (9 required files, beats in `get_detail`, `review_warning`).
- [ ] `docs/issues.md`: delete every entry this plan solved.
- [ ] `docs/product-refinement-v3.6.md` Status → implemented; list the unreviewed seed rows as "all rows of `segments.seed.json`, 23 songs" for the next refinement.
- [ ] `grep -rn "reference/proposals/whisperx_vad" docs src ui mcp whisperx_vad` → no matches.

**Checks**
- [ ] Every suite green: analyzer, ui test + build, visual, MCP full-regression.
