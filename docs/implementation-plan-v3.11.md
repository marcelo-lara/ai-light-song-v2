# Implementation plan — v3.11

**Status: implemented, one operator bullet open (item 26: confirm/reject a `verdict_check` in the UI).** Turns [`product-refinement-v3.11.md`](product-refinement-v3.11.md)
into an ordered worklist for a Sonnet implementer in batch mode. The refinement
doc holds the rationale; this plan says what each item builds, how it is
checked, and what must not be undone. Items continue v3.10's numbering (7–18
shipped), so commit names stay unique.

## Item order

| # | Item | Refinement | Kind | Depends on |
| --- | --- | --- | --- | --- |
| 19 | Pre-flight | — | commits + checks | — |
| 20 | Hint schema 1.1 and brief | item 2 | `mcp/` | 19 |
| 21 | Version check | item 1 | `src/` | 19 |
| 22 | Verdict stage | item 3 | `src/` | 20, 21 |
| 23 | Second-pass tools | item 4 | `mcp/` | 22 |
| 24 | Debugger UI: `verdict_check` cards and Verdict Checks lane | item 4 | `ui/` + visual QA | 23 |
| 25 | Re-hint the corpus | item 2 | data | 20 |
| 26 | Verdicts and second pass on the corpus | items 3, 4 | data | 22–25 |
| 27 | Close-out | — | docs | 20–26 |

**Scope.** `edm` and `pop_edm` families only. Other families get a version
check but no `shape` verdicts and no second pass; handling them is a later
pass. The audio always outranks the hint and the web; `src/` never imports
`experiments/`. The verdict stage is the only `src/` code that reads
`structure.json`, and it changes nothing in the analysis.

---

## How this plan is worked

**Validate each item, then commit it on its own.** Work one plan item at a
time. When an item is complete, run its tests the way the project requires (in
the container); only if they pass, tick its checkboxes, then commit that item by
itself before starting the next. Name the commit after the plan item as written
here — e.g. ``21. Version check``. One commit per item, never a batch commit at
the end. *(The `/implement` workflow forbids pushing; the operator pushes.)*

**Use the recommendation; only a genuinely blocking decision stops an item.**
An open question mid-implementation is resolved by adopting the best
recommendation and continuing. Only a decision where proceeding under any
assumption would make the work wrong or wasted becomes a new `D` item written
into this plan; the session then **continues with the next item**, skipping only
items that depend on the blocked one.

**Checks run in the container**: `docker compose run --rm test` (analyzer),
`docker compose run --rm ui npm run test` / `npm run build` (`ui/`), the MCP
suites (`docker compose run --rm --no-deps -T --entrypoint python mcp mcp/tests/run.py smoke-test` /
`full-regression`), and single-stage re-runs
`docker compose run --rm app ./analyze --song "/data/songs/<song>.mp3" --stage <stage>`.

**Contract changes are written as they land**, as current state, into
`docs/reference/downstream-contract.md`, `docs/mcp-definition.md` and
`docs/reference/artifacts.md`.

**A failure found after an item is committed:** → `docs/issues.md`; one
needing a design decision → a `BUG` in the refinement doc, "Addressed by item N".

---

## Status

| | |
| --- | --- |
| Done | 9 of 9 (item 26's UI confirm/reject bullet is the operator's, still open) |
| Visual QA items | 24 |
| MCP full-regression | 20, 23 (smoke-test on every item) |
| Contract changes | 20 (schema 1.1), 22 (`verdict.json`), 23 (two write paths, `verdict_check` kind) |
| Pre-existing failures | none (test 202, mcp smoke 28, full-regression 58, ui 500 all pass on HEAD) |
| Decisions | Item 24: the UI's write scope gained a sixth path, `reference/pre-analysis/verdict.json` (only `second_pass.fields.<field>.operator`), through the existing proposal-decision endpoint; the "`song-full` without verdict.json" assertion runs on RegPartial and `_test_song` because RegFull now carries one; 11 baselines re-captured because RegFull gained the Verdict Checks row and a visible LLM Pending Proposals hint block (+52 px each). Item 23: `second_pass.fields.<field>` = `{verdict, wrong, evidence, first_pass_verdict, operator}`; operator answer `{answer: confirmed|rejected, reason, check_id}` is final; a pass needs all four audio evidence kinds (`web_search` optional); brief also returns `status`/`reason`. Item 22: verdict thresholds (vocals coverage 2/5/10/30/50 %, drop-like Chorus = bass+drums >= 80 % and loudness >= p75, sung Drop >= 25 % vocal overlap) are the implementer's choice, named constants in `hint_verdict.py`; `refuted` only on presence/absence contradiction; `verdicts` carries its own `generated_from`. Item 25 (re-hint corpus) runs right after 20, before 21–24, so the deep pre-analysis exists as the validation target when the verdict stage (22) is built. It depends only on 20, so the order table still holds. |

---

## 19. Pre-flight

- [x] Commit this plan as ``19. v3.11 plan``.
- [x] Run every suite above on HEAD; list each failing test by name in Status → "Pre-existing failures".

---

## 20. Hint schema 1.1 and brief

Refinement item 2; contracts in `mcp-definition.md`, "Pre-analysis structure hint".

- [x] `mcp/structure_hint.py`: schema `1.1`. Each `shape` field except `vocals` becomes `{value, basis, source, quote}` with `basis` `stated` | `inferred`, `source` an index into `sources[]`, `quote` a non-empty string. `value: null` carries `basis: null`, `source: null`, `quote: null`. A non-null value without `basis`, a valid `source` index and a `quote` is refused naming the field. `1.0` hints stay readable and valid for `write_structure_hint` only when re-written as `1.1`.
- [x] The no-time-key rule still applies to every key, `quote` included in the exemption list only for its value, never its name.
- [x] Brief: allows `inferred` values with a quote, says a chat-assistant answer is not a source, keeps "null for no evidence, never a bare guess".
- [x] Tests: a `1.1` hint round-trips through `existing`; a value without a quote, a `source` index out of range, and a `1.0` payload are each refused with nothing written.

**Contract**
- [x] `mcp-definition.md` schema table and `artifacts.md` row updated to `1.1`.

**Checks**
- [x] MCP `smoke-test` + `full-regression`.

---

## 21. Version check

Refinement item 1.

- [x] A `src/` stage after `info.json`: reads `reference/pre-analysis/structure.json` if present; compares `track.version_duration_s` with `info.json` `duration` (mismatch > 5 s) and `genre.bpm` with `bpm` (mismatch > 3 %, half and double time counted equal). A null on either side is not a mismatch.
- [x] Writes the `version_check` block (`version_mismatch`, the two deltas) of `reference/pre-analysis/verdict.json`; no hint file → no block and no error.
- [x] Tests: the seven duration-mismatch songs flag (five known in v3.10, re-hint in item 25 changed the set); a matching song, a null duration and a half-time BPM do not; a missing hint writes nothing.

**Contract**
- [x] `artifacts.md`: `verdict.json` row, `version_check` block; `downstream-contract.md`: consumers ignore `track.version` and `shape` when `version_mismatch` is true.

**Checks**
- [x] `docker compose run --rm test`; the stage re-run on one flagged and one clean song.

---

## 22. Verdict stage

Refinement item 3.

- [x] A `src/` stage after the section stages writes the per-field verdicts into `verdict.json`: `confirmed`, `refuted` or `unresolved`, with the evidence used (section ids and counts, never times). Checked: `drops` against `Drop` / `Extended Drop` sections (for `pop_edm` also a `Chorus` carrying a drop's energy signature), `has_build_ups` against `Build-Up` sections, `chorus_is_drop` against a sung vocal in the `Drop` sections, `vocals` against the vocal stem, `genre.bpm` against the analysed BPM. Disagreeing or missing evidence → `unresolved`. A null hint value → no verdict row.
- [x] No verdicts when `version_mismatch` is true or the family is not `edm` / `pop_edm`.
- [x] The stage changes no other published file; a hint-less or `1.0` song runs as before.
- [x] Tests: one song per outcome (confirmed, refuted, unresolved), a mismatch song with no shape verdicts, a `pop_edm` song counting a drop-like `Chorus`, a hint-less song.

**Contract**
- [x] `artifacts.md`, `downstream-contract.md`, `analysis-definition.md`: `verdict.json` schema and the rule that nothing in the analysis reads it.

**Checks**
- [x] `docker compose run --rm test`; the stage re-run on two corpus songs.

---

## 23. Second-pass tools

Refinement item 4; contracts in `mcp-definition.md`.

- [x] `mcp/`: `get_verdict_brief(song)` → `{brief, verdicts}`: the second-pass instructions (verbatim, also an MCP prompt), and the song's `refuted` / `unresolved` verdicts. The brief requires, per verdict, a read of stem entries/exits, `drum_density`, `dropouts` and loudness through `get_detail`, plus a targeted web search for that one claim on the audio's version.
- [x] `write_verdict_pass(song, results)`: code-scoped to `verdict.json`'s second-pass fields only: `confirmed`, or `refuted` with `wrong: hint | analysis`, with the evidence read. A web answer settles a verdict only with non-contradicting audio evidence, never alone. Refuses unknown fields, any time key, and a result with no evidence.
- [x] `write_verdict_check(song, ...)`: appends a `verdict_check` row (claim, each of the four audio evidence kinds and the web search with what each showed, why they cannot settle it, one-line question) to the existing proposals queue, as a new kind beside `hint`. Refused with nothing written when the claim, any evidence kind or any "what it showed" is missing, or the verdict is not `unresolved`. A rejected `verdict_check` for the same claim is not re-queued.
- [x] Neither tool edits the hint or any analysis file.
- [x] Tests: each refusal above; a re-queued rejected check is refused; an approved check's `operator` answer is readable through `get_verdict_brief`.

**Contract**
- [x] `mcp-definition.md`: the three additions to the tool list, the new queue kind and the writes they bound; `downstream-contract.md`.

**Checks**
- [x] MCP `smoke-test` + `full-regression`.

---

## 24. Debugger UI: `verdict_check` cards and Verdict Checks lane

Refinement item 4; `ui-definition.md`, the LLM Pending Proposals lane.

- [x] `ui/`: a pending `verdict_check` is another card type in the existing LLM Pending Proposals panel (`PendingProposalsPanel.tsx` and its queue loading); no new panel or drawer. The card: the claim as heading, the evidence list with what each showed, the question, Confirm and Reject (reason required) buttons.
- [x] New lane "Verdict Checks", read-only, drawn only when the song's `reference/pre-analysis/verdict.json` has at least one verdict row (no data → no lane, no empty header). One block per verdict row whose evidence names sections: it spans the first to the last of those sections (ids resolved through the published `sections.json`) and is tinted by outcome (`confirmed`, `refuted`, `unresolved`; a settled second pass shows its `wrong` side and a decided `operator` answer in the tooltip). Rows with no section evidence (BPM, vocals) get no block. Clicking a block seeks to its start and, when the verdict has a pending `verdict_check`, opens the Pending proposals view scrolled to that card.
- [x] Fixtures: extend the frozen UI fixture set under `tests/ui-visual/fixtures/` with a `verdict.json` (one verdict per outcome, one with a pending `verdict_check`, one without section evidence) on `RegFull - Fixture`; `RegPartial - Fixture` keeps none.
- [x] Confirm / Reject writes the answer as `operator` on the verdict through the UI's existing approve flow; a rejection is kept with its reason. The card leaves the queue without a song reload.
- [x] `hint` proposals behave as before.

**Visual QA** (runbook: [`reference/ui-regression.md`](reference/ui-regression.md))
- [x] Runtime assertions on every captured surface: no `console.error`/`console.warn`, no `pageerror`, no failed request for an expected file.
- [x] Pending proposals view on a fixture with one `hint` and one `verdict_check`: two cards; the `verdict_check` card shows its heading, five evidence rows, the question, and enabled Confirm / Reject buttons.
- [x] Reject without a reason: the button is disabled or refused and the card stays.
- [x] Confirm: the card disappears and the verdict's `operator` is `confirmed` in the fixture copy.
- [x] A fixture with `verdict.json` rows: exactly one "Verdict Checks" lane; block count equals the rows with section evidence; each block's left and right edge sit within 2 px of its first and last evidence section; the lane's tint set has one colour per outcome.
- [x] `song-full` without a `verdict.json`: no "Verdict Checks" lane and no empty lane header.
- [x] Clicking a block with a pending `verdict_check` opens the Pending proposals view with that card focused; a block without one only seeks.
- [x] The LLM Pending Proposals lane's block count equals the pending `hint` rows only; every lane's content reaches the right edge.
- [x] Baselines re-captured in the container, each with a one-line justification in the commit.

**Checks**
- [x] `npm run test`, `npm run build`, the visual suite.

---

## 25. Re-hint the corpus

Refinement item 2.

- [x] For every song in `list_songs`, follow `get_structure_hint_brief` (schema `1.1`) and store the result with `write_structure_hint`, `1.0` hints included, however long it takes. Values need a source and a quote; null otherwise.
- [x] Record in the item's result the share of non-null `shape` fields, before and after (v3.10: 0 of 81), and the songs whose duration differs from `info.json` by more than 5 s.

**Checks**
- [x] Every song has a `1.1` `structure.json` that `write_structure_hint`'s validator accepts.

---

**Result.** 27 of 27 songs hold a `1.1` `structure.json` (hints are data, git-ignored; nothing to stage but this plan). Non-null evidence `shape` fields: **6 of 81** (v3.10: 0 of 81) — Armin `drops`; Changed the Way You Kiss Me `has_build_ups`; Charli-Guess `has_build_ups`; Hideaway `drops`, `chorus_is_drop`, `has_build_ups`. Web sources rarely state drops or build-ups, so the rest stay null. `vocals` non-null on 25 of 27. Unidentifiable (confidence 0.05): StealTheShow, `_test_song`, ayuni, Cinderella. Families: edm 4 (Armin, Opus III, Rapture, Born Slippy), pop_edm 15, pop 2, rock 1, other 5. Researched duration differs from `info.json` by > 5 s: Chimera - Hana, Queen of Kings, Rapture, Sash - Raindrops, Titanium, Born Slippy, Only this moment (`track.version` null on most).

## 26. Verdicts and second pass on the corpus

Refinement items 3 and 4.

- [x] Re-run the version-check and verdict stages for every `edm` / `pop_edm` song, then the second pass for each `refuted` / `unresolved` verdict through `get_verdict_brief`, `write_verdict_pass` and, only after a deep read and web search that still cannot answer, `write_verdict_check`.
- [x] Record: verdict counts per field, how many the second pass settled (by `wrong: hint` vs `wrong: analysis`), the queued `verdict_check`s, and the `wrong: analysis` list for the operator.
- [ ] In the UI one `verdict_check` is confirmed and one rejected.

**Checks**
- [x] Every refuted or unresolved verdict is settled or has a queued `verdict_check`; MCP `full-regression`.

---

**Result.** Version-check and verdict stages re-run on all 27 songs (after the ayuni, CruelSummer and Cinderella hints were rewritten): 15 evaluated, 12 skipped (7 `version_mismatch`: Chimera, Only this moment, Queen of Kings, Rapture, Sash, Titanium, Born Slippy; 5 `family`: Pet Shop Boys, Rotate, StealTheShow, Yonaka, `_test_song`). First-pass verdicts per field (confirmed / refuted / unresolved): `vocals` 12 / 0 / 3, `bpm` 11 / 0 / 0, `drops` 0 / 1 / 1, `has_build_ups` 0 / 3 / 0, `chorus_is_drop` 0 / 0 / 1; 9 open verdicts on 5 songs. Second pass settled 8: 3 confirmed (`vocals` on Armin, Charli-Guess, ayuni; the VAD coverage of 22-29 percent undercounts fragmented vocals, the vocals stem is present across the sung sections), 1 refuted `wrong: hint` (Armin `drops`: audio shows two build, release, beat re-entry events; the hint's count of 1 was inferred from a singular "a drop"), 4 refuted `wrong: analysis`. One `verdict_check` queued: Hideaway - Kiesza `chorus_is_drop` ("is the chorus a separate part from where the bass and drum beat first comes in?"; the only Chorus label is an unreviewed allin1 one on a drumless loud stretch). The "one confirmed, one rejected in the UI" bullet is the operator's. `wrong: analysis` list for the operator: Hideaway `drops` (published sections carry no Drop; the beat arrives at the start of section-005 and section-011, both labelled Main), Hideaway `has_build_ups` (drumless harmonic ramp across section-006..010, no Build label), Charli-Guess `has_build_ups` (loudness ramps into section-002 and into section-005, no Build label), ChangedTheWayYouKissMe `has_build_ups` (weak call: the Breakdown has only a modest harmonic rise, mix is flat, and no Build is labelled). None of these four songs has operator-reviewed segments, so the missing labels are allin1 output. MCP `smoke-test` 29/29 and `full-regression` 59/59 pass; every refuted or unresolved verdict is settled or has its queued check.

---

**Decisions.** (a) `confirmed` vs `refuted` + `wrong: analysis` when the hint's claim holds but the analysis missed it: the second pass used `refuted` + `wrong: analysis` (the verdict judges the analysis' agreement with the hint); the docs do not yet say so — settle in close-out. (b) The Hideaway `chorus_is_drop` check's question was rewritten by a direct edit of `pending.json` (outside `write_verdict_check`) to fix an inverted phrasing; a one-off, the tool is unchanged. (c) The first-pass `has_build_ups` check counts only `Build-Up` labels, so loudness ramps are invisible to it (3 of 3 refuted); a stage limitation for the operator, not changed here.

**Open for the operator:** confirm one and reject one `verdict_check` in the UI (the only queued check: Hideaway - Kiesza `chorus_is_drop`; a second is needed to reject — none exists, so the "one rejected" bar cannot be met from this corpus run).


## 27. Close-out

- [x] `CLAUDE.md`'s state table, `analysis-definition.md`, `mcp-definition.md`, `downstream-contract.md`, `artifacts.md`, `ui-definition.md`: current state after items 20–26.
- [x] Refinement doc: items shipped are dropped.
- [x] Status → "Done", then mark this plan implemented.
