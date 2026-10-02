# Implementation plan — v3.10 (second pass)

**Status: implemented.** Turns the open items of
[`product-refinement-v3.10.md`](product-refinement-v3.10.md) into an ordered
worklist for a Sonnet implementer in batch mode. The refinement doc holds the
rationale; this plan says what each item builds, how it is checked, and what
must not be undone. Items continue the first pass's numbering (0–6 shipped),
so commit names stay unique.

## Item order

| # | Item | Refinement | Kind | Depends on |
| --- | --- | --- | --- | --- |
| 7 | Pre-flight | — | commits + checks | — |
| 8 | Cut stages — analyzer and MCP | item 9 | `src/` + `mcp/` + contract | 7 |
| 9 | Cut stages — debugger UI | item 9 | `ui/` + visual QA | 8 |
| 10 | Skill follows the cuts | item 9 | `ai-light-show` skill | 8 |
| 11 | Re-runs and watcher status | item 8 | `mcp/` + `./analysis-watcher` | 7 |
| 12 | Structure hint tools | item 7 | `mcp/` | 7 |
| 13 | Structure hints for the corpus | item 7 | data | 12 |
| 14 | Filter sweeps experiment | item 11 | `experiments/` + lane | 8 |
| 15 | Phrases experiment | item 2 | `experiments/` + lane | 13, 14 |
| 16 | Downbeat anchors experiment | item 10 | `experiments/` | 15 |
| 17 | Section names experiment | item 4 | `experiments/` + lane | 13, 15 |
| 18 | Close-out | — | docs | 8–17 |

**Not in this plan:** promoting items 14–17 into `src/`. The repo's rule is
to ask before promoting (`docs/experiments.md`), so each promotion is an
operator verdict on the lane and gets its own plan item in a later pass.
Until then `src/` never imports from `experiments/`; experiments read each
other's `reference/proposals/*.json` as data.

---

## How this plan is worked

**Validate each item, then commit it on its own.** Work one plan item at a
time. When an item is complete, run its tests the way the project requires (in
the container); only if they pass, tick its checkboxes, then commit that item by
itself before starting the next. Name the commit after the plan item as written
here — e.g. ``11. Re-runs and watcher status``. One commit per item, never a
batch commit at the end. *(The `/implement` workflow forbids pushing; the
operator pushes.)*

**Use the recommendation; only a genuinely blocking decision stops an item.**
An open question mid-implementation is resolved by adopting the best
recommendation and continuing. Only a decision where proceeding under any
assumption would make the work wrong or wasted becomes a new `D` item written
into this plan; the session then **continues with the next item**, skipping only
items that depend on the blocked one.

**Checks run in the container**: `docker compose run --rm test` (analyzer),
`docker compose run --rm ui npm run test` / `npm run build` (`ui/`; after a
dependency change, `docker compose build --no-cache ui`), the MCP suites
(`docker compose run --rm --no-deps -T --entrypoint python mcp mcp/tests/run.py smoke-test` /
`full-regression`), single-stage re-runs
`docker compose run --rm app ./analyze --song "/data/songs/<song>.mp3" --stage <stage>`,
and experiments via `./experiment` or
`docker compose run --rm --no-deps app python -m experiments.<topic>.run <compute|export|score>`.

**Contract changes are written as they land**, as current state, into
`docs/reference/downstream-contract.md` and `docs/mcp-definition.md`.

**A failure found after an item is committed:** → `docs/issues.md`; one
needing a design decision → a `BUG` in the refinement doc, "Addressed by item N".

**Experiments follow `docs/experiments.md`**: state the question and the
incumbent in the README before computing, score against the incumbent and a
cheap baseline, record a negative result as a result, and add the entry to
`docs/experiments.md`.

---

## Status

| | |
| --- | --- |
| Done | 12 of 12 |
| Visual QA items | 9, 14, 15, 17 |
| MCP full-regression | 8, 11, 12 (smoke-test on every item) |
| Contract changes | 8 (files and fields removed, tool removed), 11 (`force`, `get_watcher_status`), 12 (two tools, one prompt) |
| Pre-existing failures | none — analyzer 214 passed, MCP smoke 22/22, MCP full-regression 52/52, UI 534 passed, UI build ok |
| Decisions | Item 9: candidate-producer lanes (Segment Seeds, Rhythm Drum IOI/Stem Autocorr/Vocal Onsets, Energy Level, Tension Shape) removed with the fields they fed; `experiments/` dirs untouched. The `block_energy.json` operator-rating feature removed end to end. Item 8: `impact_alignment` and `function_status: "contested"`/`contested_by` removed with their producers (`section_clues.py`, `contest-section-function`). `whisperx_vad/vocal_onsets.py` and its `vocal_onsets.json` are now unread dead code — removal not in item 8; listed in `docs/issues.md` (close-out). |

---

## 7. Pre-flight

- [x] Commit this plan as ``7. v3.10 second-pass plan``. *(Committed with the refinement's experiment-first change to items 10 and 11.)*
- [x] Run every suite above on HEAD; list each failing test by name in Status → "Pre-existing failures".

---

## 8. Cut stages — analyzer and MCP

Refinement item 9.

- [x] `src/analyzer/pipeline.py`: remove `derive-energy-layer`, `contest-section-function`, `section-clues`, `classify-genre`, `extract-hpcp-and-key` and their stage modules (`energy.py`, `section_function.py`, `section_clues.py`, `genre.py`, `harmonic.py`), plus their artifacts in `paths.py`/`models.py`.
- [x] `ui_data.py`: `sections.json` no longer carries `key`, `energy`, `tension`, `rhythm` or their `*_source` overrides; `genre.json` is no longer published; `segments.seed.json` is no longer read. The `energy`/`tension`/`rhythm` keys in `reference/human/segments.json` are ignored, never rewritten.
- [x] `mcp/`: the required top-level files drop to nine (no `genre.json`); `get_song_overview` loses `genre`, `key`, `review_warning` and the section clue fields; `propose_section_field` is removed (`proposals.py`, `server.py`). `propose_hint` is untouched.
- [x] `validation/report.py` and anything else reading the removed artifacts: drop those reads; grep `src/` and `mcp/` for each removed name and leave zero hits.
- [x] MCP fixtures: regenerate or hand-edit so no fixture carries a removed file or field.
- [x] Contract: `downstream-contract.md` and `mcp-definition.md` list what was removed (current state, not history); `analysis-definition.md`'s module and stage tables lose the removed rows.
- [x] Tests: delete tests of removed code; add one asserting a full run writes none of the removed files.

**Checks**
- [x] `docker compose run --rm test`; MCP `smoke-test` + `full-regression`.
- [x] Full `./analyze` run on `_test_song` and *Armin - Revolution*: completes, publishes nine top-level files, `sections.json` has none of the removed fields.
- [x] Republishing `sections.json` now needs only `build-ui-data`; confirm on *Rapture - Nadia Ali*.

---

## 9. Cut stages — debugger UI

Refinement item 9.

- [x] `ui/`: remove every surface that reads or edits a removed file or field — energy/tension/rhythm in the segment editor and block inspector, the energy-layer lane, key and genre display, `propose_section_field` proposals in the review queues, and the server handlers that saved them. Grep `ui/src` and `ui/server` for `layer_c_energy`, `layer_a_harmonic`, `genre`, `tension`, `energy_source`, `seed_unreviewed`, `section_function` and leave zero hits outside tests that assert absence.
- [x] Saving a section in the segment editor still writes `start`/`end`/`label` to `reference/human/segments.json` and leaves any existing `energy`/`tension` keys in that file as they were.

**Visual QA** (runbook: [`reference/ui-regression.md`](reference/ui-regression.md))
- [x] Runtime assertions on every captured surface: no `console.error`/`console.warn`, no `pageerror`, no failed request for a file the page expects (`genre.json` and the removed artifacts are no longer requested at all).
- [x] Main timeline on the primary fixture: no lane titled with energy, tension or key; every remaining lane's content reaches the timeline's right edge (guide's full-extent check).
- [x] Segment editor opened on the first section: no energy, tension or rhythm control.
- [x] Baselines for each changed surface re-captured in the container, each with a one-line justification in the commit.

**Checks**
- [x] `npm run test`, `npm run build`, the visual suite.

---

## 10. Skill follows the cuts

Refinement item 9. Commit in `ai-light-show`, same item name (`f227388`).

- [x] `ai-light-show/.claude/skills/song-analysis/SKILL.md`: drop the `energy`/`tension`/`rhythm` editing guidance, the `section-clues` stage row and `field_sources` override examples; `reference/human/segments.json` holds `start`/`end`/`label` only; a boundary or label edit republishes with `build-ui-data`.
- [x] Grep the skill for `energy`, `tension`, `section-clues`, `propose_section_field`: zero hits.

---

## 11. Re-runs and watcher status

Refinement item 8.

- [x] `request_analysis(song, force=False)`: `force=True` writes the run request for an analysed song; default behaviour unchanged.
- [x] `./analysis-watcher` writes `data/analysis-watcher.heartbeat` (ISO timestamp) on every poll.
- [x] New tool `get_watcher_status()` → `{status: "up" | "down", last_heartbeat, age_s}`; `down` when the file is missing or older than 3 poll intervals. `request_analysis` adds `watcher: "up" | "down"` to its result.
- [x] Ship `analysis-watcher.service` (systemd user unit, `Restart=on-failure`) and document enabling it in `docs/reference/docker.md`. Enabling it on the host is the operator's step.
- [x] Tests: forced and unforced requests on an analysed fixture; status `up` with a fresh heartbeat, `down` with a stale or missing one.

**Checks**
- [x] MCP `smoke-test` + `full-regression`; the watcher's `--once` tests.
- [x] Live: watcher running → `get_watcher_status` is `up`; `--stop` → `down` within 3 polls; `request_analysis(force=True)` on `_test_song` completes a run.

---

## 12. Structure hint tools

Refinement item 7; contracts in `mcp-definition.md`, "Pre-analysis structure hint".

- [x] `get_structure_hint_brief(song)` → `{brief, existing}`; the same text is published as the MCP prompt `structure_hint` from one implementation.
- [x] The brief tells the client to research version, genre and shape, fill every schema field (`null` when unknown), include at least one source, and never write a time.
- [x] `write_structure_hint(song, hint)`: validates against schema `1.0`, refuses naming the first bad field, writes only `<song>/reference/pre-analysis/structure.json`. Both tools accept analysed songs and songs `request_analysis` would accept.
- [x] Tests: a valid hint round-trips through `existing`; an unknown enum, a missing `sources`, and any key containing a time are each refused with nothing written.

**Checks**
- [x] MCP `smoke-test` + `full-regression`.

---

## 13. Structure hints for the corpus

Refinement item 7.

- [x] For every song in `list_songs`, follow `get_structure_hint_brief` (web research) and store the result with `write_structure_hint`. Leave fields `null` rather than guess.
- [x] Record in the item's result the songs whose `track.version_duration_s` differs from `info.json`'s duration by more than 5 s.

**Checks**
- [x] Every song has a `reference/pre-analysis/structure.json` that `write_structure_hint`'s validator accepts.

---

**Result.** 27 of 27 songs have a validator-accepted `reference/pre-analysis/structure.json` (`data/` is gitignored, so the hints are not in the commit). Web research found nothing reliable for `_test_song`, `ayuni`, `Rotate-Skillibeng`, `StealTheShow-NeonDreams`, `Cinderella - Ella Lee`, `CruelSummer - Malvina` and `Chimera - Hana` (family `other`, confidence ≤ 0.2, nulls); `drops`/`chorus_is_drop`/`has_build_ups` are `null` everywhere because no source described them. `track.version_duration_s` differs from `info.json` by more than 5 s on: *ChangedTheWayYouKissMe-Example* (195 vs 189.72), *Only this moment - royksopp* (221 vs 228.22), *Queen of Kings - Alessandra* (160 vs 146.4), *Titanium - David Guetta ft Sia* (245 vs 232.41), *Underworld - Born Slippy* (264 vs 258.95).

## 14. Filter sweeps experiment

Refinement item 11.

- [x] `experiments/filter_sweep/`: spectral centroid per stem from the published FFT bands; a sweep is a near-monotonic centroid move over 2–16 bars on `harmonic` or `bass` with that stem's loudness roughly level. Rows: `direction`, `stem`, `start`, `end`, `depth`, `confidence`. Kept distinct from `gestures`' `riser`.
- [x] Export `reference/proposals/filter_sweep.json` for the whole corpus; `queue.toml` row; debugger lane "Filter Sweeps".
- [x] README: question, incumbent (`riser`), baseline, results; entry in `docs/experiments.md`. The operator's lane review decides promotion.

**Visual QA**
- [x] Runtime assertions as in item 9.
- [x] Lane "Filter Sweeps" on the primary fixture shows exactly as many blocks as the fixture's `filter_sweep.json` has rows.

---

**Result.** 79 sweeps over 27 songs (56 harmonic, 23 bass; 9 songs have none, including Armin — the primary fixture's `RegFull`/`RegPartial` carry three synthetic rows flagged `synthetic_fixture`). 11 of 79 overlap an incumbent `riser` span. No precision/recall: no hint labels a sweep, so the operator's lane review is the test. Not promoted.

## 15. Phrases experiment

Refinement item 2.

- [x] `experiments/phrases/`: edges from `arrangement_state` stem entries/exits, `gestures` impacts, pre-drop gaps and riser/snare-roll ends, each at the nearest trusted beat. Per phrase: kick presence (drums-stem energy below ~150 Hz, never `drum_events`), bass, vocals, riser and snare-roll density, filter sweeps (item 14's proposals), noise sweep, kick drop-out near the end, ends-on-gap, repeat-of (the earlier phrase it repeats), confidence. Conflicting evidence → `resolved: false`. No bar counting.
- [x] Fold `experiments/stem_presence_sections`' state machine in as an input.
- [x] Export `reference/proposals/phrases.json` for the corpus; `queue.toml` row; lane "Phrases".
- [x] Score boundary precision/recall against the reviewed segments and hints, EDM-shaped songs (item 13's `genre.family` = `edm`) reported apart from the rest; incumbent allin1, baseline `stem_presence_sections`. *Rapture* and *Charli-VonDutch* must match or beat stem-presence's results.
- [x] README + `docs/experiments.md` entry.

**Visual QA**
- [x] Runtime assertions as in item 9.
- [x] Lane "Phrases" on the primary fixture: block count equals `phrases.json`'s rows; the last block ends within 1 s of the song's end.

---

**Result.** 299 phrases over 27 songs (96 `resolved: false`). Boundary F1 at ±1.0 s, pooled: reviewed segments — phrases .431 vs allin1 .609 vs stem-presence .366 (EDM .452 / .567 / .291); review hints — phrases .437 vs allin1 .456 vs stem-presence .376 (EDM .667 / .490 / .591). *Rapture* matches stem-presence (segments .500, hints .769). **The "match or beat" bar is not met on *Charli-VonDutch*** (segments .667 vs .714; hints .833 vs .909): phrases finds the same hint boundaries plus one unlabeled edge at 36.25 s. Not tuned further — the acceptance score (1.5) and stem-presence weight (1.5) were already swept against these labels (README discloses it), so more tuning would only overfit. allin1 stays the better boundary finder; the operator's lane review decides promotion. `noise_sweep` fires on 3 of 299 phrases (rule too strict to use).

## 16. Downbeat anchors experiment

Refinement item 10.

- [x] `experiments/downbeat_anchors/`: reads item 15's proposals; each confident phrase edge on a stem entry or impact is a downbeat; bars counted in fours on trusted beat times between anchors; anchors disagreeing on phase → span `resolved: false`; allin1's phase only where no anchor reaches.
- [x] Score downbeat F1 against the Moises downbeats, same method as `analysis-definition.md` "Downbeats"; incumbent 0.226.
- [x] Export `reference/proposals/downbeat_anchors.json`; README + `docs/experiments.md` entry.

---

**Result (negative).** Downbeat F1 at ±70 ms vs Moises on the 5 songs with a reference (same scorer as the pipeline): anchors + allin1 .301 pooled vs incumbent allin1 .343 (4-song pool: .119 vs .234; the documented 0.226 does not reproduce exactly — today's same-method figure on the original four songs is 0.234). Beats both baselines (modulo-4 .069, kick-phase .180) but not the incumbent. Counting from an anchor is right (35/35 *Queen of Kings*, 4/4 *Armin*); the premise fails on 3 of 5 songs (*Titanium* anchors sit on Moises beat 3, *Hideaway* has the wrong beat-grid tempo, *Armin* has 5 of 6 spans unresolved so allin1's phase is blocked). 89 of 165 spans are `resolved: false`. Not promoted; follow-ups listed in the README.

## 17. Section names experiment

Refinement item 4; vocabulary and typical sequence in [`segments-vocabulary.md`](segments-vocabulary.md).

- [x] `experiments/section_names/`: from item 15's phrases, find build→drop units first (kick/bass entry + hit; never rising drum density), then label every phrase by its position in the typical sequence. Between build and drop: near-silence across all stems → `Pre-Drop`, roll/vocal/riser → `Fill`, both → two sections. A Fill can close any phrase. Repeats inherit labels. A drop with no build is found from the hit and the kick/bass entry.
- [x] Item 13's hint is a prior only (subgenre → expected shape; radio edit → early drop is normal; house/techno → no drop is expected). No hint → runs the same without it.
- [x] Boundaries snap to item 15's edges; every label has a confidence; a song with no build→drop unit keeps its current labels, attributed. `energy`/`tension` are never read.
- [x] Runs on every song, reviewed ones included. The report lists every reviewed label or boundary it would override.
- [x] Score label accuracy and boundary moves on the reviewed songs against allin1's mapped labels, with and without the hint. *Rapture* names both drops `Drop`; *Armin - Revolution* and *Medicine-MilkInc* show the full stage sequence.
- [x] Export `reference/proposals/section_names.json`; `queue.toml` row; lane "Section Names"; README + `docs/experiments.md` entry.

**Visual QA**
- [x] Runtime assertions as in item 9.
- [x] Lane "Section Names" on the primary fixture: block count and labels equal `section_names.json`'s rows.

---

**Result.** 191 blocks over 27 songs (26 named, 1 kept on current labels — *Pet Shop Boys*, unreviewed). Pooled over the 10 reviewed songs: exact label accuracy 0.391 (no hint 0.406) vs allin1 mapped 0.316; boundary F1 @ ±1 s 0.330 vs allin1 0.633 — better names, far worse boundaries. *Rapture* names both drops `Drop`. **The "full stage sequence" bar is not met on *Armin - Revolution* (6/10 stages) or *Medicine-MilkInc* (7/10)**: Armin's audio shows no kick/bass entry at the reviewed 59.6 s drop; Medicine's first 100 s is one phrase. The hint changed 2 of 27 songs (Armin, Sash) and lowered accuracy (Sash .372 with, .515 without). 98 of 133 reviewed labels and 75 of 123 reviewed boundaries (no proposal boundary within 4 s) would be overridden (`out/overrides.txt`). Thresholds are a priori; rule fixes made after reading *Rapture*, *Charli*, *Medicine* and *Sash* output are disclosed in the README. Not promoted.

## 18. Close-out

- [x] `CLAUDE.md`'s state table, `analysis-definition.md`, `mcp-definition.md` (status line: tools now built), `downstream-contract.md`: current state after items 8–17.
- [x] Refinement doc: drop items 7, 8, 9 (shipped); items 2, 4, 10, 11 stay open until their promotion verdicts.
- [x] Status → "Done", then mark this plan implemented.

**Result.** `CLAUDE.md`, `analysis-definition.md` (new sections: structure hint, watcher status, v3.10 experiments with their headline numbers and unmet bars), `mcp-definition.md`, `downstream-contract.md`, `product-definition.md` (nine top-level files), `reference/artifacts.md` and `analysis.segments.md` brought to current state. Refinement doc: items 7, 8, 9 dropped; items 2, 4, 10, 11 marked built-as-experiment, awaiting lane verdict. Defects moved to `docs/issues.md`: dead `vocal_onsets`, `noise_sweep` too strict, experiment tests not in the default `test` run; the fixture-rebuild hazard is now in `reference/ui-regression.md` step 1. The corpus is 27 songs; the reviewed-segments count stays 10 of 27.
