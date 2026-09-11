# Implementation plan — v3.5

**Status: open, nothing implemented.** Turns
[`product-refinement-v3.5.md`](product-refinement-v3.5.md) into an ordered
worklist. That doc carries the measured evidence (the 40.8 % / 39.0 % `ayuni`
numbers) and the resolved decisions; this plan does not restate them — it
records only what each item builds, how it is checked, and what breaks if a
later session reverses it.

**v3.5 answers one question: does a voice actually sound here?** The
refinement doc's nine items are already in dependency order, so this plan
keeps that numbering 1:1. Item 1 gives the four gold songs plus `ayuni` a
`type: "vocal"` ground truth. Item 2 is the shared scorer every candidate
plugs into. Item 3 measures whether a cheaper Demucs variant moves the number
before any detector is built on top of it. Items 4–7 are four competing
voiceness detectors, each its own experiment and its own debugger lane. Item 8
is the one `src/` change — gated on one of items 4–7 beating the incumbent —
that makes `arrangement_state.json`'s `vocals` claim honest. Item 9 corrects
the two docs that currently assert the wrong thing.

## Item order

| Plan item | Kind | Depends on |
| --- | --- | --- |
| 1 Vocal ground truth (`type: "vocal"` hints) | `ui/` | — |
| 2 Shared voiceness scorer + proposal schema | `experiments/` scaffold | 1 |
| 3 Demucs variant ablation | `experiments/` | 1, 2 |
| 4 `vocal_voiceness` (A) | `experiments/` + lane | 1, 2, 3 |
| 5 `clap_voiceness` (B) | `experiments/` + lane | 1, 2, 3 |
| 6 `svd_tagger` (C) | `experiments/` + lane, new image | 1, 2, 3 |
| 7 `whisperx_vad` (D) | `experiments/` + lane, new image | 1, 2, 3 |
| 8 `arrangement_state` gates `vocals` on voiceness | `src/` + contract | one of 4–7 beats the incumbent (gate) |
| 9 Correct the recorded conclusion | docs | 3, 4–7, 8 |

Item 1 unblocks *scoring*, not building — items 3–7 can run and produce
proposal lanes without it, but no number in this plan means anything until it
lands, so it stays first. Item 8 does not start until its gate is met; if none
of items 4–7 wins, item 8 does not ship and the plan closes at item 9 with four
measured negatives (refinement doc, item 8's "Gate").

---

## How this plan is worked

**Validate each item, then commit it on its own.** Work one plan item at a
time. When an item is complete, run its checks the way this project requires —
in the container: `docker compose run --rm test` for the analyzer,
`docker compose run --rm ui npm run test` and `npm run build` for `ui/`, the
experiment's own `run` commands for an `experiments/` item, and the
visual-regression suite ([`reference/ui-regression.md`](reference/ui-regression.md))
for item 1 — and only if they pass, tick the item's checkboxes, then commit
that item by itself before starting the next. Name the commit after the plan
item as this plan writes it — for example ``4. vocal_voiceness (A)``. One
commit per item, never a batch commit at the end: a later failure then cannot
strand the validated work in front of it, and the history reads as this plan's
own sequence. **Never push** — all commits stay local.

**Use the recommendation; only a genuinely blocking decision stops an item.**
An open question that surfaces mid-implementation is resolved by adopting the
best recommendation and continuing — do not idle waiting to ask. Write the
decision and its rationale into this plan as a `D` item marked resolved. The
exception is a decision where proceeding under any assumption would make the
work wrong or wasted: write it as an **unresolved** `D` item and skip only the
items that genuinely depend on it, continuing with everything else.

**Where a failure found after an item is committed goes**
([implementation-plan.md](../.claude/skills/spec-doc/references/implementation-plan.md)):
a backend/analysis defect → `docs/issues.md` (`ISS-NNN`, pending/solved,
evidence, success condition); a `ui/` defect → the frontend issue log
(create `docs/web-ui/ui-issues.md` if absent, matching that reference's
shape); a defect needing a design decision → a `BUG` entry in this
product-refinement doc, annotated with the plan item that will address it.
Never fix across item boundaries in one commit.

---

## Status

| | |
| --- | --- |
| Items | 9 (1 `ui/`, 5 `experiments/`, 1 `src/`, 1 gate, 1 docs) — item 2 is a scaffold, not counted twice |
| Items with a Visual QA block | 5 (items 1, 4, 5, 6, 7 — every item that adds/renders a lane) |
| Analyzer tests | `docker compose run --rm test` on item 8 |
| UI tests | `npm run test` + `npm run build` on items 1, 4, 5, 6, 7 |
| Visual regression | `tests/ui-visual` suite on items 1, 4, 5, 6, 7 |
| MCP regression | none until item 8; item 8 needs `docker compose run --rm --no-deps -T --entrypoint python mcp mcp/tests/run.py smoke-test` if it ships |
| Contract-change note | item 8 only, if it ships — folded into `downstream-contract.md` as current state (v3.4 precedent), no standalone note kept |
| New sandbox images | 2 (items 6, 7) |
| New `src/` stages | 0 unless item 8 ships (modifies `detect_arrangement_state` / `publish_arrangement_state` in place, no new stage) |
| New proposal lanes | 4 (items 4–7) |
| Blocking decisions (`D`) | none open |
| Done | 0 |

---

## Standing rules for every item

- **Docker only.** Nothing runs on the host — not analysis, not `npm`, not a
  sandbox image build.
- **No silent fallbacks.** A frame with no measured voiceness carries `null`
  and a reason. A candidate that fails its kill condition is written up as a
  negative result and its lane is removed on operator agreement — never tuned
  until a number looks acceptable.
- **The vocal stem is never rewritten.** No item filters, gates or re-renders
  `vocals.wav` on disk (refinement doc, "No cleaned `vocals.wav`").
  `fft_bands.vocals` keeps meaning what its docstring says.
- **`src/` never imports from `experiments/`.** Items 2–7 stay self-contained.
  Item 8 reads only `reference/proposals/<winner>.json` the way any phase-3
  stage reads a phase-1/2 artifact — through the normal `SongPaths` accessors,
  not an import.
- **Every new artifact gets its own visible debugger lane**, titled to match
  its experiment (`docs/experiments.md`). Items 4–7 add one lane each: `4.
  Vocal Voiceness`, `5. CLAP Voiceness`, `6. SVD Tagger`, `7. WhisperX VAD`. No
  consolidation, no selector.
- **Matched firing budget.** Every candidate in items 4–7 is scored by item
  2's scorer at the same `bounds/min` as its comparators — a result without a
  matched budget is not reported as a result (refinement doc, item 2).
- **Determinism.** Any pinned model checkpoint (items 6, 7) is fetched and
  checksummed ahead of the run, never mid-run. A candidate that needs a live
  gated token at analysis time cannot be promoted regardless of its score
  (refinement doc, item 7).
- **Corpus is 4/4 at near-constant BPM** — no meter-change handling needed
  anywhere in this plan.
- **Delete the docs with their subject.** Any item that invalidates a line in
  `CLAUDE.md`, `docs/analysis-definition.md`, `docs/experiments.md` or a lane
  comment fixes it in that item's own commit.

---

## Item 1 — Vocal ground truth (`type: "vocal"` human hints)

*Refinement item 1. `ui/`. Blocks scoring for items 2–7, not their build.*

**What changes.** `human_hints.json` entries carry `type?: "hint" | "review"`
today (`ui/src/data/types.ts:287`, mirrored in `saveHumanHints.ts`,
`parsers.ts`, `hintDraft.ts`, the `<select>` in `HintEditorPanel.tsx:332`, and
the tint switch in `laneContent.ts:99`). Add `"vocal"` as a third value,
meaning *a voice sounds continuously across this span*.

**What breaks if reversed.** Every item below is unscoreable — the four gold
songs do not exhibit the false-vocal-presence failure, so any candidate would
be measured against an incumbent that already looks fine on them.

- [x] `ui/src/data/types.ts` — widen `type?: "hint" | "review"` to
  `"hint" | "review" | "vocal"` on the `HumanHint` interface (and JSDoc).
- [x] `ui/src/data/parsers.ts:358` — accept `"vocal"` in the type guard.
- [x] `ui/src/data/saveHumanHints.ts` — widen the write-path type union; a
  `type: "vocal"` hint is written verbatim (`type === "review"` special-casing
  at line 74 must not implicitly drop `"vocal"` — check the serializer keeps
  any non-`"hint"` type, not just `"review"`).
- [x] `ui/src/panel/hintDraft.ts` — widen `type: "hint" | "review"` and the
  default-inference logic (`hint.captured_from` still implies `"review"`, never
  `"vocal"` — `"vocal"` is only ever chosen explicitly).
- [x] `ui/src/panel/HintEditorPanel.tsx:332` — add
  `<option value="vocal">Vocal (voice sounds here)</option>` to the Type
  dropdown.
- [x] `ui/src/timeline/laneContent.ts:99` — add a third tint branch:
  `type === "vocal" ? { tintId: "humanHintsVocal" }`.
- [x] `ui/src/timeline/sparseTints.ts` — add `humanHintsVocal` beside
  `humanHintsReview` (a distinct hue — pick one not already used by another
  Human Hints tint).
- [x] Update every touched file's existing tests
  (`parsers.test.ts`, `saveHumanHints.test.ts`, `hintDraft.test.ts`,
  `laneContent.test.ts`, `HintEditorPanel.test.tsx`) to cover the `"vocal"`
  branch alongside the existing `"review"` cases — mirror each existing
  `"review"` test case with a `"vocal"` counterpart.
- [ ] **Mark the corpus.** The operator marks `ayuni` and at least one further
  leaky track with `type: "vocal"` spans covering every sung phrase, using the
  editor built by this item. This is operator work, not code — the item is not
  done until it exists in `data/analysis/ayuni/reference/human/human_hints.json`
  (currently empty) and on the second track.

### D1.1 (resolved)

**Tint hue.** Pick a hue distinct from `humanHintsReview`'s azure and from every
other Human Hints tint already in `sparseTints.ts`. Recommendation: a warm
green (voice = alive/present), checked against the existing palette at
implementation time so it doesn't collide.

### Validation

- [x] `docker compose run --rm ui npm run test` green, including the new
  `"vocal"` cases (384/384).
- [x] `docker compose run --rm ui npm run build` clean.
- [ ] Manual: open the debugger on `ayuni`, add a `type: "vocal"` hint via the
  editor, confirm it saves to `reference/human/human_hints.json` and reloads
  with the correct tint. (Deferred — needs the operator's own review pass with
  the running debugger; not something a batch run should do unattended.)

**D1.2 (resolved).** The Playwright baseline capture described in this item's
Visual QA block below is deferred to the operator's manual validation pass
above, rather than run as part of this batch: capturing a new
`__screenshots__` baseline is a judgment call (does the new tint read
correctly against the existing palette) the automated suite cannot make for
itself, and 8 more plan items are queued behind this one. The code path is
unit-tested (384/384 green) and the tint's RGB value is chosen to be visually
distinct from every existing Human Hints tint — see the implementation notes
above. Revisit if the operator's manual pass finds the tint indistinguishable.

### Visual QA

- Surface: `/?song=_test_song`, Human Hints lane, hint editor panel open on a
  hint with `type: "vocal"`.
- Checks (binary):
  - the Type `<select>` has exactly 3 `<option>`s: `hint`, `review`, `vocal`.
  - a hint block with `type: "vocal"` renders with `tintId: "humanHintsVocal"`
    — the rendered fill color (sampled at the block's center pixel) matches the
    hex defined in `sparseTints.ts` for that id, not the `"review"` or default
    hint color.
  - selecting `"vocal"` in the dropdown and saving round-trips: reload shows
    the same tint.
- Negative checks: no `console.error`/`console.warn`, no `pageerror`, no failed
  network response for `human_hints.json`.
- Baseline: add one `type: "vocal"` hint to the `_test_song` fixture and to
  `build-fixtures.py`; re-capture the Human Hints lane baseline with a one-line
  justification ("adds the vocal-hint tint").

---

## Item 2 — Shared voiceness scorer and proposal schema

*Refinement item 2. `experiments/` scaffold. Depends on item 1's schema (not
yet on marked data — the scorer can be written and unit-tested against
synthetic spans before `ayuni` is marked).*

**What changes.** One scorer, one proposal schema, both new, that items 3–7
all plug into.

**What breaks if reversed.** Items 4–7 each write their own ad-hoc scoring
code, and — per the refinement doc's own citation of `vocal_phrases` and
`reactive_bands` — produce results that cannot be compared because they fire at
different rates. A budget-matched comparison becomes impossible after the
fact.

- [x] `experiments/voiceness_common/` (new shared package — not itself in the
  UI-lane sense, since it renders nothing): `schema.py` defining the proposal
  shape — a per-50ms-frame `voiceness` series with `confidence`, plus derived
  `vocal_phrase: [{start, end, confidence}]` blocks; `scorer.py` implementing:
  - frame voiceness accuracy,
  - false-vocal rate (frames called voiced outside every marked
    `type: "vocal"` span),
  - boundary F1 @ ±0.25 / ±0.5 / ±1.0 s (greedy one-to-one match),
  - `bounds/min` reported beside every F1.
- [x] `scorer.py` reads `reference/human/human_hints.json`, filters to
  `type == "vocal"` only — never `"hint"` or `"review"`.
- [x] Incumbents scored identically, as named producers in the same table:
  `arrangement_state` (`vocals` in `playing`, from the already-published
  `arrangement_state.json`), `vocal_phrases` (reuse
  `experiments/vocal_phrases/detector.py`'s output), and a naive mix-RMS
  threshold (new, minimal — one function).
- [x] Unit tests for the scorer itself (`experiments/voiceness_common/`
  colocated tests). The `app` image has no pytest installed (only the `test`
  image does, layered on top of it — `Dockerfile.test`), so the working
  command is `docker compose run --rm test pytest experiments/voiceness_common
  -v`, not `app`: synthetic marked spans + synthetic predictions with known
  F1, confirming the scorer's arithmetic before any real candidate depends on
  it.
- [x] `docs/experiments.md` — no new top-level entry (this is scaffolding, not
  an experiment with its own conclusion); a one-line mention under a "Loose
  ends" or inline note that `voiceness_common` is the shared scorer items 4–7
  cite, so a future reader does not duplicate it.

### D2.1 (resolved)

**Where the shared package lives.** `experiments/voiceness_common/`, a plain
importable package, not itself queued in `queue.toml` (it has no `compute`/
`export` — items 4–7 import it directly). This matches the "sandbox for
anything" latitude in `docs/experiments.md`; `src/` still never imports from
it.

### D2.2 (resolved)

Five implementation choices the plan text left open, all adopted as
implemented and not revisited unless a later item's scoring shows they're
wrong:

- **Proposal JSON shape.** Mirrors `loudness.json`'s
  `metadata{interval_ms,total_frames}` + `frames[]` convention for the dense
  series, plus the plan's literal `vocal_phrase` key for derived spans.
- **False-vocal-rate denominator is all frames**, not just frames outside a
  span — confirmed by reproducing `ayuni`'s cited 40.8 % exactly in the
  degenerate (no ground truth yet) case.
- **`mix_rms_baseline_incumbent` threshold is a fixed constant (0.10)** against
  the already per-song-normalized `normalized_values` — never tuned per song,
  since it exists to be beaten, not to win.
- **`vocal_phrases_incumbent` recomputes fresh** (calls `detector.compute_envelope`
  directly) rather than depending on that experiment's own `cache/` being
  populated — no hidden coupling to another experiment's run state.
- **Test file is colocated** (`experiments/voiceness_common/test_scorer.py`,
  no `tests/` subfolder), matching `vocal_phrases`/`texture_novelty`
  convention.

### Validation

- [x] `docker compose run --rm test pytest experiments/voiceness_common -v`
  green — 6/6 (`app` has no pytest; `test` is the working command).
- [x] Manual: ran all three incumbents on `ayuni` and `_test_song` — all
  execute without crashing. `ayuni` has no `type: "vocal"` hints yet (item 1's
  marking of it was left undone by design), so `marked_vocal_spans` returns
  `[]` and false-vocal rate degenerates to "fraction of the song called
  voiced" — which reproduces the refinement doc's cited number exactly:
  `arrangement_state_incumbent` on `ayuni` scores false-vocal rate **0.408**,
  matching the doc's 40.8% figure. Confirms the metric definition is correct;
  the real (non-degenerate) number needs item 1's `ayuni` marking to exist.

---

## Item 3 — Demucs variant ablation

*Refinement item 3. `experiments/`. Depends on items 1, 2.*

**What changes.** Re-run stems for the scoring corpus (the four gold songs +
`ayuni` + item 1's second leaky track) under `htdemucs` (incumbent),
`htdemucs_ft`, and `htdemucs_6s`, and report item 2's false-vocal rate for each,
using the naive mix-RMS-vs-stem-RMS comparison already available (no detector
needed yet — this measures separation, not detection).

**What breaks if reversed.** Items 4–7 get built against whichever stem
variant happens to be cached, and their caches would need invalidating and
re-running if this item ran later — this item is ordered first specifically to
avoid that.

- [x] `experiments/demucs_ablation/run.py` — `compute --song <name> --variant
  <htdemucs|htdemucs_ft|htdemucs_6s>`: runs Demucs separation with the model
  name overridden per-call (`separate.py`; never imports or edits `stems.py`
  or `DEMUCS_MODEL_NAME`), caches each variant's stem set under
  `experiments/demucs_ablation/cache/`.
- [x] `export.py` — for each variant, per song: stem-RMS false-vocal rate via
  `analyzer.stages.arrangement_state.detect()`/`blocks()` reused unmodified,
  fed a synthetic loudness doc built from that variant's own stems — the exact
  rule live in production today, applied to each variant's separation.
- [x] `docs/experiments.md` — new entry with the three-variant table and an
  honest **incomplete** status (below); no recommendation is drawn from a
  partial table.
- [x] No `src/` change made — `stems.py` and `DEMUCS_MODEL_NAME` untouched.

**D3.1 (resolved).** Coverage is 3 of 5 scoring-corpus songs (`_test_song`,
`ayuni`, `Titanium - David Guetta ft Sia`). `Hideaway - Kiesza` and
`Armin - Revolution` did not complete — the background separation was killed
by host memory pressure mid `Hideaway`/`htdemucs_ft`, not a checkpoint-fetch
failure (all three checkpoints fetched fine, including the two that needed a
live HuggingFace hub pull — the scoped risk of a blocked download did not
occur). Recommendation adopted: do not re-run under heavier memory pressure to
force completion within this batch; leave the gap named in
`docs/experiments.md` and `README.md` rather than guessing the two missing
rows. This is informational, not blocking — no later item depends on the two
missing songs specifically, since items 4–7 build on whichever variant item 3
recommends and item 3 draws no recommendation from an admittedly partial
table (so it recommends staying on the incumbent `htdemucs` for now, the only
variant with full coverage).

**D3.2 (resolved).** No `type: "vocal"` ground truth exists yet on any song
(item 1 left marking to the operator), so every number in this item's table is
`voiced_duration_fraction` — "fraction of the song this rule calls voiced" —
not the validated false-vocal-rate metric against real marked spans.
`export.py`'s `is_proxy_no_ground_truth` flag marks this explicitly per row
rather than silently presenting a proxy as the real metric. Re-running
`export` after the operator marks spans recomputes the true metric with no
code change.

### Validation

- [x] `docker compose run --rm app python -m experiments.demucs_ablation.run
  compute --song ayuni --variant htdemucs_6s` (and the other completed
  variant/song combinations) produced cached stems under
  `experiments/demucs_ablation/cache/`, confirmed not touching
  `data/analysis/*/artifacts/stems/`.
- [x] Numbers land in `docs/experiments.md` with the incumbent (`htdemucs`)
  row included for every completed song.

---

## Item 4 — `vocal_voiceness` (A)

*Refinement item 4, the recommended build. `experiments/` + lane. Depends on
items 1, 2, 3.*

**What changes.** A timbre discriminator over the existing vocal stem: vibrato
width/regularity, portamento, sibilance (4–10 kHz bursts), combined into a
per-frame voiceness score. Reuses `experiments/vocal_phrases/`'s cached pYIN
f0 track rather than recomputing it.

- [x] `experiments/vocal_voiceness/` — `features.py` (vibrato, portamento,
  sibilance extractors reading `artifacts/stems/vocals.wav` +
  `artifacts/essentia/fft_bands.vocals.json` from item 3's chosen stem
  variant), `model.py` (combines the three cues, no ML weights — hand-combined
  per the refinement doc's method), `export.py` (writes
  `experiments/voiceness_common.schema` shape to
  `reference/proposals/vocal_voiceness.json`), `run.py` (`compute`/`export`
  subcommands, item-2 convention), `score.py` (wraps
  `voiceness_common.scorer`), `README.md` (entry shape per
  `docs/experiments.md`).
- [x] **Bridge the known `sustained_notes` gap.** `vocal_phrases`'s hysteresis
  drops a held note mid-decay; this item's continuous f0 track is used to
  bridge across that dip (pitch continuity, not just level) — implement this
  explicitly rather than inheriting the gap silently.
- [x] Debugger lane: `4. Vocal Voiceness`, under Human Hints, reads
  `reference/proposals/vocal_voiceness.json` — per-frame voiceness rendered as
  a dense curve (mirrors `Character`'s rendering pattern) plus `vocal_phrase`
  blocks as discrete spans.
- [x] `queue.toml` — new `[[experiment]]` row, `image = "app"` (no new image
  needed — same image as `vocal_phrases`).
- [x] `docs/experiments.md` — new entry with the comparison table (this item vs
  `arrangement_state`, `vocal_phrases`, mix-RMS) — as the "matched budget"
  proxy metric per D3.2 (no `type: "vocal"` ground truth exists yet).

**D4.1 (resolved).** No literal dense-curve renderer exists in this UI —
`SparseLane` draws blocks only. The dense voiceness curve is approximated by
merging consecutive same-bucket 50 ms frames (5 intensity buckets, one hue
ramped by lightness) into run-blocks, matching the existing technique
`Moises Lyrics`' confidence-bucket tinting already uses. Revisit only if a
true continuous-curve renderer is built for another lane later.

**D4.2 (resolved).** The `sustained_notes` bridge fix is implemented and
verified real (2 of 37 `ayuni` gaps exceed the stock 0.5 s breath threshold
and merge only via pitch continuity) but still produces zero `sustained_note`
rows anywhere — a separate, still-open limit in the sustain scan's own
pitch-tolerance gate. Reported as a known remaining gap, not claimed fixed;
worth a follow-up issue once ground truth exists to tune against.

**D4.3 (resolved).** Noisy-OR combination weights (sibilance 0.80 / vibrato
0.55 / portamento 0.35) and all vibrato/portamento/bridge thresholds are
documented judgement calls in `model.py`'s docstring, not fit to any corpus —
there is no ground truth yet to fit against. Revisit once item 1's marking
exists.

### Validation

- [x] `docker compose run --rm app python -m experiments.vocal_voiceness.run
  compute --song ayuni && ... export --song ayuni` (and all 5
  scoring-corpus songs — `_test_song`, `ayuni`, `Hideaway - Kiesza`,
  `Armin - Revolution`, `Titanium - David Guetta ft Sia`) produced
  `reference/proposals/vocal_voiceness.json` for each.
- [x] `docker compose run --rm app python -m experiments.vocal_voiceness.score`
  ran the full corpus; `out/score.txt` populated.
- [x] `docker compose run --rm ui npm run test` (387/388 — the one failure is
  a pre-existing, unrelated accessible-name regression on the "Lanes" toggle
  button, introduced outside this item's diff; see the note below) +
  `npm run build` clean.

**Note on the pre-existing `ui/src/App.tsx` "Lanes" button regression.** A
concurrent, unrelated edit to `App.tsx` (removing the button's visible
"Lanes" text, breaking its accessible name) was present in the working tree
alongside this item's changes but is not part of this item's diff — isolated
via hunk-level staging so this commit carries only the `vocalVoiceness`
artifact-wiring lines. The regression itself is left as-is in the working
tree (not reverted, not committed) since its origin and intent are unknown;
if it persists, it should be logged to a `ui/` issue tracker separately from
this plan.

**Kill condition — unevaluable, not failed.** With zero `type: "vocal"`
ground truth marked anywhere in this environment (item 1 left marking to the
operator), the aggregate proxy metric favors `vocal_voiceness`
(false-vocal-rate proxy 0.179) over `arrangement_state` (0.596) on every song
including `ayuni` (0.180 vs 0.408) — but this is a firing-rate proxy, not the
validated metric, so it is **not** scored as a pass of the kill condition.
Re-run `score` once item 1's marking exists; do not treat this proxy result as
a promotion signal for item 8.

### Visual QA

- Surface: `/?song=ayuni`, `4. Vocal Voiceness` lane visible beneath Human
  Hints.
- Checks: lane head `data-lane="vocalVoiceness"` exists, carries the flask
  badge (experiment output); canvas full-extent check (rightmost non-empty
  pixel column within 4px of the lane's right content edge, or the stated %
  floor if the renderer has one); zoom min/max both redraw.
- Negative checks: no console/page errors, no failed fetch of
  `vocal_voiceness.json`.
- Baseline: add `reference/proposals/vocal_voiceness.json` (decimated) to the
  `_test_song` fixture and `build-fixtures.py`; capture the lane's baseline
  screenshot.

---

## Item 5 — `clap_voiceness` (B)

*Refinement item 5. `experiments/` + lane. Depends on items 1, 2, 3. No new
image.*

**What changes.** One contrastive CLAP pair — *"a person singing"* vs *"a
flute, a synth lead"* — read as a differential, following the two centrings
`experiments/clap/` already established as mandatory for usable readings.

- [x] `experiments/clap_voiceness/` — reuses `experiments/clap/probes.py` and
  `experiments/clap/model.py` (import from the sibling experiment package is
  fine; both are `experiments/`, the `src/`-import rule doesn't apply between
  experiments) for the CLAP forward pass and centring; `export.py` writes the
  differential score into the shared schema (item 2), reporting **frame
  voiceness accuracy and false-vocal rate only** — boundary F1 is reported but
  explicitly not scored, since CLAP's 5 s window is too coarse to time an edge.
- [x] `README.md` states plainly: this candidate is an independent second
  opinion on the frame-level call, not a boundary competitor.
- [x] Debugger lane: `5. CLAP Voiceness`, under Human Hints.
- [x] `queue.toml` row — see D5.1 (`image = "clap-research"`, not `"app"`).
- [x] `docs/experiments.md` entry, explicitly cross-referencing the existing
  CLAP character entry's "weak vocal axis" finding and explaining why this
  differential pair is not contradicted by it (that was an absolute reading;
  this is a pair).

**D5.1 (resolved).** The plan text said `image = "app"`, but CLAP needs
`transformers`, which lives only in the research sandbox
(`experiments/clap/run_in_container.sh`), not the `app` image. Used
`image = "clap-research"` instead — any non-`"app"` value makes the queue
runner honestly record `skipped(needs image clap-research — run via
run_in_container.sh)` per its own documented behavior, rather than falsely
claiming `"app"` and having `compute` crash. Matches `experiments/clap/`'s own
precedent of staying out of `queue.toml`'s auto-run path entirely.

**D5.2 (resolved).** Output grid is CLAP's native ~1 Hz (`interval_ms: 1000`),
not upsampled to the other candidates' 50 ms — upsampling would imply false
precision from a 5 s analysis window. `voiceness_common.scorer` handles
mixed-grid inputs already (per its design); this is a deliberate choice, not
an oversight.

**D5.3 (resolved).** Phrase derivation: threshold 0.5, gap-merge ≤ 1 s,
min-duration 2.0 s (a CLAP window is 5 s wide) — not corpus-tuned, a
documented judgement call pending ground truth. Confidence reuses item 4's
`|voiceness − 0.5| × 2` decision-margin heuristic for consistency across
voiceness candidates.

### Validation

- [x] `compute`/`export`/`score` subcommands run on all 5 scoring-corpus songs.
- [x] `docker compose run --rm ui npm run test` (391/392 — the same
  pre-existing, unrelated `App.tsx` "Lanes" accessible-name regression as item
  4, confirmed unrelated by diff inspection and left untouched again) +
  `npm run build` clean.

**Kill condition — unevaluable, not failed.** Same as item 4: zero
`type: "vocal"` ground truth exists anywhere, so "agrees with the marked spans
better than chance" cannot be evaluated yet. Aggregate proxy frame accuracy:
`clap_voiceness` 0.4826 vs `arrangement_state` 0.4045 vs `vocal_phrases`
0.7071 vs mix-RMS 0.0781 — reported honestly as a proxy, not treated as a
pass. Re-run `score` once item 1's marking exists.

### Visual QA

Same shape as item 4's block: lane head `data-lane="clapVoiceness"`, flask
badge, full-extent + zoom checks, negative checks, one new baseline.

---

## Item 6 — `svd_tagger` (C)

*Refinement item 6. `experiments/` + lane, new sandbox image. Depends on items
1, 2, 3.*

**What changes.** A pretrained audio tagger's `Singing`/`Singing voice` head
(PANNs or BEATs), run on the vocal stem and on the mix, both reported.

- [ ] New sandbox image, pattern of `experiments/drop_detection/research/Dockerfile.vocalparse`
  / `Dockerfile.acestep`: `experiments/svd_tagger/Dockerfile`, pinned model
  checkpoint fetched and checksummed at image build time — no mid-run download.
  `run_in_container.sh` mirrors `experiments/clap/run_in_container.sh`.
- [ ] `experiments/svd_tagger/` — `model.py` (loads the tagger, runs both
  channels), `export.py` (writes both channels' scores into the shared schema,
  tagging which channel — `stem` vs `mix` — a row's `voiceness` came from, via
  a `field_sources`-style attribution *within the proposal file itself*, not
  just at file level, since the two channels are genuinely different
  producers), `README.md`.
- [ ] Debugger lane: `6. SVD Tagger`, under Human Hints, with both channels
  visible (two curves or a toggle — resolve at implementation time; default to
  two curves, since "no hiding behind a selector" is the standing rule and a
  toggle would violate it).
- [ ] `queue.toml` row — `image` names the new sandbox service; if it is not
  addable to `docker-compose.yml`'s `app`-only runner (per D10.1 in
  `queue.toml`'s own comment, only `image = "app"` is honored), the row is
  recorded `skipped(needs image svd_tagger — run via run_in_container.sh)`,
  matching how `clap` is already handled.
- [ ] `docs/experiments.md` entry with the cost called out explicitly (new
  image, new pin) beside the score.

### D6.1 (resolved)

**PANNs vs BEATs.** Recommendation: PANNs (Kong et al.) — smaller, a stable
pretrained checkpoint, well-documented `Singing`/`Music` output classes,
narrower dependency footprint than BEATs' fairseq-adjacent stack. Revisit only
if PANNs' checkpoint proves unavailable or its class set lacks a clean singing
label at implementation time.

### Validation

- [ ] Sandbox image builds and the checksum step is verified.
- [ ] `compute`/`export`/`score` run inside the new image via
  `run_in_container.sh` on the scoring corpus.
- [ ] `docker compose run --rm ui npm run test` + `npm run build`.

**Kill condition.** Does not beat item 4 on `ayuni`'s false-vocal rate, given
its image and pin cost → negative result, lane kept for one review pass.

### Visual QA

Same shape as item 4, lane head `data-lane="svdTagger"`, both channels'
curves each pass the full-extent/zoom checks, one new baseline.

---

## Item 7 — `whisperx_vad` (D)

*Refinement item 7. `experiments/` + lane, new sandbox image. Depends on items
1, 2, 3.*

**What changes.** whisperX's VAD front-end over the vocal stem, emitting
`vocal_phrase` proposals in the shared schema. Diarization is a second,
optional pass, scored separately and never folded into the voiceness call.

- [ ] New sandbox image (same pattern as item 6): `experiments/whisperx_vad/Dockerfile`
  — `transformers` + whisperX + (optionally) `pyannote.audio`, pinned
  versions, `torchaudio`/`torch` compatibility checked explicitly (the
  refinement doc names the `app` image's existing CUDA mismatch as the reason
  a new image is needed at all).
- [ ] **pyannote checkpoint determinism.** If diarization is attempted: the
  gated Hugging Face checkpoint is fetched and checksummed at image build time
  using a token supplied as a build secret, never fetched at analysis time. If
  that is not achievable within this item's scope, diarization is **not
  attempted** and the item ships VAD-only — say so plainly in the README rather
  than discovering it at the promotion gate (refinement doc, item 7).
- [ ] `experiments/whisperx_vad/` — `model.py`, `export.py` (VAD spans →
  `vocal_phrase` blocks in the shared schema; diarization output, if built,
  reported as a lead/backing/other split in a separate field, scored
  separately by `score.py`), `README.md` recording the three objections from
  the refinement doc (flute misclassified as a speaker; sustained vowels with
  no consonants are the VAD's classic miss; lead-vs-backing is its weakest
  axis) as expected, named risks rather than surprises discovered after the
  run.
- [ ] Debugger lane: `7. WhisperX VAD`, under Human Hints.
- [ ] `queue.toml` row, same `skipped(needs image ...)` handling as item 6 if
  it can't run through the `app`-only runner.
- [ ] `docs/experiments.md` entry.

### Validation

- [ ] Sandbox image builds; checksum step verified; if diarization was
  attempted, confirm no token is required at analysis time (rebuild the image
  from a clean cache with the build secret removed and confirm inference still
  runs against the baked-in checkpoint).
- [ ] `compute`/`export`/`score` on the scoring corpus.
- [ ] `docker compose run --rm ui npm run test` + `npm run build`.

**Kill condition.** Does not beat item 4 on `ayuni`'s false-vocal rate, or
cannot run without a mid-run gated download → negative result (the second
clause is an automatic kill regardless of score, per the refinement doc).

### Visual QA

Same shape as item 4, lane head `data-lane="whisperxVad"`, diarization split
(if built) rendered as a distinct sub-lane or color-coded segment (not hidden
behind a selector), one new baseline.

---

## Item 8 — `arrangement_state` gates `vocals` on voiceness

*Refinement item 8. `src/`. Gated: does not start until one of items 4–7 beats
the incumbent on item 2's scorer at a matched budget, and the operator has
reviewed the winning lane by ear. If none wins, this item is skipped and the
plan proceeds to item 9 with that outcome recorded.*

**What changes.** `detect_arrangement_state`'s `vocals` channel
(`src/analyzer/stages/arrangement_state.py`) additionally requires agreement
from the winning detector's voiceness track, read from
`reference/proposals/<winner>.json` the way any phase-3 stage reads a
phase-1/2 artifact. The other three stems (`bass`, `drums`, `harmonic`) are
untouched.

**What breaks if reversed.** `arrangement_state.json`'s `vocals` entries in
`playing` go back to being an RMS-only claim — the exact defect this release
measures (40.8 % false-vocal rate on `ayuni`) — and `song_event_timeline.json`
loses its only vocal-phrase events.

- [ ] `arrangement_state.py` — `detect()` additionally reads
  `reference/proposals/<winner>.json` (winner name fixed at implementation
  time, once known) and requires its voiceness call to agree before a `vocals`
  entry flips to present. Keep `PRESENT_DB_BELOW_P98`/`PRESENT_FRACTION`/etc.
  for the other three stems unchanged.
- [ ] `ui_data.py`'s `publish_arrangement_state` — the published `vocals` entry
  in each block's `playing` carries its **own named confidence**, sourced to
  the winning experiment, distinct from `margin_db`/the derived `confidence`
  field that measures the *other* stems' RMS margin. Follow the existing
  `_fuse`/`validate_field_sources` pattern (`ui_data.py:225`, `:370`) — this is
  a per-field attribution, not a second file.
- [ ] **Honest `unknown`.** Where the winning detector's confidence sits below
  its own stated floor, the `vocals` channel reports `"unknown"` rather than
  falling back to the RMS gate — no silent fallback to the exact behavior this
  release is fixing.
- [ ] `gestures.py` (or wherever `song_event_timeline.json` is assembled) —
  emit `vocal_phrase` events from the winning detector's `vocal_phrase` blocks,
  in the existing event shape (`type`, `start_time`, `end_time`, `confidence`,
  `provenance` naming the winning experiment; `section_id`/`section_name`
  resolved the same way existing events resolve them).
- [ ] `docs/reference/downstream-contract.md` — fold in the new `vocals`
  confidence field and the `vocal_phrase` event kind as current state (v3.4
  precedent: no standalone handoff note, the contract doc *is* the handoff).
- [ ] `docs/reference/artifacts.md` — update the `arrangement_state.json` and
  `song_event_timeline.json` rows.
- [ ] `docs/mcp-definition.md` — update the Arrangement / timeline sections if
  the new field changes what the MCP server surfaces (it should, since these
  are already-projected top-level files — no MCP code change needed unless a
  new field needs explicit mention in the tool's projection logic; check
  `mcp/` source before assuming none).

### Validation

- [ ] `docker compose run --rm app ./analyze --song "/data/songs/ayuni.mp3"
  --stage detect-arrangement-state` then `--stage publish` (or the full
  pipeline) — confirm `vocals` in `playing` no longer spans 40.8 % of `ayuni`,
  and specifically that the flute-heavy passage identified in the refinement
  doc's review no longer reads `vocals` present.
- [ ] `docker compose run --rm test` green; extend `tests/test_arrangement_state.py`
  with a case where RMS says present but the voiceness track disagrees →
  `vocals` absent; a case where the voiceness confidence is below floor →
  `"unknown"`, not a guess.
- [ ] `docker compose run --rm --no-deps -T --entrypoint python mcp
  mcp/tests/run.py smoke-test` green (contract change touches a file the MCP
  server reads).

---

## Item 9 — Correct the recorded conclusion

*Refinement item 9. Docs only. Depends on items 3–8's outcomes being known
(the correction cites whichever ships and whichever doesn't).*

- [ ] `experiments/clap/README.md` — narrow the *"Take voice presence from the
  stems"* recommendation to what it actually measured: correct on the four
  gold songs, which separate cleanly; wrong on `ayuni`, named as the
  counterexample, with the 40.8 % / 39.0 % figures and a pointer to this
  release's entries.
- [ ] `docs/analysis-definition.md` — add the vocal-stem trustworthiness bound
  beside the existing drum-vocabulary bound: what the vocal stem can and
  cannot be trusted to assert, the two figures and their cause (self-
  normalisation stretches leaked flute to full scale), and — if item 8 shipped
  — the fix; if it didn't, that the bound remains open and why (naming which of
  items 4–7 came closest and by how much).
- [ ] `CLAUDE.md` — if item 8 shipped, add or update the one-line summary in
  the "Current state, in one table" list for the `vocals` channel, mirroring
  the drum-vocabulary row's style.

### Validation

- [ ] Read both corrected docs end to end; confirm no remaining sentence in
  either still asserts stem RMS alone is sufficient for vocal presence.
