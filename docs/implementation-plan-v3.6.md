# Implementation plan — v3.6

**Status: implemented, all 12 items.** Turns
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
| Done | 12 of 12 |
| Visual QA items | 2, 4, 5, 7, 8 |
| MCP full-regression | items 9, 10, 11, 12 (smoke-test on every item) |
| `get_song_overview("Titanium - David Guetta ft Sia")` byte size (item 9, `mcp/tests/measure_tokens.py`-style measurement) | 34,919 bytes — over the 6,144-byte target even after item 8's field trim; `arrangement` (44 blocks, 7,273 B) is now the largest block, ahead of `gestures` (7,107 B); see `docs/issues.md` "prose budget" |
| Contract changes (`docs/reference/downstream-contract.md`, written as current state in the item that makes the change) | 2, 8, 9, 10 |
| New services | `whisperx` (item 2) |
| New experiments | `truth_common`, `segment_seeds`, `rhythm_drum_ioi`, `rhythm_stem_autocorr`, `rhythm_vocal_onsets`, `energy_level`, `tension_shape` |
| Promotion approval | producers kept by item 6 are **pre-approved** for `src/` (operator, 2026-09-14: "unless something fails too far, just add it as a layer") |
| Pre-existing failures | analyzer tests, ui test+build, MCP smoke-test: all green on HEAD (7a58785). Visual suite: 39/44 specs failed pre-existing — screenshot-baseline drift in this environment (e.g. `timeline-zoom-max` expects 1280×1142, environment renders 1280×1304 — a systemic font/viewport rendering difference, not a code defect). Item 2 incidentally fixed two non-screenshot contributors (stale `human_hints.json`/`block_energy.json` fixture drift, and the `segments.json` 404 gap — see D2.2), dropping this to 23/44 failing, all pure screenshot-baseline drift now. Treat any per-item visual QA as DOM/data assertions; screenshot re-capture is skipped for the reason given in each item's Visual QA section — a human with a matching rendering environment should run `--update-snapshots` once and review the diff before trusting pixel baselines again. |
| Decisions | D2.1 (resolved), D2.2 (resolved), D4.1 (resolved), D5.1 (resolved), D8.1 (resolved), D10.1 (resolved), D10.2 (resolved), D11.1 (resolved) |

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

- [x] `experiments/truth_common/`, one module per family: `structure`, `drop_stages`, `vocal_presence` (port of `voiceness_common.scorer`), `texture`, `energy_tension`, `rhythm`, `vocal_rhythm` (word onsets, text ignored). Corpus, metrics and circularity rules exactly as in the refinement doc's item 2 tables.
- [x] Seeds: `energy_tension` and `rhythm` read `reference/human/segments.json` (operator) and `segments.seed.json` (seed). Every row scored against a seed carries `provisional: true`. `segments.seed.json` doesn't exist yet (item 4) — the loader returns no seed rows rather than guessing or crashing, tested explicitly.
- [x] Repoint every importer of `experiments/voiceness_common`, then delete that directory. Nine files repointed across `clap_voiceness`, `svd_tagger`, `vocal_voiceness`, `demucs_ablation`; `docs/experiments.md` and each experiment's `README.md` updated too.
- [x] One unit test per family on a hand-built fixture under `experiments/truth_common/tests/`.
- [x] Output: each caller writes `out/score.txt` with one row per truth song, one corpus row, and the same columns within a family.

**Checks**
- [x] `docker compose run --rm test python -m pytest experiments/truth_common -q` green — 31 passed.
- [x] whisperX rescored through `truth_common` on `ayuni`: frame_acc 0.9881261595547309, false_vocal 0.0055658627087198514 — both within tolerance.
- [x] `grep -rn voiceness_common experiments src` → no matches (three historical docstring mentions of the old module name reworded to satisfy this literally).

---

## 4. Segment seeds + segment editor

Refinement item 6 ("Seeds first", `rhythm` field) and item 7's editor part.
Guard: seeds never go into `segments.json`, and no operator value is ever
overwritten.

- [x] `experiments/segment_seeds/seed.py --song <name>` / `--all-songs`: the seed rule table in refinement item 6, exactly. Spans: `segments.json` spans where that file exists, else `sections.json` spans. Writes `reference/human/segments.seed.json` as a bare array of `{start, end, label, energy, tension, rhythm: {drums, bass, harmonic, vocals}}`. Output is deterministic; floats round to 3 places. This is the one experiment that writes under `reference/human/`, and only to `*.seed.json`.
- [x] Run it for `ayuni`, `Cinderella - Ella Lee`, `_test_song`, `What a Feeling - Courtney Storm`.
- [x] `ui/src/data/saveHumanSections.ts`: optional `rhythm` object. Keys ∈ `drums|bass|harmonic|vocals`, values ∈ `half|quarter|eighth|sixteenth|eighth_triplet|none`. An unmarked source is omitted.
- [x] `ui/src/data/paths.ts` gains `humanSectionsSeed` (`reference/human/segments.seed.json`). Segment editor, per field: the `segments.json` value if present, else the seed value shown as a draft. Save writes the drafts into `segments.json`. With no `segments.json`, the `humanSections` lane renders the seed spans, every field a draft, and Save creates `segments.json`.
- [x] Test ids: the `segment-editor` root gains `data-segment-start`. Controls `segment-energy`, `segment-tension`, `segment-rhythm-drums`, `segment-rhythm-bass`, `segment-rhythm-harmonic`, `segment-rhythm-vocals` each carry `data-seed-draft="true|false"`.
- [x] `build-fixtures.py` `inject_segments` (synthetic, like `inject_block_energy`):
  - `RegFull` `segments.json` = `[{start:40,end:60,label:"Build",energy:4},{start:60,end:80,label:"Drop"}]`; `segments.seed.json` = `[{start:40,end:60,label:"Build",energy:3,tension:4,rhythm:{drums:"sixteenth",vocals:"none"}},{start:60,end:80,label:"Drop",energy:5,tension:2,rhythm:{drums:"quarter",bass:"eighth"}}]`.
  - `RegPartial`: no `segments.json`; the same seed file.
  - `_test_song`: seed `[]`.
- [x] New spec `tests/ui-visual/specs/segment-seeds.spec.ts` = the Visual QA below. It snapshots and restores `RegFull`'s `segments.json`, like `promote-hint.spec.ts`.

**D4.1 (resolved):** the first implementation subagent hit a rate-limit mid-item after producing `features.py`/`paths.py` — those were read, independently verified against real on-disk artifact shapes, and reused rather than redone. A follow-up subagent finished `seed.py` + the UI/fixtures/spec work; its `tsc --noEmit` build failed on two `exactOptionalPropertyTypes` errors (`parseSegmentRhythm`'s return type was declared as `HumanSegment["rhythm"]`, which TS widens to include `undefined` for an optional property even under this flag) and a missing `SegmentRhythm` import — both fixed directly (return type narrowed to `SegmentRhythm | null`, import added). The new spec's third test also asserted zero runtime errors against `RegPartial - Fixture`, which is *deliberately* missing `artifacts/essentia/fft_bands*.json` (the degraded-banner fixture) — no prior spec had combined `assertNoRuntimeErrors` with that fixture, so this was a latent gap the new spec exposed rather than a regression; fixed by dropping the blanket error-list assertion from that one test (it isn't testing load-health, it's testing segment-editor fusion).

**Checks**
- [x] The 4 seed files exist with 16 + 20 + 8 + 9 = 53 rows. Every `energy`/`tension` ∈ 1–5, every `rhythm` value ∈ the vocabulary.
- [x] `git diff --stat -- 'data/analysis/*/reference/human/segments.json'` → empty.
- [x] analyzer tests (156), ui test (400) + build green. Determinism: `seed.py --song ayuni` run twice → `cmp` identical.

**Visual QA**
- [x] Runtime assertions as item 2 (except RegPartial's own test — see D4.1).
- [x] `RegFull`: click `lane-events-humanSections`, then the first `.lane-events__card` → `segment-editor` `data-segment-start="40"`; `segment-energy` value `4`, draft `false`; `segment-tension` `4`, draft `true`; `segment-rhythm-drums` `sixteenth`, draft `true`; `segment-rhythm-bass` empty, draft `false`; `segment-rhythm-vocals` `none`, draft `true`.
- [x] `RegFull`: Save on that segment, reload, reopen → `segment-tension` `4`, draft `false`.
- [x] `RegPartial`: `lane-events-humanSections` panel has exactly 2 `.lane-events__card`; the second card's editor shows `segment-energy` `5`, draft `true`.
- [ ] `song-full` baseline re-captured — skipped, same reason as item 2 (environment-wide screenshot drift, see Status). Full suite re-run: 21/44 failing now (down from 23/44 before this item), all pure screenshot-pixel drift; `segment-seeds.spec.ts`'s 3 non-screenshot tests pass.

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

- [x] Each follows the queue convention (`docs/reference/cli.md`, `experiments/queue.toml` header): `run.py compute --song <name>` then `export --song <name>`, plus one `[[experiment]]` row (`image = "app"`), run with `docker compose run --rm app ./experiment --song "/data/songs/<song>.mp3" --only <name>`. `rhythm_vocal_onsets` needs the ACE-Step image: its row says so and is skipped by the runner, and it is run with `experiments/acestep_transcriber/run_in_container.sh`. Export writes `reference/proposals/<name>.json` rows over segment spans (`segments.json`, else `sections.json`): `{start, end, <field>, confidence}`. Confidence is computed per row (e.g. the margin between the top two candidates), never a constant.
- [x] Each is run on the 4 segment songs and on `Armin - Revolution` (the fixture source). Each is scored through `truth_common`, results marked provisional.
- [x] Existing `clap` (character), `texture_novelty` and `phrase_periodicity` are scored as energy/tension producers through adapters in `truth_common` that read their existing proposals (`experiments/truth_common/adapters.py`). Those experiments are not reworked.
- [x] `docs/experiments.md`: one entry per new experiment (status OPEN, method, provisional scores — real numbers filled in after the orchestrator's run, see each entry's "Results evidence").
- [x] Fixtures: `build-fixtures.py` copies the five proposals from `Armin - Revolution` into `RegFull`/`RegPartial`. `experiment-badge.spec.ts` `BADGED` gains the five lane ids (10→15).

**D5.1 (resolved):** all five experiments' `export.py` wrote a wall-clock `generated_from.generated_at`, breaking the determinism check outright (two runs never `cmp` identical). Fixed by dropping the field from all five, matching item 2's own precedent for exactly this reason. Caught before commit by actually running the determinism check rather than trusting the subagent's static review.

**Checks**
- [x] Each producer run twice on `_test_song` → identical output (`cmp`) — confirmed for all 5 after the D5.1 fix.
- [x] analyzer tests (156, after updating `tests/test_run_queue.py`'s stale expected-queue-names list to the new 10-row `queue.toml`), ui test (413) + build green.

**Visual QA** (`RegFull`)
- [x] Runtime assertions as item 2.
- [x] For each of the five lane ids: `.tl-lane-head[data-lane="<id>"]` count 1, flask count 1, and the `lane-events-<id>` panel `.lane-events__card` count == number of rows in that fixture proposal (11/11/6/11/11, all matched).
- [x] `experiment-badge.spec.ts` passes.
- [ ] `song-full` baseline re-captured — skipped, same reason as items 2/4. Full suite: 21/44 failing (unchanged from item 4), all pure screenshot-pixel drift; item 5's own assertions (flask/count/card-count) all pass.

---

## 6. Verdict per open experiment

Refinement item 3: its table, keep-by-default rule and ACE-Step paragraph.

- [x] Score every row of refinement item 3's table through `truth_common`. ACE-Step: `Queen of Kings` + `_test_song` (onset F1 ±50 ms / ±100 ms, onsets per second per phrase, phrase edges); `Cinderella - Ella Lee` (three-class presence).
- [x] For each entry, write a `**Verdict (v3.6):**` line into its `### Status` in `docs/experiments.md`: keep / archive / merge, plus the deciding number per truth song.
- [x] Archive = no better than the family's trivial baseline, or contradicted by truth on most truth songs. Write the TLDR into `docs/archive/experiments_discarded.md` and delete the entry. **No energy/tension/rhythm producer is archived while its truth is seed-only.** Archived: `SongFormer` (dropped un-run, third pending cycle), `Texture Novelty` (killed on its own kill condition, best pooled F1 0.29 vs incumbent 0.27), `Structural vs Micro` (killed on its own kill condition, macro-F1 0.38 vs duration-only baseline 0.82). The five item-5 producers all kept (provisional), as required.
- [x] `drop_detection`: archive and retire the Drop Proposals lane if `gestures.py` matches or beats it on the drop-stage family. Otherwise give it a queue entry. `gestures.py` wins (4/7 @±1.0s at 4.5–10.3 events/min vs drop_detection's 4/7 @±0.5s at precision 0.048) — archived. Code/lane left in place; retirement is item 7's job. Also fixed a stale cross-reference in `docs/experiments.md`'s own "Loose ends" section (an open question this item settles).

**Checks**
- [x] Every `## ` experiment entry in `docs/experiments.md` contains `**Verdict (v3.6):**` — 14 experiment entries, 14 verdicts (5 meta sections excluded).
- [x] analyzer tests green (156).

---

## 7. Delete what nothing reads

Refinement item 4.

- [x] Delete `reference/proposals/{clap_voiceness,reactive_bands,grid,gestures}.json` on every song (23/4/4/4 songs respectively). Delete `reference/proposals/arrangement_state.json` (4 songs) after `grep -rn "proposals.*arrangement_state" src ui/src experiments mcp` returns no match — confirmed clean.
- [x] Retire the lane of every experiment item 6 archived (Recipe B): `textureNovelty`, `structuralVsMicro`, `dropProposals` (SongFormer had no lane, nothing to retire). All 11 Recipe B steps done per lane, plus two stale references outside the recipe's strict file list caught and fixed (`blockFields.ts`'s `LANE_LABELS`, dangling `loadDropProposals` test references) and two now-fully-obsolete visual specs deleted. Remove those proposals from the fixtures and `build-fixtures.py`, their ids from `BADGED`, and their rows from `experiments/queue.toml`.
- [x] Docs: `docs/analysis-definition.md` (4 songs with `human/segments.json` — `Cinderella - Ella Lee` confirmed as the 4th), `docs/experiments.md` "Vocal ground truth inventory" and "Loose ends" rewritten to refinement item 2's corpus table.

**Checks**
- [x] Every `data/analysis/*/reference/proposals/*.json` basename is referenced in `ui/src/data/paths.ts` or in an `experiments/*/` reader. `texture_novelty.json`/`structural_vs_micro.json` stay on disk (no longer UI-read, but still written by their own experiment and — `texture_novelty.json`/`phrase_periodicity.json` — read by `truth_common/adapters.py`'s item-5 adapters); `drop_impacts.json` stays, read by `experiments/{reactive_bands,grid_consensus,gestures}/score.py` (older, already-archived experiments kept as historical code, unrelated to this item).
- [x] Every `experiment:` value in `laneState.ts` names an entry still open in `docs/experiments.md` — verified all 11 remaining values.
- [x] ui test (399) + build green. analyzer tests (156, `test_run_queue.py` row counts updated for the 2 removed queue rows) green too.

**Visual QA** (`RegFull`)
- [x] Runtime assertions as item 2.
- [x] For each retired lane id: `[data-lane="<id>"]` count 0.
- [x] `experiment-badge.spec.ts` passes.
- [ ] `song-full` baseline re-captured — skipped, same reason as items 2/4/5. Full suite: 21/44 failing (same set, unchanged), all pure screenshot-pixel drift; `texture-novelty.spec.ts`/`structural-vs-micro.spec.ts` correctly gone (deleted with their lanes), no other regressions.

---

## 8. Trim top-level publishers

Refinement item 5, the field table. Guard: no top-level file carries
`generated_from`, a display string, or a field `mcp/serializers.py` does not
read. Beat `time`/`type`/`bar`/`beat`/`downbeat_confidence` stay.

- [x] Apply refinement item 5's drop table in the stages that write each top-level file (`src/analyzer/paths.py` lists them). `hints.json` becomes a flat, human-only `hints[]` with `section_id, title, text, start_time, end_time, lighting_hint`, and `source` declared once in `field_sources`. `drum_events.json` gets a file-level `confidence: null` with a `confidence_reason`. Bump `schema_version` in every changed file. `field_sources` lists surviving fields only.
- [x] If a dropped field exists in no artifact, the producing stage first writes it under `artifacts/<producer>/` — new `artifacts/section_segmentation/sections_display.json` (`section_id, label, description, chord_progression`).
- [x] `ui/src/data/parsers.ts` and the loaders read `chord`, `chord_progression`, `label`, `description`, `section_name`, `summary`, `evidence_summary` and `provenance` from those artifact files, never from top level. `sections.json`'s display trio reads from the new artifact via `mergeSectionDisplay` (join on `section_id`, fails loudly on a mismatch); the Gestures lane's `section_name`/`summary`/`evidence_summary`/`provenance` now read `artifacts/gestures/song_event_timeline.json` (the pre-trim artifact) instead of the trimmed top-level file. `beats.json`'s `chord` was already unused by the UI (the Chords lane reads `artifacts/layer_a_harmonic.json`, unrelated) — nothing to repoint. `genre.json`'s `top_predictions`/`guidance` are shown only through the generic raw-artifact inspector reading `artifacts/genre.json` directly — nothing to repoint.
- [x] Update `tests/test_field_sources_convention.py`, `tests/test_publish_views.py` and any failing publish test to the new shapes.
- [x] Re-publish all 23 songs from `build-ui-data` onward, then run `build-fixtures.py` (re-curating the hand-curated files). Republished via the 7 downstream stages the schema change actually touches (`build-gestures`, `generate-section-hints`, `build-ui-data`, `detect-arrangement-state`, `publish-arrangement-state`, `contest-section-function`, `build-human-hints-alignment`) rather than the full pipeline — phase-1/2 artifacts (stems, HPCP, drum transcription, etc.) are untouched by this item and re-running them would have been pure waste.
- [x] Contract: `docs/reference/downstream-contract.md` file-by-file, `docs/reference/artifacts.md`. `CLAUDE.md` "Provenance" rule → "every artifact carries `generated_from`; top-level files carry `field_sources`". Delete `docs/issues.md` "host paths" entry.

**D8.1 (resolved):** two implementation subagents hit the same infra rate-limit mid-item, in sequence — the second one left the Python/analyzer side complete and green (157 tests) but the UI side half-wired (`parsers.ts`/`types.ts` had the new merge machinery, but `loaders.ts` still called the deleted `parseSectionsTopLevel`, and `paths.ts`/fixture wiring were untouched). A third, narrowly-scoped subagent finished the UI wiring; validated independently afterward (see Checks) rather than trusting its self-report, which caught two more gaps the subagent didn't: `build-fixtures.py`'s `NEEDED` list was missing the two new/repointed artifact paths (`artifacts/section_segmentation/sections_display.json`, `artifacts/gestures/song_event_timeline.json`), which would have 404'd every RegFull/RegPartial load — fixed directly.

**Checks**
- [x] `grep -l generated_from data/analysis/*/*.json` → no matches, across all 23 songs.
- [x] Each published top-level file's key set equals refinement item 5's surviving set — verified directly against `Armin - Revolution` and `_test_song` for every changed file (`sections.json`, `beats.json`, `song_event_timeline.json`, `hints.json`, `genre.json`, `drum_events.json`, `loudness.json`); `contested_by` on `sections.json` rows is correctly optional (present only when a section is actually contested — 2/23 songs).
- [x] analyzer tests (157), ui test (400) + build green.

**Visual QA**
- [x] Before the change, recorded `lane-events-chords` card count on `RegFull`: **39**. After: **39** — unchanged, and no runtime errors.
- [x] The full visual suite: 21/44 failing, same set as items 5/7 (unchanged), all pure screenshot-pixel drift — no new failures from this item. `--update-snapshots` not run, per the environment-drift reasoning already recorded in Status; every DOM/data/network assertion this item can check directly all pass.
- [x] Runtime assertions as item 2.

---

## 9. MCP: no backwards compatibility, beats in `get_detail`

Refinement item 5 (MCP part, beats decision).

- [x] `mcp/loaders.py` `REQUIRED_TOP_LEVEL_FILES` = all 9. Delete `serializers._maybe_load`, the "song analysed before v3.2" block and every `.get("function_status", "unknown")`-style default.
- [x] Serializers stop reading dropped fields. The genre `guidance` text goes once into the `get_song_overview` tool description. The hints block reads the flat `hints[]`. The drum block carries the file-level confidence, not per row.
- [x] `get_detail` structural view: `beats` block with every beat in the span (`time, bar, beat, downbeat_confidence`), undecimated, present past the 5 s cap, plus `field_sources`.
- [x] Rebuild `mcp/tests/fixtures/analysis/*` to the item-8 schema (`McpPartial` omits one required file). Regenerate `mcp/tests/__snapshots__/` with one justification line each.
- [x] `docs/reference/mcp-regression.md`: add checks for the `beats` block (count == beats in the fixture span) and for all 9 files required. Update `docs/mcp-definition.md` and `downstream-contract.md`.
- [x] Record `get_song_overview("Titanium - David Guetta ft Sia")` bytes (`mcp/tests/measure_tokens.py`) in Status. Update or delete `docs/issues.md` "prose budget" entry against the 6 KB target.

**Checks**
- [x] MCP smoke-test and full-regression green.
- [x] `grep -n "_maybe_load\|before v3.2" mcp/*.py` → no matches.

---

## 10. Publish energy / tension / rhythm

Refinement item 6: fields, precedence, `review_warning`.

- [x] Port every producer item 6 kept into `src/analyzer/stages/section_clues.py` (a phase-3 stage, never reads audio), registered in `STAGE_PIPELINE_IDS` before `build-ui-data` (dict key `section-clues`, runs immediately after `contest-section-function` in the real execution order). Delete the ported experiment code per **D10.2 (resolved, below)**.
- [x] `sections.json` rows gain `energy`, `energy_confidence`, `tension`, `tension_confidence`, and `rhythm: {<source>: {subdivision, onsets_per_beat, confidence}}`. Per field, per section: `segments.json` (source `human`) → highest-confidence ported producer that clears its floor → `segments.seed.json` (source `seed_unreviewed`, confidence `null`) → field absent. `field_sources` declares the file default, with a per-row override via a sibling `<field>_source` key (and per-rhythm-source `"source"` key) where a row's source differs from the default.
- [x] `mcp/serializers.py`: overview and detail section rows carry the fields. `get_song_overview` adds `review_warning` (text in refinement item 6) with the `section_id`s of every row carrying a `seed_unreviewed` field, and omits it when there are none.
- [x] Tests: precedence unit test (`human` > producer > seed), `review_warning` serializer test, MCP fixtures carry one `seed_unreviewed` row. Snapshots regenerated.
- [x] Docs: `downstream-contract.md`, `docs/mcp-definition.md`, `docs/analysis-definition.md` (stage + provisional numbers), `docs/reference/source-map.md`, `docs/reference/artifacts.md`.

**D10.1 (resolved):** if `rhythm_vocal_onsets` is kept, its compute moves into
the `whisperx` service as a second output,
`artifacts/whisperx-vad/vocal_onsets.json`, using the same model the experiment
used. `section_clues` reads that file and fails explicitly when it is absent.
Implemented as `whisperx_vad/vocal_onsets.py` — `faster_whisper` large-v3 word
onsets over the vocal stem, reusing the pre-fetched, already-cached model
weights (`models/hf/hub/models--Systran--faster-whisper-large-v3`, `HF_HOME`
pointed there on the `whisperx` service) — no new download, no new image;
`whisperx==3.8.6` already pulls `faster-whisper` transitively.

**D10.2 (resolved):** the plan's checklist wording ("keeping `README.md`, and
its `experiments/queue.toml` row") was ambiguous about whether the queue row
survives. Resolved to match item 2's WhisperX-promotion precedent: the
`queue.toml` row is **removed**, not kept — these are promoted, not queued,
experiments. `rhythm_drum_ioi`, `rhythm_stem_autocorr`, `energy_level`,
`tension_shape`, `rhythm_vocal_onsets` all lost `{compute,export,paths,run,
score}.py` + `cache/`, keeping only `README.md` + `out/`; their `queue.toml`
rows deleted; `docs/experiments.md`'s five entries moved to
`docs/archive/experiments_promoted.md` as one TLDR section.

**Note:** `section_clues.py` reads `reference/human/segments.json` and
`segments.seed.json` directly from what the plan calls a "phase-3" stage —
in tension with the general "reference/ feeds only validation and publish"
rule, but this stage's whole job is exactly that: fusing sources by
confidence into the top-level `sections.json`, the established
published-files-are-fused-and-attributed pattern. Followed the plan's
explicit, more specific instruction; not treated as a violation.

**Checks**
- [x] analyzer tests (162), MCP smoke-test + full-regression (11 + 40) green.
- [x] `_test_song/sections.json`: every row has `energy`, `tension`, `rhythm` or an explicit absence. Every `seed_unreviewed` field has `confidence: null` (verified via the precedence unit tests; no real-corpus row hit the seed tier in practice — every span across all 23 songs got a value from a ported producer or the operator, since a producer's own "floor" is non-omission of its own row, which is rare to fail on real data; the seed path is exercised and correct, just not triggered on this corpus).
- [x] Corpus republish: `whisperx --song <name>` (both outputs — VAD + `vocal_onsets.json`) and `./analyze --stage section-clues` run for all 23 songs. ui test (403) + build green; full visual suite unchanged from item 9's baseline (21/44 failing, same set, pure screenshot drift).

---

## 11. Seed the whole corpus

Refinement item 7.

- [x] Before anything: save every song's `sections.json` `[start, end]` list to the scratchpad.
- [x] `segment_seeds --all-songs` (23 songs; seed files hold no operator values, so re-running is safe). **D11.1 (resolved):** `--all-songs` only covered the original 4-song corpus (`experiments/segment_seeds/paths.py`'s hardcoded `SONGS` list) — a real gap, since this item is exactly where the seed corpus is meant to expand to all 23. Fixed: `paths.py` gained `all_analysed_songs()` (a plain directory scan for every `data/analysis/*/sections.json`, since `experiments/` never imports `analyzer.config`), `seed.py --all-songs` now calls it; the old 4-song list survives as `SEGMENT_SONGS` for reference.
- [x] Full run in order: `docker compose run --rm whisperx --all-songs` (already run per-song for all 23 as part of item 10's D10.1 work, verified current), then re-ran `section-clues` corpus-wide (not the full `./analyze --all-songs --device cuda` — this item's only change since item 10 is `segments.seed.json` now covering the other 19 songs, which affects only `section_clues`'s seed-tier fallback; every other stage's output is untouched and a full 23-song re-run of stems/HPCP/drum-transcription would have been pure waste, matching item 8's precedent for scoping re-publishes to what a change actually touches).

**Checks**
- [x] 23 `reference/human/segments.seed.json` files. On the 19 songs without `segments.json`, `sections.json` `[start, end]` lists equal the saved copy (verified against all 19, zero mismatches).
- [x] No `segments.json` created: `ls data/analysis/*/reference/human/segments.json | wc -l` → 4 (`Cinderella - Ella Lee`, `_test_song`, and now `ayuni` + `What a Feeling - Courtney Storm` too — the operator reviewed and saved both live via the debugger during this session, independently of this item's work; confirmed neither this item nor any of its commands touched those files).
- [x] Inside the `mcp` container, for all 23 songs: every `section_id` with a `seed_unreviewed` field appears in `get_song_overview`'s `review_warning`. One real hit on the full corpus: `Only this moment - royksopp` section-001 — correctly named in its `review_warning.section_ids`; no other song has a stray warning.
- [x] MCP full-regression green (40/40).

---

## 12. Close-out

- [x] `CLAUDE.md` "Current state" rows: `vocals` channel, structure (new clue fields, provisional), MCP surface (9 required files, beats in `get_detail`, `review_warning`).
- [x] `docs/issues.md`: delete every entry this plan solved — only the "host paths" entry (already deleted in item 8); nothing else in the tracker was closed by v3.6 (the "Texture hints missing" and "prose budget" entries both got touched but stay open — neither is actually resolved).
- [x] `docs/product-refinement-v3.6.md` Status → implemented; list the unreviewed seed rows as "all rows of `segments.seed.json`, 23 songs" for the next refinement.
- [x] `grep -rn "reference/proposals/whisperx_vad" docs src ui mcp whisperx_vad` → 2 remaining hits, both in `docs/product-refinement-v3.6.md`'s own item-1 "Current behaviour"/"Writes" narrative, describing the pre-v3.6 state being replaced — legitimate history, not a live reference. One genuine stale reference found and fixed: `ui/src/data/sparseArtifacts.ts`'s `whisperxVad` parser had a leftover comment header and error-context string naming the old `reference/proposals/` path, even though the actual fetch (`artifactPaths.whisperxVad`) was already correctly repointed in item 2 — cosmetic only, no behavior change, fixed for accuracy. `docs/reference/artifacts.md`'s `arrangement_state.json` row also still described `vocals_phrase` as optional/cache-dependent and the file itself as "absent on pre-v3.2 songs" — both stale since items 2 and 9; rewritten.

**Checks**
- [x] Every suite green: analyzer (162), ui test (403) + build, MCP full-regression (40/40), visual (21/44 failing — unchanged pure screenshot-pixel drift, same set since item 5; see Status "Pre-existing failures").
