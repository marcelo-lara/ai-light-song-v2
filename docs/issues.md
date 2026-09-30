# Open issues

**Pending issues only** (a queue, not a history). Solving one means deleting its
entry in the same change; write anything durable into the relevant definition
doc first. An empty queue is not a claim that the analysis is in good shape —
see [`analysis-definition.md`](analysis-definition.md) "Known gaps".

Scope each entry to one problem, one validation target, and one success
condition — and make the success condition mean the *stage* improved, not that
one song stopped complaining.

Current focus song: `_test_song`
(`reference/human/human_hints.json`, `reference/moises/chords.json`,
`artifacts/validation/phase_1_report.json`).

## Open queue

### `test_seeded_queue_parses_with_three_enabled_app_rows` expects archived queue rows

- **Status:** `pending` — stale since v3.6, carried as a known failure through v3.7–v3.9.
- **Problem:** `tests/test_run_queue.py::QueueFileTests::test_seeded_queue_parses_with_three_enabled_app_rows`
  asserts `phrase_periodicity` / `svd_tagger` / `vocal_voiceness` rows that left
  `experiments/queue.toml` when those experiments were archived. It is the only red
  analyzer test (202/203 at v3.9 close-out).
- **Success condition:** the test asserts against the queue's current rows (or
  a fixture queue file), and the analyzer suite is fully green.

### `CruelSummer - Malvina` publishes an empty `sections.json`

- **Status:** `pending` — found implementing v3.9 item 4 (stem-entry impacts,
  which need a published section boundary to anchor on).
- **Problem:** `data/analysis/CruelSummer - Malvina/sections.json` has zero
  rows. Cause: `reference/human/segments.json` is an empty list (since
  `f87d31f`, 2026-09-20), and `ui_data.py` treats the file's *existence* as a
  reviewed override, so the human tier wins with 0 rows and allin1's 7
  sections are discarded. `Charli-VonDutch` is the same shape with one row
  (`Verse` at 0) → a single published section. Downstream, stem-entry impacts
  (`gestures.py`) have no boundary to anchor on, so the drops at 81.37 s and
  162.73 s are missed.
- **Validation target:** an empty (or clearly unfinished) reviewed segments
  file no longer erases the structure — either the tier is skipped with the
  reason recorded in `field_sources`, or the operator's file is completed.
  Needs the operator's call on which (a design decision, not a silent
  fallback).

### `Cinderella - Ella Lee`'s 85.73s drop is a drums-only entry

- **Status:** `pending` — found implementing v3.9 item 4.
- **Problem:** `detect_stem_entry_impacts` (`gestures.py`) requires the bass
  and drums stems to both cross their on-threshold within one beat of each
  other. This song's drop at 85.73s is drums-only at the boundary — the bass
  stem doesn't reach the shared on-threshold until ~86.1s, on a different
  beat entirely (a real bass note, not this drop's own entry) — so no
  qualifying pair is ever found and nothing is emitted (correct per "never
  guessed," but a real gap in coverage). The transient detector also misses
  this instant by >1s.
- **Validation target:** an impact within ±40ms of 85.73s on this song
  without regressing the corpus-wide gold score (`docs/analysis-definition.md`
  "Gestures").
- **Next step:** a drums-only entry variant of the stem-entry detector (single
  stem crossing its own on-threshold at a boundary, with a higher confidence
  penalty than the two-stem case) — evaluate on the gold set before shipping,
  per the promotion rule.

### `Charli-VonDutch`'s 29.85s drop gets no stem-entry impact — sparse kicks dilute the smoothing

- **Status:** `pending` — found implementing v3.9 item 4 follow-up.
- **Problem:** the bass stem legitimately crosses the on-threshold at ~30.19s
  (within one beat of the 29.85s boundary — the physical entry is correctly
  reachable). The drums stem never does: its raw signal has two real, loud
  kicks right at the boundary (29.765–29.825s and 30.245–30.285s, each
  0.96–1.24× the song's own drums p95), but each lasts only 40–60ms, roughly
  a beat apart, with near-silence between. `detect_stem_entry_impacts`'
  centered 1-beat rolling *mean* used to decide "is this stem on" dilutes
  each brief kick into the surrounding silence, topping out at 0.31× p95 —
  short of the 0.40× on-threshold by about a quarter. No pairing is ever
  found, so nothing is emitted (never guessed, but a real gap on a sparse
  kick pattern). I tried swapping the rolling mean for a rolling max
  (naturally immune to dilution) and it did **not** fix this song — the
  full pipeline (crossing → jump-score → onset → sustain) still produced no
  candidate at 29.85s for a reason I didn't chase further — while it *did*
  regress a verified case: Titanium's 151.445s onset vanished entirely, and
  Rapture's/QoK's crossings all shifted noticeably earlier from picking up
  more transient blips. Did not ship it.
- **Validation target:** an impact within ±40ms of 29.85s (or wherever the
  true onset resolves to) on this song, without moving Rapture's 55.385s/
  169.845s, Titanium's 151.445s, or reintroducing QoK's 48.555s duplicate.
- **Next step:** a presence check that's robust to sparse, short hits without
  over-triggering on transient noise — e.g. a rolling max gated by a minimum
  hit *duration* (not just amplitude), or a hit-count/density check over the
  window rather than an amplitude average — evaluated against the full gold
  set before shipping, per the promotion rule.

### `get_detail`'s `dropouts` — vocals gap detector misses short mid-song gaps

- **Status:** `pending` — found implementing v3.7 item 9 (dropouts).
- **Problem:** the vocals-stem noise floor for gap detection is a whole-song
  5th-percentile of the loudness series. On *What a Feeling – Courtney Storm*
  this only finds the intro/outro silences; the short "chatter gap under a
  synth pulse" moments the item's refinement doc named (found by manual ear
  during the original review) do not clear that floor and are not emitted.
  The detector works — it just isn't sensitive enough for a brief, local dip
  against an otherwise-loud song.
- **Validation target:** *What a Feeling – Courtney Storm*, the two known
  chatter gaps under synth pulses (found by ear, times not yet logged
  precisely — re-locate by ear against the mix stem).
- **Success condition:** a more local/adaptive floor (e.g. a rolling window
  rather than whole-song percentile) emits both known gaps without also
  emitting spurious short dips elsewhere in the song.

### `arrangement_state`'s drums-absence call looks broken past 112.75 s on *What a Feeling*

- **Status:** `pending` — found implementing v3.7 item 9 (dropouts), which
  cross-checks `arrangement_state`'s per-block stem-absence calls against
  measured drum onsets and reports a `disagreement: true` span wherever they
  conflict.
- **Problem:** beyond the one pre-chorus block the operator had hand-flagged
  (`112.75–127.0 s`, confidence 0.163), several further blocks from 127 s to
  song end call `drums` absent at confidence up to **0.963** while
  `drum_events.json` shows 4–8 onsets/s throughout — not silence, not noise.
  The scale of the disagreement (high-confidence blocks, not just the
  marginal one) suggests something more structural than a borderline call.
- **Validation target:** *What a Feeling – Courtney Storm*'s `drums`-absent
  `arrangement_state` blocks past 127 s, cross-checked against `drum_events.json`.
- **Success condition:** root cause found (e.g. a stem-routing bug specific to
  this song, or a systematic issue with the absence detector on dense mixes)
  and either fixed or the confidence model corrected so it stops asserting
  high-confidence absence where onsets are present.

### `mcp/tests/fixtures/build_fixtures.py` has drifted from the committed fixtures

- **Status:** `pending` — found during v3.9 items 1 and 3.
- **Problem:** a full `build_fixtures.py` run drops the `energy` / `tension` /
  `rhythm` / `impact_alignment` fields hand-added to `McpFull - Fixture/sections.json`
  since v3.6/v3.7, so the generator no longer reproduces what is checked in.
  Items 1 and 3 regenerated only the files they added or changed and reverted the rest.
- **Success condition:** the generator emits every committed fixture file
  byte-identically, so it can be re-run in full.

### Visual-regression baseline mismatch — height off by ~78px on most specs, environment-side

- **Status:** `pending` — found running `docs/reference/ui-regression.md` §6
  during v3.7 item 2, confirmed pre-existing (reproduces identically at the
  v3.7 item-1-only commit, before any UI change this release made).
- **Problem:** 36 of 40 Playwright specs fail with a captured-image height
  mismatch against the committed baseline (e.g. `timeline-zoom-min.png`:
  expected 1280×1142, received 1280×1220 — a consistent ~78px taller capture),
  spanning specs unrelated to any recent feature (fft-bands-stems, drums-crash,
  header-readout, lane-collapsed, …). Consistent with the pinned Playwright
  container (`mcr.microsoft.com/playwright:v1.56.0-noble`) rendering fonts or
  layout slightly differently than whatever machine captured the current
  `__screenshots__` baselines, not a real UI regression.
- **Success condition:** either the baselines are recaptured in the pinned
  container and committed, or the root cause (font substitution, DPR, viewport)
  is found and the guide's determinism section is amended so a recapture is not
  needed. Until then, a `pending`/`failed` visual suite must not be read as a
  UI defect without first checking whether it reproduces at a commit before
  the change under test.
- **Re-run at v3.8 item 2 (44 specs: 4 pass, 38 fail, 2 skipped)** — none
  caused by that item. Besides the 10 height-mismatch failures above:
  - **Fixture gap (18 specs):** `RegFull - Fixture/reference/proposals/allin1_posterior.json`
    is missing, but the `allin1Posterior` lane fetches it unconditionally → a
    404 that `assertNoRuntimeErrors` fails on. Stubbing the file made all 18
    pass. Fix: add the fixture, or make the 404 optional in `helpers.ts`.
  - **Right-panel pixel diff (4):** `block-energy-rating`, `lane-events` ×2,
    `lyric-validation` fail at ~2% pixel diff (not a height change).
  - **Functional failures (6), reproduce in isolation:** `card-click-seek`,
    `experiment-badge` ×2, `follow-playhead`, `phrase-periodicity`,
    `sections-contested`; `promote-hint` times out on `.app-header__total`.

### Waveform/playhead drift — up to 600ms, root cause not yet located

- **Status:** `pending` — reported by the operator as "the waveform is not
  aligned with playback", triaged this session, not fixed.
- **Raised:** 2026-09-13.
- **Ruled out by measurement**, so the next session shouldn't re-check these:
  - Shared playhead (`TimelineGrid`'s `.tl-playhead`) vs. wavesurfer's own
    played/progress edge (pierced its shadow DOM): agreed within 0–8px
    (sub-100ms) across two songs, multiple playback times, after zoom, after
    fit-to-width, in this session's own headless-browser probe. Not the
    "whole waveform looks played" effect it first appeared to be in a
    screenshot — that was two similar purple hues (`WAVE_COLOR` #968ae0 vs
    `WAVE_PROGRESS_COLOR` #d2cefd) misread at small scale; a zoomed crop
    showed the transition sitting exactly on the playhead.
  - Waveform content vs. the analysis timeline (the thing that positions bar
    lines / drives `timeToX`), at t≈0: decoded Cinderella's mp3 in a real
    browser via `AudioContext.decodeAudioData` (the same path `wavesurfer.js`
    uses for peaks), built a 10ms RMS envelope, cross-correlated it against
    `artifacts/essentia/rms_loudness.json`'s own mix-channel RMS envelope —
    best lag **0ms** at the start of the file. No encoder-delay / decode-path
    offset there.
  - **Neither measurement caught the real bug** — both were near t=0 / short
    playback windows. The operator confirms the actual drift reaches **up to
    600ms**, and separately, that **the waveform can be out of alignment with
    the bar grid AND with timed events (hints/sections/lane markers)
    simultaneously** — i.e. not only a playhead-vs-audio question, but the
    bar lines and event blocks (independently positioned via the same
    `coords.timeToX`) can also disagree with what the waveform picture shows.
    That rules out an isolated seek-lag theory and points more at something
    session-duration- or drift-dependent (possibly `coords`/`pxPerSec`
    recomputing as beats stream in and the wavesurfer instance not
    re-anchoring cleanly — unconfirmed) rather than a one-shot async-seek
    race.
- **Validation target:** any song with audio; reproduce with a *longer*
  playback session (this session's probes only ran ~30–40s) and check
  alignment against bar lines and Human Hints / Human Sections blocks, not
  just the playhead.
- **Success condition:** the drift is reproduced and measured directly (not
  inferred from a short probe), its growth condition identified (time
  elapsed? a specific action — seek, zoom, scroll, lane toggle? artifact
  arriving late and shifting `coords`?), and then closed.

### `gestures` — per-primitive precision has never been audited by ear

- **Status:** `pending`
- **Raised:** 2026-09-05, on closing the v3.0 release docs. This was the one
  risk the release accepted and did not discharge, and it is the largest
  unmeasured risk in the shipped pipeline.
- **Problem:** the gestures stage is scored on impact *recall* against seven
  hand-clicked impacts. A phantom primitive — a riser, a build or a tension
  span asserted where the music has none — does not move that metric at all,
  yet it fires a cue that contradicts the song. Nothing currently measures how
  often that happens.
- **Evidence to use:** every gesture phase in `song_event_timeline.json`
  carries its per-primitive evidence string, so the audit is possible against
  the shipped artifacts without re-running anything. **v3.7 item 1 built the
  instrument**: a three-state verdict control (`correct`/`wrong`/`misplaced`)
  on the `gestures` lane's blocks in the debugger, and
  `experiments/truth_common`'s `block_reviews` scorer turns saved verdicts
  into a per-lane precision figure. Auditioning itself — clicking a verdict on
  each gesture block for the four gold songs — is still open; nothing here
  claims that work is done.
- **Validation target:** the four gold songs (`Titanium - David Guetta ft Sia`,
  `Armin - Revolution`, `Hideaway - Kiesza`, `_test_song`), auditioned in the
  debugger against the waveform, using the block-verdict control above.
- **Success condition:** a per-primitive precision figure exists for each
  gesture phase across the gold set, and either the false-positive rate is
  written into `CLAUDE.md` as a known bound, or the primitives responsible for
  the phantoms are tightened until it is.

### `get_song_overview` — prose budget on gesture-dense songs

- **Status:** `pending`
- **Raised:** 2026-09-06, closing v3.1 (decision D25, resolved-as-accepted).
  Re-measured 2026-09-14 after v3.6 item 8's field trim + item 9's MCP-side
  rebuild: `McpFull - Fixture` overview is now 4973 bytes (still under the
  6144-byte fixture gate). `Titanium - David Guetta ft Sia` is **34,919
  bytes** — larger than the pre-trim 13,981 B, not smaller. Trimming
  `label`/`description`/`chord_progression`/`guidance`/etc. did not move the
  needle: `arrangement` (44 blocks, 7,273 B — promoted after this issue was
  first raised) is now the largest block, just ahead of `gestures` (7,107 B);
  `sections` fell to 3,169 B once `description` was dropped. v3.7 item 2 added
  `impact_alignment` (omitted when `null`, same convention as energy/tension) —
  the fixture gate moved to 6450 B to keep one resolved example in the
  committed snapshot; `position` (item 3/5) was deliberately kept off this
  tool entirely for the same reason (see serializers.py's `build_song_overview`
  docstring) — `get_detail` carries it instead.
- **Why it was accepted, not fixed:** the size is driven by *structure*, not
  prose — dropping prose fields saves low hundreds of bytes, not the low
  thousands needed. Every dense block (`arrangement`, `gestures`, human hints)
  is verbatim structural or ground-truth data the honesty rules forbid
  trimming or truncating.
- **Options for a real fix:** a phase-code legend replacing repeated
  `phases_present`/`phases_absent` arrays; a compact gesture encoding; a
  compact arrangement-block encoding (44 blocks is now the single largest
  contributor); or making the overview paginate gestures/arrangement and
  expose the rest via `get_detail`.
- **Success condition:** a gesture-dense gold song's `get_song_overview` is at
  or under 6 KB with every human hint still verbatim and every composite
  gesture and arrangement block still individually addressable — or the 6 KB
  target is formally replaced with a structure-aware budget in
  `mcp-definition.md`.

### Texture hints missing on three gold songs — `arrangement_state` corpus F1 measures the label absence, not the detector

- **Status:** `pending`
- **Raised:** 2026-09-07, on promoting `arrangement_state` into the pipeline
  (v3.2). The stage shipped on `_test_song` evidence alone, knowingly.
- **Problem:** `detect-arrangement-state` scores F1 0.59 @0.5 s on `_test_song`
  vs `sections.json`'s 0.00, but corpus-wide sits at 0.20 pooled — *below* the
  incumbent — because the gold hints are almost all drop stages, which
  `gestures.py` owns. Counted from `reference/human/human_hints.json`:

  | song | drop-stage hints | everything else |
  | --- | --- | --- |
  | `_test_song` (58 s, synthetic) | 5 | **10** |
  | `Titanium - David Guetta ft Sia` | 15 | **0** |
  | `Hideaway - Kiesza` | 5 | **0** |
  | `Armin - Revolution` | 10 | **2** |

  12 non-drop hints in the whole gold set, 10 of them inside one 58-second
  synthetic excerpt. On three of four gold songs every genuine arrangement
  change the detector finds is scored as a false positive by construction.
  `margin-sweep` confirms tuning does not help — gating `margin_db` 0 → 15 dB
  never improves pooled F1.
- **Validation target:** `Hideaway - Kiesza`, `Armin - Revolution`,
  `Titanium - David Guetta ft Sia`, marked in the debugger against the waveform.
- **Success condition:** texture blocks are marked on all three in
  `reference/human/human_hints.json` and the `arrangement_state` corpus F1 is
  re-scored against them — so the number measures the detector, not the labels.
  Marking the same blocks also unblocks the **CLAP character layer** entry in
  `docs/experiments.md`. It is an operator task: the hints are hand-authored
  truth and nothing in the pipeline may write them.

### UI Canvas Performance

- **Status:** `pending`
- **Raised:** 2026-09-13
- **Problem:** When expanding the canvas to >200px/bar the width contains excesive information that is not visible, flooding the browser memory; The solution could be to narrow the loaded information only to the visible portion, plus a buffer of half screen before and after to improve the ux; (lazy loading vs eagaer loading)
