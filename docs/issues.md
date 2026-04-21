# Analysis Issue Tracker

## Purpose

This file tracks analysis issues as a cumulative work queue.

Use it to break broad quality problems into focused, testable items that can be handled one at a time across multiple sessions.

## Status Convention

- `pending`: the issue is open and not yet fixed.
- `solved`: the issue has a verified fix, the relevant validation was rerun, and the success condition was met.

Do not change an issue from `pending` to `solved` without updating its evidence, validation notes, and success condition outcome.

## Operating Rules

- Keep this file cumulative. Add newly discovered issues instead of replacing older ones.
- Scope each issue to one concrete problem, one validation target, and one success condition.
- Prefer evidence from generated artifacts and documented reference files.
- Treat `data/reference/` as read-only validation input.
- For chord truth, treat `data/reference/<Song - Artist>/moises/chords.json` as authoritative when it exists.
- For section semantics, prefer context-aware musical-state labels over generic form labels like `intro`, `verse`, or `chorus` unless a separate structural contract explicitly requires those labels.
- Human storytelling hints are review guidance. They are not direct replacements for harmonic, symbolic, or energy truth.

## Current Focus Song

- Song: `What a Feeling - Courtney Storm`
- Human hints: `data/reference/What a Feeling - Courtney Storm/human/human_hints.json`
- Chord reference: `data/reference/What a Feeling - Courtney Storm/moises/chords.json`
- Lyric timing clue: `data/reference/What a Feeling - Courtney Storm/moises/lyrics.json`
- Current validation report: `data/artifacts/What a Feeling - Courtney Storm/validation/phase_1_report.json`
- Human-hints alignment review: `data/artifacts/What a Feeling - Courtney Storm/validation/human_hints_alignment.json`

## Active Queue

### ISS-001 - Beat and boundary alignment drift

- Status: `solved`
- Scope: beat timestamps, section boundaries, and event anchors for `What a Feeling - Courtney Storm`
- Evidence:
  - `data/artifacts/What a Feeling - Courtney Storm/validation/phase_1_report.json` reports beat match ratio near 0.30.
  - Generated boundaries show repeated sub-second drift against reference anchors and human-hint landmarks.
  - Section and event timing differences appear large enough to contaminate chord, section, and event comparisons.
- Validation target:
  - Produce a timing diagnosis that separates global offset, local drift, and beat-grid snapping error.
- Success condition:
  - The timing report explains the dominant failure mode and downstream artifacts use a timing basis that no longer masks chord and section evaluation.
- Notes:
  - This issue is a dependency for trustworthy comparison of several downstream layers.
  - Current mitigation: when Story 1.2 promotes the reference beat grid, section starts now stay on canonical bar anchors instead of being shifted one beat late by local novelty refinement.

### ISS-002 - Story 2.2 chord truth mismatch

- Status: `solved`
- Scope: harmonic inference for `What a Feeling - Courtney Storm`
- Evidence:
  - The current harmonic artifact diverges from the expected loop described during review.
  - `data/reference/What a Feeling - Courtney Storm/moises/chords.json` is the source of truth for chord validation in this repo.
  - Current phase validation does not yet provide enough attribution to separate timing-overlap misses from actual chord-label failures.
- Validation target:
  - Compare inferred chords against Moises chords with explicit miss attribution.
  - Define when a failing inferred result should trigger explicit reference-backed canonical promotion.
- Success condition:
  - The system can explain why chord mismatches happen for this song and either improve inference materially or promote the Moises-backed canonical chord output explicitly when inference fails.
- Notes:
  - Do not create a substitute custom fallback algorithm. If a different named model is tried, it must remain explicit and preserve provenance.
  - Implemented: inferred chords are validated first, explicit mismatch attribution is written to the report, failing inferred harmonic output is preserved under `data/artifacts/<Song - Artist>/harmonic_inference/layer_a_harmonic.inferred.json`, and the canonical harmonic layer is promoted from the Moises reference for downstream phases when the stricter gate fails.

### ISS-003 - Context-aware section semantics

- Status: `solved`
- Scope: section labeling behavior for `What a Feeling - Courtney Storm`
- Evidence:
  - Current sections are useful as lighting-energy summaries, but they do not express the richer context described in the human hints.
  - Generic structural labels such as `intro` or `verse` are not the desired target for this song.
  - The preferred direction is a context-aware vocabulary such as intimate chatter bed, soft vocal rise, arpeggiated lift, snare-only fade, instrumental plateau, and release tail.
- Validation target:
  - Propose and test a section vocabulary that is stable, musically meaningful, and compatible with downstream consumers.
- Success condition:
  - Section labels for this song become more context-aware without collapsing into generic pop-form labels or losing timing stability.
- Notes:
  - If structural form is still needed somewhere, preserve it separately instead of forcing the primary label field to carry both meanings.
  - Current progress: section labels now use a more contextual vocabulary (`momentum_lift`, `groove_plateau`, `contrast_bridge`, `focal_lift`, `flowing_plateau`, `breath_space`) and `data/output/<Song - Artist>/sections.json` now carries non-empty descriptions derived from those labels.

### ISS-004 - Event semantic under-representation

- Status: `solved`
- Scope: `song_event_timeline.json` and upstream event inference for `What a Feeling - Courtney Storm`
- Evidence:
  - Human-hint moments such as vocal entry, vocal tail-off, snare-only bar, and sustained instrumental passages were previously weakly represented or missing.
  - `data/artifacts/What a Feeling - Courtney Storm/validation/human_hints_alignment.md` now shows explicit `vocal_tail` overlap for `ui_004` and explicit `percussion_break` overlap for `ui_006`.
  - `data/output/What a Feeling - Courtney Storm/song_event_timeline.json` now exports `vocal_spotlight`, `vocal_tail`, `percussion_break`, and `instrumental_bed` events for the real song.
- Validation target:
  - Compare human-hint windows against generated events and identify which missing semantic concepts should be added or made more explicit.
- Success condition:
  - The event layer can express the musically important moments of this song without exploding into noisy micro-events.
- Notes:
  - Implemented: generic sustained-state plateaus can refine into canonical `groove_loop` and `atmospheric_plateau` event types when the evidence is strong enough, reducing reliance on the weaker `no_drop_plateau` label.
  - Implemented: stem-aware context scoring, human-hint-guided event promotion, and optional Moises lyric-line timing are now used as weak priors for `vocal_spotlight`, `vocal_tail`, and `percussion_break` when the overlapping stem evidence agrees.

### ISS-005 - Symbolic phrasing and alignment gaps

- Status: `solved`
- Scope: `layer_b_symbolic.json` for `What a Feeling - Courtney Storm`
- Evidence:
  - Human hints describe long vocal and arpeggiated phrases that are only partially reflected in the current symbolic artifact.
  - Some note events remain unresolved against the beat grid, which weakens phrase-level interpretation.
- Validation target:
  - Inspect alignment failures and compare perceived phrases against symbolic note grouping and density summaries.
- Success condition:
  - Symbolic output becomes reliable enough to support phrase-level reasoning for this song, especially around vocal-rise and arpeggiated-lift passages.

### ISS-006 - Pattern granularity mismatch

- Status: `solved`
- Scope: `layer_d_patterns.json` and pattern mining outputs for `What a Feeling - Courtney Storm`
- Evidence:
  - Current pattern outputs emphasize longer loops while the human hints repeatedly describe one-bar and two-bar behaviors.
  - The present grouping loses some phrase-level repetition detail that matters for this track.
- Validation target:
  - Compare current detected pattern windows against the repeated one-bar and two-bar gestures described in the hints and against the validated chord timeline.
- Success condition:
  - Pattern outputs preserve the musically relevant repeated structure at the right scale for this song.

### ISS-007 - Chord inference model quality after canonical fallback

- Status: `solved`
- Scope: inferred harmonic quality for `What a Feeling - Courtney Storm` after the canonical fallback contract is in place
- Evidence:
  - The canonical harmonic output is now corrected operationally through explicit Moises promotion, but the preserved inferred harmonic layer still mismatches the reference strongly enough to fail the stricter chord gate.
- Validation target:
  - Benchmark alternative named chord-recognition backends or improved decoding settings against the same Moises reference without removing the explicit fallback contract.
- Success condition:
  - The inferred harmonic layer materially closes the gap to the reference instead of depending on canonical promotion for this song.

## Session Split

### Session 1

- Create and maintain this tracker.
- Seed the initial queue.

### Session 2

- Work ISS-001.

### Session 3

- Work ISS-002.

### Session 4

- Work ISS-003.

### Session 5

- Work ISS-004.

### Session 6

- Work ISS-005.

### Session 7

- Work ISS-006.

### ISS-008 - Missing zero-start in section segmentation

- Status: `solved`
- Scope: `section_segmentation/sections.json` for all songs (specifically observed in `ayuni`)
- Evidence:
  - `sections.json` for `ayuni` begins after `0.0`, despite `fft_bands.json` showing active spectral energy (sub-band kicks) from the start.
  - Algorithmic novelty detection is likely missing the initial "state" as a "boundary."
- Validation target:
  - Ensure the first section of every song starts at exactly `0.0`.
- Success condition:
  - The section segmentation post-processor forces the first section start to `0.0` and snaps it to the beat grid.

### ISS-009 - Section Boundary Latency (Priority to Onsets)

- Status: `solved`
- Scope: `Best Friend - Sofi Tukker` (Epic 4.2)
- Evidence: 
  - `essentia/fft_bands.json` shows sub-band kicks at 19.0s.
  - `sections.json` places the `percussion_break` at 19.6s (snapping to grid), missing the physical 19.0s kick.
- Validation target:
  - Section boundaries must use the exact 19.0s onset timestamp.
- Success condition:
  - The 19.0s kick is the authoritative boundary, overriding the 19.6s beat grid anchor.

### ISS-010 - Missing Micro-Structure (Breaks and Pockets)

- Status: `solved`
- Scope: `Best Friend - Sofi Tukker` (Epic 4.2 / Epic 5)
- Evidence:
  - A 1-bar vocal gap (no drums) exists from 37.8s to 40.2s.
  - This window is currently ignored by the segmenter, merging it into the surrounding high-energy section.
  - **Clap Break:** 56.6s to 106.1s (near `contrast_bridge`) is not identified as a distinct structural/rhythmic shift.
  - **Percussion Break:** A distinct break starting at 115.5s is missing from the `sections.json` boundaries.
- Validation target:
  - Enable sensitivity for sub-phrase energy/percussion shifts (1-bar to 4-bar pockets).
- Success condition:
  - The windows at 37.8s, 56.6s, and 115.5s are identified as distinct structural states (e.g., `breath_space`, `percussion_break`) or high-confidence Events.
- Notes:
  - Lighting requires these "blackout" or "contrast" windows to be explicitly identified, even if they are shorter than a traditional musical "section."
- Notes:
  - This is a constitutional requirement for "Determinism" and "Clarity."