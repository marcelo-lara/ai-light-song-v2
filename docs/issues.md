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
  the shipped artifacts without re-running anything.
- **Validation target:** the four gold songs (`Titanium - David Guetta ft Sia`,
  `Armin - Revolution`, `Hideaway - Kiesza`, `_test_song`), auditioned in the
  debugger against the waveform.
- **Success condition:** a per-primitive precision figure exists for each
  gesture phase across the gold set, and either the false-positive rate is
  written into `CLAUDE.md` as a known bound, or the primitives responsible for
  the phantoms are tightened until it is.

### `get_song_overview` — prose budget on gesture-dense songs

- **Status:** `pending`
- **Raised:** 2026-09-06, closing v3.1 (decision D25, resolved-as-accepted).
- **Problem:** the committed token-budget gate is fixture-based — the
  `McpFull - Fixture` overview is 4283 bytes, under the 6144-byte ceiling. Real
  gesture-dense songs run larger: `Titanium` 13981 B, `Armin - Revolution`
  12644 B, `Hideaway` 10025 B, `_test_song` 7936 B — all over the 6 KB
  real-song target the plan set.
- **Why it was accepted, not fixed:** the size is driven by *structure*, not
  prose. On `Armin` the 31 grouped gesture rows are ~6.8 KB on their own —
  already over the target — and the 13 human-hint rows (~2.2 KB) are verbatim
  ground truth that the honesty rules forbid trimming. The genre `guidance` and
  section `description` prose is already short (~180 / ~30 chars); clipping it
  saves under 300 bytes and does not change the picture. Getting near 6 KB would
  mean cutting gesture structure or truncating hints, both of which the plan
  ruled out.
- **Options for a real fix:** a phase-code legend replacing repeated
  `phases_present` / `phases_absent` arrays; a compact gesture encoding; or
  making the overview paginate gestures and expose the rest via `get_detail`.
- **Success condition:** a gesture-dense gold song's `get_song_overview` is at
  or under 6 KB with every human hint still verbatim and every composite gesture
  still individually addressable — or the 6 KB target is formally replaced with
  a structure-aware budget in `mcp-definition.md`.

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
