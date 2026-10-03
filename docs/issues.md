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
  `impact_alignment` (removed again in v3.10 item 8; the fixture gate stays at
  the 6900 B v3.9 set); `position` (item 3/5) was deliberately kept off this
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

### `whisperx_vad/vocal_onsets.py` and `vocal_onsets.json` are dead since v3.10 item 8

- **Status:** `pending` — found implementing v3.10 item 8.
- **Problem:** `section_clues.py` was the only reader of
  `artifacts/whisperx-vad/vocal_onsets.json`. It was cut, but the `whisperx`
  service still loads `faster_whisper` large-v3 and writes the file on every run
  (`whisperx_vad/vocal_onsets.py`, `export.export_vocal_onsets`,
  `__main__.py`, `paths.py`, the `WHISPER_DEVICE` comment in
  `docker-compose.yml`). Nothing in `src/`, `mcp/` or `ui/` reads it (grep
  verified); `experiments/truth_common/block_reviews.py` names only the
  separate `rhythm_vocal_onsets.json` proposal.
- **Validation target:** a `whisperx` run on one song.
- **Success condition:** the module, its export call, the path helper, the
  compose note and the `artifacts.md` row are deleted, and a `whisperx` run
  writes only `whisperx_vad.json`.

### `phrases`' `noise_sweep` rule fires on 3 of 299 phrases

- **Status:** `pending` — found in v3.10 item 15.
- **Problem:** the rising-noise rule in `experiments/phrases/` is too strict to
  carry information (3 of 299 phrases, no ground truth), so the field is
  effectively always false.
- **Validation target:** a few songs with an audible white-noise sweep, named
  by the operator in the Phrases lane.
- **Success condition:** the rule fires on those sweeps and not on steady
  sections, or the field is dropped from `phrases.json`.

### Experiment tests are not collected by `docker compose run --rm test`

- **Status:** `pending` — found in v3.10 items 14-17.
- **Problem:** the `test` service's default command is `pytest tests/ -q`
  (`Dockerfile.test`), so the suites under `experiments/*/tests/`
  (`filter_sweep`, `phrases`, `downbeat_anchors`, `section_names`,
  `stem_presence_sections`, `truth_common`, ...) never run in the default check
  and a regression there is invisible. Each runs only when named, e.g.
  `docker compose run --rm test python3 -m pytest experiments/phrases/tests -q`.
- **Validation target:** `docker compose run --rm test` before and after.
- **Success condition:** the default run covers `experiments/*/tests` too (or
  the docs state, in one place, that it deliberately does not).

### Light changes — `kick_present` misses Medicine bar 18

- **Status:** `pending` — found in v3.12 item 29, accepted there (D1).
- **Problem:** Medicine's bar-18 drum roll is low-end bumps with a click <= 4 dB; `CLICK_MIN_DB` 4.0 rejects it, and lowering the gate far enough admits the bass hits of bars 20-21. `kick_present` is right on 13 of 14 bars (9-17 present, 19-22 absent).
- **Validation target:** *Medicine-MilkInc* bars 9-22 `kick_present` in `bar_features.json`.
- **Success condition:** bar 18 reads present with bars 19-22 still absent, using a rule that is not a threshold tuned on Medicine alone.

### `detect-kick-attacks` recall is near zero under a hat bed (Armin and others)

- **Status:** `pending` — found in v3.12 item 29.
- **Problem:** agreement with omnizart kicks (+-50 ms) is precision 0.44 / recall 0.32 over 27 songs and near-zero recall on *Armin*, *Sash*, *StealTheShow*, *Charli-VonDutch*, *ChangedTheWayYouKissMe*: the 2-5 kHz click does not clear a busy hat bed, so `kick_present` is false where a kick plays. The published `bar_features.json` `kick_present` is therefore unreliable on those songs.
- **Validation target:** the five songs above, kick bars named by the operator in the Kick Attacks lane.
- **Success condition:** `kick_present` on those songs agrees with the operator's reading without lowering precision on *Fascination* (.87) and *Medicine*.

### Medicine fill, break and drop `light_change` points sit 0.95-1.00 beat early

- **Status:** `pending` — found in v3.12 items 32 and 37. Addressed by v3.13 items 40–41 (`docs/implementation-plan-v3.13.md`).
- **Problem:** the point time is floored to the beat that contains the change, so Medicine 8 fill (-1.00 beat), 19 break (-0.95) and 23 drop (-0.98) land a full beat before the bar start, right at the one-beat hit limit; a cue fired a beat early is a cue missed. Medicine also carries an extra break at 29.41 s (bar 18 beat 1).
- **Validation target:** the 8 validation targets in `docs/implementation-plan-v3.12.md` item 37.
- **Success condition:** round-to-nearest (a one-line change) or a half-beat-aware rule puts those three within half a beat with Armin 55/59/60 and Medicine 9/16 unchanged and 10-14 still empty.

### 65% of filter sweeps carry `aftermath: none`

- **Status:** `pending` — found in v3.12 item 31.
- **Problem:** 131 sweeps on 27 songs (1.3/min), 85 with `aftermath: none` (halved confidence), the "suspect detection" signature. Thresholds were set on *Armin* and *Medicine*. Sweep end events and `aftermath` were not ported to `src/` (no consumer), so the sweep state in `bar_features.json` carries none of it.
- **Validation target:** the Filter Sweeps v2 lane on *ayuni*, *Charli-VonDutch*, *Cinderella* (14 sweeps) and *It's a fine day* (14), reviewed by the operator.
- **Success condition:** a verdict per sweep in the lane; the rule is tightened until the suspect share is explained or the `none` sweeps are dropped.

### Downbeat re-anchor: let the phase change only inside an unresolved span

- **Status:** `pending` — follow-up of `experiments/downbeat_reanchor` (v3.12 item 30, gate not met: F1 0.024 / 0.163 vs allin1 0.343).
- **Problem:** one constant phase per trusted run cannot follow a real 1-beat slip (*Armin*), which is what costs the F1. The phase should be allowed to change only inside an unresolved (`resolved: false`) span or an `off_grid_span`, never in the middle of a resolved run. Today 72 bars outside `off_grid_spans` are not 4 beats long (99 in all).
- **Validation target:** the 5 Moises songs (downbeat F1 @ +-70 ms) and Medicine bar 16 (a 1-beat bar).
- **Success condition:** F1 above 0.343 with zero bars != 4 beats outside `off_grid_spans`, thresholds not tuned on the Moises songs.

### `vocal_cadence` line starts without lyrics are unsolved

- **Status:** `pending` — v3.12 item 36 gate not met (D9).
- **Problem:** line starts from `vocal_onsets.json` word times (rest >= 1 beat) score F1 0.346 @ +-1 beat on the 5 songs with lyrics (needs 0.7); a 2-beat rest gives 0.305. Word onsets carry no end time and whisper splits slow phrasing. 22 of 27 songs have `source: null` and no lines.
- **Validation target:** Armin, Hideaway, Queen of Kings, `_test_song`, Titanium lyric line starts.
- **Success condition:** a method (word ends, `vocals_phrase` cover, or a forced aligner) reaches F1 >= 0.7 @ +-1 beat on those songs without reading word text.

### Operator lane review: light changes and kick attacks

- **Status:** `pending` — list from v3.12 item 37.
- **Review:** *ayuni* (24 points, 8.74/min, 1 irregular bar) and *Charli-VonDutch* (8 points, 2.97/min, 5 irregular bars, 2 sweeps where v1 found 0) bar placement; every song above 8 points/min: *Armin - Revolution* 8.97, *Medicine-MilkInc* 8.82, *ayuni* 8.74 (next: *Rapture* 7.52, `_test_song` 7.23, *CruelSummer* 7.00); the Filter Sweeps v2 and Kick Attacks lanes.
- **Success condition:** a verdict per song; points the operator rejects become a threshold or role-rule change.

### Debugger lanes "Kick Attacks" and "Filter Sweeps v2" read experiments whose logic now lives in `src/`

- **Status:** `pending` — found closing v3.12.
- **Problem:** `src/` stages `detect-kick-attacks` and `extract-harmonic-spectrum` are ports of `experiments/kick_attacks` and `experiments/filter_sweep_v2`, whose proposals still draw two flask-badged lanes and are 404 on the fixtures (allowed by `OPTIONAL_PROPOSALS_404` in `tests/ui-visual/helpers.ts`). The experiments are archived as promoted, so by the lane rule the lanes should read `artifacts/` or be retired.
- **Validation target:** `docker compose run --rm ui npm run test` and the visual suite.
- **Success condition:** both lanes are either re-pointed at the stage artifacts or removed via Recipe B in [`reference/ui-development.md`](reference/ui-development.md), and `OPTIONAL_PROPOSALS_404` drops their paths.
