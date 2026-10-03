# Implementation plan — v3.12

**Status: not started.** Turns [`product-refinement-v3.12.md`](product-refinement-v3.12.md)
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
| Done | 4 of 11 |
| Visual QA items | 35 |
| MCP full-regression | 34, 37 (smoke-test on every item touching `mcp/` or a top-level file) |
| Contract changes | 30 (`beats.json` bar labels), 33 (`light_change` rows, `bar_features.json`, producers), 36 (`vocal_cadence.json` source tier) |
| Pre-existing failures | `docker compose run --rm test` 223 pass; `ui npm run test` 525 pass; `npm run build` ok; MCP `smoke-test` 29/29 and `full-regression` 59/59 pass. **Visual suite: 50 of 58 specs fail on HEAD, one cause**: the `Bar Features` and `Light Changes` proposal lanes (v3.12 items 1–2) request `reference/proposals/bar_features.json` and `light_changes.json`, which the `RegFull - Fixture` has not got, so every spec that asserts no failed response gets two 404s (e.g. `song-full`, `timeline-zoom`, `timeline-scrolled`, `verdict-checks`, `phrases`, `filter-sweep`, `hint-drag`, `left-panel`, `header-readout`). 6 specs pass, 2 did not run. Item 35 moves both lanes to published files and adds fixtures, which clears it; not fixed earlier. |
| Decisions | D0 (resolved): the operator told this session to push; each item is pushed to `origin v3.12` after its commit. D1 (item 29): Medicine `kick_present` is right on 13 of 14 bars (9–17 present, 19–22 absent) and **misses bar 18**: its drum-roll hits are low-end bumps with a click ≤ 4 dB, and lowering the click gate far enough admits the bass hits in bars 20–21. Accepted, not tuned further. Thresholds `CLICK_DB` 6.5, `CLICK_MIN_DB` 4.0, `PRESENT_MIN_CONF` 0.25, the +50 ms bin shift and the short-bar rule were chosen on Medicine (not held out). Agreement with `drum_events` kicks ±50 ms, mean of 27 songs: precision 0.44, recall 0.32 (omnizart over-labels toms and snares, so a cross-check only); recall near zero on Armin, Sash, StealTheShow, Charli-VonDutch, ChangedTheWayYouKissMe where a hat bed hides the click. Corpus: 6,767 attacks (68/min), 715 echoes, 35% off-grid.  D2 (item 30, **gate not met, not promoted**): `experiments/downbeat_reanchor` scores downbeat F1 @ +-70 ms on the 5 Moises songs **0.024** (confidence-bearing downbeats, the incumbent's convention) / **0.163** (all downbeats) vs allin1 0.343 and `downbeat_anchors` 0.301, with 0 bars != 4 beats outside `off_grid_spans` (47 on today's grid; 74 counting the song-edge partials). Zero irregular bars is met by construction (one phase per trusted run) and is what costs the F1: *Armin* has a real 1-beat slip inside one trusted run, and the votes are thin (kick phase alone 0.000). `timing.py`, `artifacts.md` and `downstream-contract.md` untouched; **items 32+ proceed on the old grid**. No threshold was tuned on Medicine, Armin, ayuni or Charli-VonDutch (a post-hoc 24-point grid reached at most 0.166, not adopted). Possible follow-up outside this plan: let the phase change only inside an unresolved span. D3 (item 31): `experiments/filter_sweep_v2` — Armin bars 51–58 `opening` (covers 55–58; the trailing window starts early), end at bar 59 (109.39 s) `aftermath: gap`; Medicine bars 7–15 `opening` (bar 16 is the 1-beat grid slip, no state, so 9–15 not 9–16), end at bar 16 `aftermath: drop`; ayuni 2 sweeps and Charli-VonDutch 2 sweeps (old detector 0), listed in `experiments/filter_sweep_v2/out/score.txt` for operator review. Corpus 131 sweeps (1.3/min vs v1 79), 65% with `aftermath: none` (halved confidence). Resonant peak Hz is reported but drives nothing (jumps between chord tones); state comes from the high/low ratio and the 99% rolloff. Thresholds `HL_SLOPE` 1.5, `ROLL_SLOPE` 0.15, `MIN_CONS` 0.6, `DROPOUT_DB` 6, `MIN_RUN_BARS` 3, `HOLE_RATIO` 0.75, `DROP_RATIO` 1.25 were chosen on Armin and Medicine (not held out); the dropout rule flatters the Armin check by construction. Run order: filter_sweep_v2 compute, export, then bar_features. |

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

- [ ] Stage builds the per-bar table (plus items 29 and 31 columns) and writes `artifacts/light_changes/bar_features.json` and `artifacts/light_changes/light_changes.json`.
- [ ] Point time = the beat where the change physically starts (half-beat table, within ± one beat of the bar edge), snapped to the beat grid. Fixes Charli's off-bar points.
- [ ] Item 31's sweep state is a detector input; Armin bar 55 is the target.
- [ ] Roles as in the experiment; unclaimed → `unknown`, never a guessed role.
- [ ] Tests: ported experiment tests + a fixture where the half-beat refinement moves a point.

**Checks**
- [ ] `docker compose run --rm test`; stage re-run on the validation set: all 8 targets within one beat, roles right, Medicine 10–14 empty; corpus rate reported vs the experiment's 4.7/min.

---

## 33. Publish texture and light changes

Refinement item 6.

- [ ] `song_event_timeline.json` gains rows `{type: "light_change", role, start_time, end_time: start_time, confidence, section_id}`; `field_sources` producer `light_changes`.
- [ ] New required top-level `bar_features.json`: `{schema_version, song_name, field_sources, bars[]}`, each `{bar, start, end, irregular, brightness, transient_density, kick_present, sweep_state, light_change_role}` — the slim projection, not the experiment's full row.
- [ ] `mcp/loaders` hard-require list gains `bar_features.json` (no degraded mode).

**Contract**
- [ ] `artifacts.md` (rows + `field_sources`), `downstream-contract.md` (new file, new row type, producers `light_changes`), `mcp-definition.md` file list.

**Checks**
- [ ] `docker compose run --rm test`; MCP `smoke-test`.

---

## 34. MCP projection

Refinement item 6.

- [ ] `get_song_overview`: a `light_changes` block, one compact row per point `{time, role}` (no `position`, per the overview's byte budget); `scope: "brief"` keeps only the count.
- [ ] `get_detail` structural view: `bar_texture` rows for bars in the span, each with `position`; `light_change` rows with `position`.
- [ ] Golden fixtures and the overview byte budget updated; budget growth stated in Status → Decisions.

**Checks**
- [ ] MCP `smoke-test` + `full-regression`; `get_detail` over Medicine bars 8–20 shows groove_in, build and break.

---

## 35. Debugger lanes from published files

Items 1, 2, 6. Lanes "Bar Features" and "Light Changes" read the published files instead of `reference/proposals/`; "Kick Attacks" and "Filter Sweeps v2" stay proposal lanes (flask badge).

- [ ] `ui/src/data/paths.ts`: lanes read `bar_features.json` and `song_event_timeline.json` `light_change` rows; flask badge removed from both.
- [ ] Fixtures: `RegFull - Fixture` gains `bar_features.json` (≥ 8 bars, one `irregular`) and 3 `light_change` rows (`groove_in`, `build`, `drop`); `RegPartial - Fixture` gets none.
- [ ] `tests/ui-visual` BADGED list and baselines updated; one-line justification per re-captured baseline in the commit message.

**Visual QA** (surface `song-full`, `/?song=RegFull - Fixture`, viewport and readiness per the guide)
- [ ] No `console.error` / `console.warn`, no `pageerror`, no failed response except the guide's named allowed 404s.
- [ ] Lane "Light Changes" present, exactly 3 markers, labels `groove_in`, `build`, `drop` in time order.
- [ ] Each marker's x within 2 px of the ruler x for its `start_time`.
- [ ] Lane "Bar Features" block count = fixture bar count; the `irregular` bar is drawn grey; the last block's right edge within 4 px of its `end` on the ruler.
- [ ] `song-partial`: neither lane drawn, no empty header.
- [ ] Diff `song-full`, `timeline-scrolled`, `timeline-zoomed-out` baselines; masks as in the guide.

**Checks**
- [ ] `docker compose run --rm ui npm run test` / `npm run build`; visual suite green.

---

## 36. Vocal cadence from word onsets

Refinement item 7.

- [ ] `vocal_cadence.py`: when neither `reference/human/lyrics.json` nor `reference/moises/lyrics.json` exists, build `lines` from `artifacts/whisperx-vad/vocal_onsets.json` **times only**: a line breaks at a rest ≥ 1 beat. Word text is never read. `calls` stay `[]` (no call marker without lyrics) with `reason` saying so.
- [ ] `source: "word_onsets"` (third tier); producer vocabulary gains it.
- [ ] Gate: on the songs with lyrics, onset-derived line starts vs lyric line starts, F1 @ ± one beat. Ship the tier only if F1 ≥ 0.7; otherwise a `D` item, `source: null` as today.
- [ ] Tests: tier precedence, rest-split, no text in output.

**Contract**
- [ ] `artifacts.md`, `downstream-contract.md`: third `source` tier.

**Checks**
- [ ] `docker compose run --rm test`; MCP `smoke-test`; count of songs gaining lines.

---

## 37. Corpus run and validation

- [ ] Re-run the pipeline on all 27 songs.
- [ ] Record in this item: validation-set hit/miss table (time and bar landed, role), corpus points/min, roles distribution, irregular-bar count before/after item 30, sweeps found per song.
- [ ] Operator lane review list: ayuni, Charli-VonDutch bar placement; any song above 8 points/min.

**Checks**
- [ ] MCP `full-regression`; `docker compose run --rm test`.

---

## 38. Close-out

- [ ] `CLAUDE.md` state table, `analysis-definition.md`, `mcp-definition.md`, `downstream-contract.md`, `artifacts.md`, `ui-definition.md`, `experiments.md` (promoted entries → archive): current state after items 29–37.
- [ ] Refinement doc: shipped items dropped.
- [ ] Status → "Done", then mark this plan implemented.
