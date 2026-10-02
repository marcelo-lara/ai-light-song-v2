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
