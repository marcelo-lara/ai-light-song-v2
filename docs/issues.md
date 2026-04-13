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
- Current validation report: `data/artifacts/What a Feeling - Courtney Storm/validation/phase_1_report.json`
- Human-hints alignment review: `data/artifacts/What a Feeling - Courtney Storm/validation/human_hints_alignment.json`

## Active Queue

### ISS-001 - Beat and boundary alignment drift

- Status: `pending`
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

### ISS-002 - Story 2.2 chord truth mismatch

- Status: `pending`
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

### ISS-003 - Context-aware section semantics

- Status: `pending`
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

### ISS-004 - Event semantic under-representation

- Status: `pending`
- Scope: `song_event_timeline.json` and upstream event inference for `What a Feeling - Courtney Storm`
- Evidence:
  - Human-hint moments such as vocal entry, vocal tail-off, snare-only bar, and sustained instrumental passages are weakly represented or missing.
  - Current events overuse generic energy/event types for moments that need clearer semantic names.
- Validation target:
  - Compare human-hint windows against generated events and identify which missing semantic concepts should be added or made more explicit.
- Success condition:
  - The event layer can express the musically important moments of this song without exploding into noisy micro-events.

### ISS-005 - Symbolic phrasing and alignment gaps

- Status: `pending`
- Scope: `layer_b_symbolic.json` for `What a Feeling - Courtney Storm`
- Evidence:
  - Human hints describe long vocal and arpeggiated phrases that are only partially reflected in the current symbolic artifact.
  - Some note events remain unresolved against the beat grid, which weakens phrase-level interpretation.
- Validation target:
  - Inspect alignment failures and compare perceived phrases against symbolic note grouping and density summaries.
- Success condition:
  - Symbolic output becomes reliable enough to support phrase-level reasoning for this song, especially around vocal-rise and arpeggiated-lift passages.

### ISS-006 - Pattern granularity mismatch

- Status: `pending`
- Scope: `layer_d_patterns.json` and pattern mining outputs for `What a Feeling - Courtney Storm`
- Evidence:
  - Current pattern outputs emphasize longer loops while the human hints repeatedly describe one-bar and two-bar behaviors.
  - The present grouping loses some phrase-level repetition detail that matters for this track.
- Validation target:
  - Compare current detected pattern windows against the repeated one-bar and two-bar gestures described in the hints and against the validated chord timeline.
- Success condition:
  - Pattern outputs preserve the musically relevant repeated structure at the right scale for this song.

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