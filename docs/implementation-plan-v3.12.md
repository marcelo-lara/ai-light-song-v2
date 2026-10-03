# Implementation plan — v3.12

**Status: implemented.** Items 28, 29, 31, 32, 33, 34, 35, 37, 38 shipped; item 30 (downbeat re-anchoring) and item 36 (vocal cadence from word onsets) ended as measured experiments / decisions D2 and D9 (gate not met, nothing promoted). Turns [`product-refinement-v3.12.md`](product-refinement-v3.12.md)
into an ordered worklist for a Sonnet implementer in batch mode. The refinement
doc holds the rationale; this plan says what each item builds, how it is
checked, and what must not be undone. Items continue v3.11's numbering (19–27
shipped). Branch: `v3.12`.

## Item order

| # | Item | Refinement | Kind | Depends on |
| --- | --- | --- | --- | --- |
| 28 | Pre-flight | — | commits + checks | — |
| 29 | Kick attacks | item 4 | experiment | 28 |
| 30 | Downbeat re-anchoring | item 3 | experiment → `src/` | 29 |
| 31 | Filter sweeps v2 | item 5 | experiment | 28 |
| 32 | Light changes in `src/` | items 1, 2 | `src/` | 29–31 |
| 33 | Publish texture and light changes | item 6 | `src/` + contract | 32 |
| 34 | MCP projection | item 6 | `mcp/` | 33 |
| 35 | Debugger lanes from published files | items 1, 2, 6 | `ui/` + visual QA | 33 |
| 36 | Vocal cadence from word onsets | item 7 | `src/` + contract | 28 |
| 37 | Corpus run and validation | all | data | 30–36 |
| 38 | Close-out | — | docs | 29–37 |

**Scope.** Light-relevant change, never transcription: no pitch, harmony or word
text reaches any file. `src/` never imports `experiments/`: promotion ports the
code. Phase 3 stages read published files and `artifacts/`, never audio; item 29
and 31's audio work runs in phase 1/2 or stays in `experiments/`.

---

## How this plan is worked

**Validate each item, then push it on its own.** Work one plan item at a time.
When an item is complete, run its tests in the container; only if they pass,
tick its checkboxes, then commit and push that item by itself (`git push origin
v3.12`; check `git branch --show-current` prints `v3.12` first, never commit to
`main`) before starting the next. Name the commit after the plan item as written
here — e.g. ``29. Kick attacks``. One commit per item, never a batch commit at
the end.

**Use the recommendation; only a genuinely blocking decision stops an item.**
An open question mid-implementation is resolved by adopting the best
recommendation and continuing. Only a decision where proceeding under any
assumption would make the work wrong or wasted becomes a new `D` item written
into this plan; the session then **continues with the next item**, skipping only
items that depend on the blocked one.

**Checks run in the container**: `docker compose run --rm test` (analyzer),
`docker compose run --rm ui npm run test` / `npm run build` (`ui/`), the MCP
suites (`docker compose run --rm --no-deps -T --entrypoint python mcp mcp/tests/run.py smoke-test` /
`full-regression`), single-stage re-runs
`docker compose run --rm app ./analyze --song "/data/songs/<song>.mp3" --stage <stage>`,
and the visual suite per [`reference/ui-regression.md`](reference/ui-regression.md).

**Validation set** (refinement doc table): *Medicine-MilkInc* 8 fill, 9
groove_in, 16 build, 19 break, 23 drop, no point in 10–14; *Armin - Revolution*
55 build, 59 gap, 60 drop; *ayuni*, *Charli-VonDutch* by operator review. Bar
numbers are the pre-item-30 grid; after item 30, compare by time (± one beat).
Report thresholds chosen on these songs as such.

**Contract changes are written as they land**, as current state, into
`docs/reference/downstream-contract.md`, `docs/mcp-definition.md` and
`docs/reference/artifacts.md`.

**A failure found after an item is committed:** → `docs/issues.md`; one
needing a design decision → a `BUG` in the refinement doc, "Addressed by item N".

---

## Status

| | |
| --- | --- |
| Done | 11 of 11 |
| Visual QA items | 35 |
| MCP full-regression | 34, 37 (smoke-test on every item touching `mcp/` or a top-level file) |
| Contract changes | 30 (`beats.json` bar labels), 33 (`light_change` rows, `bar_features.json`, producers), 36 (`vocal_cadence.json` source tier) |
| Pre-existing failures | `docker compose run --rm test` 223 pass; `ui npm run test` 525 pass; `npm run build` ok; MCP `smoke-test` 29/29 and `full-regression` 59/59 pass. **Visual suite: 50 of 58 specs fail on HEAD, one cause**: the `Bar Features` and `Light Changes` proposal lanes (v3.12 items 1–2) request `reference/proposals/bar_features.json` and `light_changes.json`, which the `RegFull - Fixture` has not got, so every spec that asserts no failed response gets two 404s (e.g. `song-full`, `timeline-zoom`, `timeline-scrolled`, `verdict-checks`, `phrases`, `filter-sweep`, `hint-drag`, `left-panel`, `header-readout`). 6 specs pass, 2 did not run. Item 35 moves both lanes to published files and adds fixtures, which clears it; not fixed earlier. |
| Decisions | D0 (resolved): the operator told this session to push; each item is pushed to `origin v3.12` after its commit. D1 (item 29): Medicine `kick_present` is right on 13 of 14 bars (9–17 present, 19–22 absent) and **misses bar 18**: its drum-roll hits are low-end bumps with a click ≤ 4 dB, and lowering the click gate far enough admits the bass hits in bars 20–21. Accepted, not tuned further. Thresholds `CLICK_DB` 6.5, `CLICK_MIN_DB` 4.0, `PRESENT_MIN_CONF` 0.25, the +50 ms bin shift and the short-bar rule were chosen on Medicine (not held out). Agreement with `drum_events` kicks ±50 ms, mean of 27 songs: precision 0.44, recall 0.32 (omnizart over-labels toms and snares, so a cross-check only); recall near zero on Armin, Sash, StealTheShow, Charli-VonDutch, ChangedTheWayYouKissMe where a hat bed hides the click. Corpus: 6,767 attacks (68/min), 715 echoes, 35% off-grid.  D2 (item 30, **gate not met, not promoted**): `experiments/downbeat_reanchor` scores downbeat F1 @ +-70 ms on the 5 Moises songs **0.024** (confidence-bearing downbeats, the incumbent's convention) / **0.163** (all downbeats) vs allin1 0.343 and `downbeat_anchors` 0.301, with 0 bars != 4 beats outside `off_grid_spans` (47 on today's grid; 74 counting the song-edge partials). Zero irregular bars is met by construction (one phase per trusted run) and is what costs the F1: *Armin* has a real 1-beat slip inside one trusted run, and the votes are thin (kick phase alone 0.000). `timing.py`, `artifacts.md` and `downstream-contract.md` untouched; **items 32+ proceed on the old grid**. No threshold was tuned on Medicine, Armin, ayuni or Charli-VonDutch (a post-hoc 24-point grid reached at most 0.166, not adopted). Possible follow-up outside this plan: let the phase change only inside an unresolved span. D3 (item 31): `experiments/filter_sweep_v2` — Armin bars 51–58 `opening` (covers 55–58; the trailing window starts early), end at bar 59 (109.39 s) `aftermath: gap`; Medicine bars 7–15 `opening` (bar 16 is the 1-beat grid slip, no state, so 9–15 not 9–16), end at bar 16 `aftermath: drop`; ayuni 2 sweeps and Charli-VonDutch 2 sweeps (old detector 0), listed in `experiments/filter_sweep_v2/out/score.txt` for operator review. Corpus 131 sweeps (1.3/min vs v1 79), 65% with `aftermath: none` (halved confidence). Resonant peak Hz is reported but drives nothing (jumps between chord tones); state comes from the high/low ratio and the 99% rolloff. Thresholds `HL_SLOPE` 1.5, `ROLL_SLOPE` 0.15, `MIN_CONS` 0.6, `DROPOUT_DB` 6, `MIN_RUN_BARS` 3, `HOLE_RATIO` 0.75, `DROP_RATIO` 1.25 were chosen on Armin and Medicine (not held out); the dropout rule flatters the Armin check by construction. Run order: filter_sweep_v2 compute, export, then bar_features. D4 (item 32): phase 3 may not read audio, `reference/` or `reference/proposals/`, and kick attacks (mix audio) and the sweep spectrum (harmonic stem) are audio work, so the smallest honest split is two measurement stages and one phase-3 stage. `extract-harmonic-spectrum` (1.5, no confidence; half-beat spectrum rows of the harmonic stem, `artifacts/harmonic_spectrum/half_beats.json`) and `detect-kick-attacks` (2.6, carries confidence; `artifacts/kick_attacks/kick_attacks.json`) are straight ports; the slopes, sweep state and `kick_present` rule stay in phase 3 (`light-changes`, 3.3, `stages/light_changes.py`), which reads only published `beats.json`, `loudness.json`, `drum_events.json`, `arrangement_state.json` and `artifacts/`. All three run after `publish-arrangement-state`. Dropped from the table vs the experiment: the `gestures` column (it would read `song_event_timeline.json`, which item 33 makes `light_changes` write into) and the v1 `sweep` overlap. Sweep end events and `aftermath` are not ported (no consumer in item 33). Sweep state enters the detector as a ramp onset: inside each `opening`/`closing` run, walk back from the run's last bar while the bar-median high/low ratio does not fall; a climb of >= 3 bars and >= 4.5 dB (`HL_SLOPE` x `MIN_RUN_BARS`) makes a `source: sweep` point (`build` for opening, `break` for closing) unless a step point is within 1 bar, which is tagged instead. Point time: half-beat refinement within +-1 beat of the bar edge, floored to the beat that contains the change, so it is on the grid and never later than the onset; sweep points stay on the bar edge. `confidence` stays `null` (uncalibrated score; a sweep point has none). Thresholds `SWEEP_MIN_BARS` 3, `MOVE_MARGIN` 0.15, `MIN_STEP_SPREAD` 0.1 and the strict no-fall rule of the ramp walk were chosen on Armin and Medicine (and the point-time check on ayuni and Charli-VonDutch), not held out. D5 (item 32): `light_changes` points carry `confidence: null` plus a `confidence_reason` (the pooled score is uncalibrated; a sweep point has no score) — the repo's honest-null rule, as for `downbeat_confidence`; item 33 publishes it as is. Point time is floored to the beat containing the change (never late); round-to-nearest is a one-line change. Validation: 8 of 8 targets within one beat, Medicine 10–14 empty, but Medicine 8, 19, 23 sit at 0.96–1.0 beat early (right at the limit) and Medicine gets an extra break at bar 18 beat 1. Corpus 494 points / 103.0 min = 4.80/min (experiment 4.71), median 4.55/song, range 1.49–8.97. Roles: break 168, drop 152, build 128, groove_in 18, gap 12, fill 12, unknown 4. Constants (`SWEEP_MIN_BARS` 3, strict no-fall ramp walk, `MOVE_MARGIN` 0.15, `MIN_STEP_SPREAD` 0.1, S ≥ 7, role rules) were tuned on Medicine and Armin, not held out; Armin bar 55 depends on the walk-back rule. D6 (item 33): new stage `publish-light-changes` (7.7). `bar_features.json` `transient_density` is the artifact's `transient_mean`. `light_change_role` goes on the bar containing the point's time (earlier role wins when two share a bar; 4 times on Armin). Points inside a section gap get `section_id: null` (Armin 66.77–81.76 s, 2 of 29), never a nearest-section guess. After a single-stage `build-gestures` re-run, `publish-light-changes` must be re-run (it is in cli.md and source-map.md). Top-level required files are now ten. D7 (item 34): the overview byte budget stays **6900** (F4.20, committed `McpFull` fixture): the `light_changes` block (2 rows) took the fixture overview from 5451 to 5779 bytes (+328), still 1121 under the ceiling, so no raise is needed and none was taken. Real songs (pretty-printed JSON, full overview / brief) grow 2-8% / under 1.2%: Medicine 25100 -> 27106 / 4761 -> 4803; Armin 41851 -> 43839 / 6968 -> 7010; Fascination 101777 -> 103083 / 19178 -> 19220; _test_song 20767 -> 21349 / 3898 -> 3939 (about 15-60 rows of `{time, role}`; brief is `{count}`). Projection choices: `light_change` rows carry `confidence: null` as a separate field only in `get_detail` (the overview row is `{time, role}`); `bar_texture` `position` is that of the bar `start`; a `light_change` at exactly the span end is included (same inclusive rule as transitions); role `drop` is passed through as published, `F2.11` only scans the fixture (roles `groove_in`, `build`). D8 (item 35): the three proposal files `kick_attacks.json`, `downbeat_reanchor.json`, `filter_sweep_v2.json` also 404 on the fixtures; they were added to the named allowed-404 regex `OPTIONAL_PROPOSALS_404` in `tests/ui-visual/helpers.ts` rather than adding fixtures (which would draw three more badged lanes and re-baseline more). The visual suite is 61/61 (was 6 pass / 50 fail / 2 not run on HEAD). D9 (item 36, **gate not met, tier not shipped**): onset-derived line starts (a line breaks where the gap between consecutive `vocal_onsets.json` word times is >= 1 beat at the song's bpm) vs lyric line starts (human > moises `lyrics.json`, markers dropped), F1 @ +-1 beat, on the 5 songs with lyrics: Armin 0.053 (1 of 10 predicted, 28 gold), Hideaway 0.000 (0 of 17 predicted, 20 gold), Queen of Kings 0.504 (33 of 89, 42), _test_song 0.364 (4 of 17, 5), Titanium 0.368 (25 of 101, 35); pooled precision 0.250, recall 0.563, **F1 0.346 vs the 0.7 gate**. Informational only, not tuned: a 2-beat rest gives pooled 0.305, 4-beat 0.075. The 1-beat rule is the plan's, fixed before measuring, so no threshold was chosen on validation songs. Word onsets carry no end time, so rests cannot be measured from word ends; whisper word times also split on slow phrasing. `vocal_cadence.py` unchanged, `source` stays `null` without lyrics; the measurement script lived in the session scratchpad and was deleted. |

---

## 28. Pre-flight

- [x] Commit this plan and the refinement update as ``28. v3.12 plan``.
- [x] Run every suite above on HEAD; list each failing test by name in Status → "Pre-existing failures".
- [x] `docs/experiments.md`: `bar_features` and `light_changes` entries record the operator verdict "promote" (refinement item 2).

---

## 29. Kick attacks

Refinement item 4. Experiment `experiments/kick_attacks/`, beside `kick_check`.

- [x] Kick = attack only: steep 40–120 Hz rise (≈10–20 ms) on the **mix**, with a coincident 2–5 kHz click; pitch drop over the first ≈50 ms as tie-break. Sustained low end never fires.
- [x] Echo rejection: an attack that follows a stronger one at a repeated fixed offset and is weaker and duller is labelled `echo`, not a kick.
- [x] Off-grid survivors (beyond ¼ beat from `beats.json`) keep the event at low confidence.
- [x] Output `reference/proposals/kick_attacks.json` `{time, confidence, echo_of}`; `bar_features` gains `kick_attacks` and `kick_present` columns (half-beat variant too). Lane "Kick Attacks", queue row.
- [x] Tests: synthetic kick, sustained bass note, kick + delay echo.

**Checks**
- [x] Medicine bars 9–18 `kick_present`, 19–22 not. Agreement with `drum_events` kicks (±50 ms) reported per song.

---

## 30. Downbeat re-anchoring

Refinement item 3. Experiment `experiments/downbeat_reanchor/`; ported to `timing.py` only if it passes.

- [x] Beat times unchanged. Anchors: item-29 kick attacks on the beat (kick-phase over a sliding 8-bar window), `song_event_timeline` impacts, `arrangement_state` bass/drums entries. Each anchor votes a downbeat phase.
- [x] Between anchors, bars counted in fours on beat times; the slip is resolved by relabelling the index, never by warping time. Disagreeing anchors → span `resolved: false` (existing `downbeat_confidence: null` rule).
- [x] Spans with no kick (Charli-VonDutch) use the remaining anchors; none → allin1's phase, unresolved.
- [x] Score: downbeat F1 @ ±70 ms on the Moises songs vs allin1 (.343) and `downbeat_anchors` (.301); count of bars ≠ 4 beats outside `off_grid_spans`, corpus-wide.
- [x] Promote **only if** F1 > .343 and zero irregular bars: `timing.py` writes `bar`/`beat`/`type`/`downbeat_confidence` from the re-anchored phase; `field_sources` names the new producer. Otherwise stays an experiment and becomes a `D` item; items 32+ proceed on the old grid.

**Contract** (on promotion)
- [ ] (not promoted, N/A — see D2) `artifacts.md`, `downstream-contract.md`: `bar` labels may shift by whole beats vs earlier runs; the producer vocabulary gains `downbeat_reanchor`.

**Checks**
- [x] `docker compose run --rm test`; MCP `smoke-test` (Medicine bar lengths: not promoted, old grid unchanged).

---

## 31. Filter sweeps v2

Refinement item 5. Experiment `experiments/filter_sweep_v2/`.

- [x] Half-beat frames of a log-frequency spectrogram of the harmonic stem: resonant peak Hz, peak sharpness, high/low energy ratio.
- [x] Per bar: slope and consistency over the last 1/2/4/8 bars (a running indicator, not a verdict).
- [x] Sweep **end** event on the beat grid (top reached, cut, gap, drop landing) with `aftermath` ∈ `gap` / `drop` / `break` / `none` from the next 1–2 bars of `bar_features`. `none` lowers confidence.
- [x] Output `reference/proposals/filter_sweep_v2.json`; `bar_features` gains `sweep_slope`, `sweep_state` (`opening`/`closing`/null). Lane "Filter Sweeps v2", queue row.

**Checks**
- [x] Armin: opening over bars 55–58, end at 59 with `aftermath: gap`. Sweeps found on ayuni and Charli-VonDutch (old detector: 0), listed for operator review. Medicine 9–16 opening.

---

## 32. Light changes in `src/`

Refinement items 1–2. Port `experiments/bar_features` and `experiments/light_changes` into a phase-3 stage (`stages/light_changes.py`); the experiments stay as the reference.

- [x] Stage builds the per-bar table (plus items 29 and 31 columns) and writes `artifacts/light_changes/bar_features.json` and `artifacts/light_changes/light_changes.json`.
- [x] Point time = the beat where the change physically starts (half-beat table, within ± one beat of the bar edge), snapped to the beat grid. Fixes Charli's off-bar points.
- [x] Item 31's sweep state is a detector input; Armin bar 55 is the target.
- [x] Roles as in the experiment; unclaimed → `unknown`, never a guessed role.
- [x] Tests: ported experiment tests + a fixture where the half-beat refinement moves a point.

**Checks**
- [x] `docker compose run --rm test`; stage re-run on the validation set: all 8 targets within one beat, roles right, Medicine 10–14 empty; corpus rate reported vs the experiment's 4.7/min.

---

## 33. Publish texture and light changes

Refinement item 6.

- [x] `song_event_timeline.json` gains rows `{type: "light_change", role, start_time, end_time: start_time, confidence, section_id}`; `field_sources` producer `light_changes`.
- [x] New required top-level `bar_features.json`: `{schema_version, song_name, field_sources, bars[]}`, each `{bar, start, end, irregular, brightness, transient_density, kick_present, sweep_state, light_change_role}` — the slim projection, not the experiment's full row.
- [x] `mcp/loaders` hard-require list gains `bar_features.json` (no degraded mode).

**Contract**
- [x] `artifacts.md` (rows + `field_sources`), `downstream-contract.md` (new file, new row type, producers `light_changes`), `mcp-definition.md` file list.

**Checks**
- [x] `docker compose run --rm test`; MCP `smoke-test`.

---

## 34. MCP projection

Refinement item 6.

- [x] `get_song_overview`: a `light_changes` block, one compact row per point `{time, role}` (no `position`, per the overview's byte budget); `scope: "brief"` keeps only the count.
- [x] `get_detail` structural view: `bar_texture` rows for bars in the span, each with `position`; `light_change` rows with `position`.
- [x] Golden fixtures and the overview byte budget updated; budget growth stated in Status → Decisions.

**Checks**
- [x] MCP `smoke-test` + `full-regression`; `get_detail` over Medicine bars 8–20 shows groove_in, build and break.

---

## 35. Debugger lanes from published files

Items 1, 2, 6. Lanes "Bar Features" and "Light Changes" read the published files instead of `reference/proposals/`; "Kick Attacks" and "Filter Sweeps v2" stay proposal lanes (flask badge).

- [x] `ui/src/data/paths.ts`: lanes read `bar_features.json` and `song_event_timeline.json` `light_change` rows; flask badge removed from both.
- [x] Fixtures: `RegFull - Fixture` gains `bar_features.json` (≥ 8 bars, one `irregular`) and 3 `light_change` rows (`groove_in`, `build`, `drop`); `RegPartial - Fixture` gets none.
- [x] `tests/ui-visual` BADGED list and baselines updated; one-line justification per re-captured baseline in the commit message.

**Visual QA** (surface `song-full`, `/?song=RegFull - Fixture`, viewport and readiness per the guide)
- [x] No `console.error` / `console.warn`, no `pageerror`, no failed response except the guide's named allowed 404s.
- [x] Lane "Light Changes" present, exactly 3 markers, labels `groove_in`, `build`, `drop` in time order.
- [x] Each marker's x within 2 px of the ruler x for its `start_time`.
- [x] Lane "Bar Features" block count = fixture bar count; the `irregular` bar is drawn grey; the last block's right edge within 4 px of its `end` on the ruler.
- [x] `song-partial`: neither lane drawn, no empty header.
- [x] Diff `song-full`, `timeline-scrolled`, `timeline-zoomed-out` baselines; masks as in the guide.

**Checks**
- [x] `docker compose run --rm ui npm run test` / `npm run build`; visual suite green.

---

## 36. Vocal cadence from word onsets

Refinement item 7.

- [ ] (not shipped, gate failed — D9) `vocal_cadence.py`: when neither `reference/human/lyrics.json` nor `reference/moises/lyrics.json` exists, build `lines` from `artifacts/whisperx-vad/vocal_onsets.json` **times only**: a line breaks at a rest ≥ 1 beat. Word text is never read. `calls` stay `[]` (no call marker without lyrics) with `reason` saying so.
- [ ] (not shipped, gate failed — D9) `source: "word_onsets"` (third tier); producer vocabulary gains it.
- [x] Gate: on the songs with lyrics, onset-derived line starts vs lyric line starts, F1 @ ± one beat. Ship the tier only if F1 ≥ 0.7; otherwise a `D` item, `source: null` as today.
- [ ] (not shipped, gate failed — D9) Tests: tier precedence, rest-split, no text in output.

**Contract**
- [ ] (not shipped, gate failed — D9) `artifacts.md`, `downstream-contract.md`: third `source` tier.

**Checks**
- [ ] (not shipped, gate failed — D9) `docker compose run --rm test`; MCP `smoke-test`; count of songs gaining lines.

---

## 37. Corpus run and validation

- [x] Re-run the pipeline on all 27 songs.
- [x] Record in this item: validation-set hit/miss table (time and bar landed, role), corpus points/min, roles distribution, irregular-bar count before/after item 30, sweeps found per song.
- [x] Operator lane review list: ayuni, Charli-VonDutch bar placement; any song above 8 points/min.

**Checks**
- [x] MCP `full-regression`; `docker compose run --rm test`.

**Run record (2026-10-03).** `docker compose run --rm -T app ./analyze --all-songs --device cuda` (CUDA available, GTX 1650): **27 passed, 0 failed**, about 36 min; whisperx and `ensure-stems` not re-run. Determinism: Medicine re-run a second time, then every top-level `*.json` plus `artifacts/{light_changes,kick_attacks,harmonic_spectrum}/` hashed on all 27 songs before and after: byte-identical. (No pre-run hash exists for the whole corpus; the first corpus run is the baseline, so only the Medicine re-run proves determinism.) Every song has the 10 required top-level files; `list_songs`, `get_song_overview` (full and brief) and `get_detail(bars=[1,2])` return without error on all 27.

**Validation set** (old grid, D2; bar start from `bar_features.json`, hit = point within one beat of the bar start, role as expected):

| Song | Target bar, role | Bar start s | Point landed | Offset | Role | Result |
| --- | --- | --- | --- | --- | --- | --- |
| Medicine | 8 fill | 13.54 | 13.11 (bar 7 beat 4) | -1.00 beat | fill | hit (at the limit) |
| Medicine | 9 groove_in | 15.26 | 15.26 (9.1) | 0 | groove_in | hit |
| Medicine | 16 build | 27.25 | 27.25 (16.1) | 0 | build | hit |
| Medicine | 19 break | 31.10 | 30.69 (18.4) | -0.95 beat | break | hit |
| Medicine | 23 drop | 37.96 | 37.54 (22.4) | -0.98 beat | drop | hit |
| Medicine | none in 10-14 | | no point in bars 10-14 | | | hit |
| Armin | 55 build | 102.01 | 102.01 (55.1, `sweep`) | 0 | build | hit |
| Armin | 59 gap | 109.39 | 109.39 (59.1) | 0 | gap | hit |
| Armin | 60 drop | 111.22 | 111.22 (60.1) | 0 | drop | hit |

8 of 8 targets plus the empty span, as in D5. Medicine still carries the extra break at 29.41 (bar 18 beat 1) noted in D5 and 3 of its 5 hits sit 0.95-1.00 beat early, so any change to the beat floor risks them.

**Corpus.** 494 points / 103.0 min = **4.80/min** (experiment 4.71), identical to D5, so items 33-34 added no points and the published `light_change` row count equals the artifact count on every song (494). Roles: break 168, drop 152, build 128, groove_in 18, gap 12, fill 12, unknown 4. Per song, points / per min (sweeps found, from `reference/proposals/filter_sweep_v2.json`, 131 total, not re-run: generated 2026-10-03 03:42 from unchanged inputs):
Armin 29/8.97 (6 sweeps), Best Friend 17/5.64 (5), ChangedTheWay 14/4.43 (4), Charli-Guess 14/5.94 (1), Charli-VonDutch 8/2.97 (2), Chimera 19/3.61 (3), Cinderella 31/5.48 (14), CruelSummer 29/7.00 (3), Fascination 18/2.68 (9), Gabry Ponte 19/6.52 (6), Hideaway 15/3.58 (7), In da name 20/6.12 (1), It's a fine day 23/4.22 (14), Medicine 29/8.82 (5), Only this moment 11/2.89 (0), Pet Shop Boys 11/1.49 (2), Queen of Kings 11/4.51 (3), Rapture 27/7.52 (7), Rotate 13/4.55 (4), Sash 18/5.60 (4), StealTheShow 39/6.20 (10), Titanium 13/3.36 (6), Underworld 16/3.71 (3), What a Feeling 10/2.85 (4), Yonaka 9/3.41 (3), _test_song 7/7.23 (3), ayuni 24/8.74 (2).

**Irregular bars** (`bar_features.json` `irregular: true`; D2: item 30 was not promoted, so before = after = today's grid). 99 irregular bars corpus-wide; **72 outside `off_grid_spans`** (bar start and end both outside a span; D2's 47 excluded song-edge partial bars, 74 counted them, a different count of the same grid). Most on: In da name of love 6, Cinderella 5, CruelSummer 5, Charli-VonDutch 5, Medicine 5.

**vocal_cadence** (D9): 0 songs gained lines. Lines exist only where lyrics do: Armin 10, Hideaway 20, Queen of Kings 42 (human), Titanium 35, _test_song 5 (moises); the other 22 songs `source: null`, 0 lines.

**Checks run:** MCP `full-regression` PASS 59 / FAIL 0 / DEFER 0; `docker compose run --rm test` 263 passed.

**Operator lane review list.**
- ayuni and Charli-VonDutch bar placement: ayuni 24 points (8.74/min) with 1 irregular bar, Charli-VonDutch 8 points (2.97/min) with 5 irregular bars and 2 sweeps (the old detector found 0).
- Above 8 points/min: Armin - Revolution 8.97, Medicine-MilkInc 8.82, ayuni 8.74. Next: Rapture 7.52, _test_song 7.23, CruelSummer 7.00.

---

## 38. Close-out

- [x] `CLAUDE.md` state table, `analysis-definition.md`, `mcp-definition.md`, `downstream-contract.md`, `artifacts.md`, `ui-definition.md`, `experiments.md` (promoted entries → archive): current state after items 29–37.
- [x] Refinement doc: shipped items dropped.
- [x] Status → "Done", then mark this plan implemented.
