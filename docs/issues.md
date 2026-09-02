# Analysis Issue Tracker

## Purpose

This file is the **open** analysis-issue queue. It breaks broad quality problems
into focused, testable items that can be handled one at a time across sessions.

**It contains only pending issues.** When an issue is solved the entry is
removed in the same change; the closed entry stays recoverable in that commit. A
tracker whose entries are mostly closed stops being a queue and becomes a
history nobody can skim — see constitution §4.2.

## Status Convention

- `pending`: open, not yet fixed. **These are the only entries this file holds.**
- `solved`: the fix is verified, the relevant validation was rerun, and the
  success condition was met.

Do not mark an issue solved without updating its evidence, validation notes and
success-condition outcome. Then **delete the entry** — closing an issue and
removing it are one action, not two. If closing it established something durable
(a contract, a constraint, a measured number), write that into the relevant doc
or `CLAUDE.md` first; the issue text itself is scaffolding.

## Operating Rules

- Add newly discovered issues rather than rewriting older ones. This file is not cumulative — it is a queue.
- Scope each issue to one concrete problem, one validation target, and one success condition — and make the success condition mean the stage improved, not that one song stopped complaining.
- Prefer evidence from generated artifacts and documented reference files.
- Treat `data/analysis/<Song - Artist>/reference/` as read-only validation input.
- For chord truth, treat `data/analysis/<Song - Artist>/reference/moises/chords.json` as authoritative when it exists.
- For section semantics, prefer context-aware musical-state labels over generic form labels like `intro`, `verse`, or `chorus` unless a separate structural contract explicitly requires those labels.
- Human storytelling hints are review guidance. They are not direct replacements for harmonic, symbolic, or energy truth.

## Current focus song

- Song: `_test_song`
- Human hints: `data/analysis/_test_song/reference/human/human_hints.json`
- Chord reference: `data/analysis/_test_song/reference/moises/chords.json`
- Lyric timing clue: `data/analysis/_test_song/reference/moises/lyrics.json`
- Current validation report: `data/analysis/_test_song/artifacts/validation/phase_1_report.json`
- Human-hints alignment review: `data/analysis/_test_song/artifacts/validation/human_hints_alignment.json`

## Open queue

*Empty.*

All ten issues raised so far were closed; their entries were removed in commit
`c227bec` and remain recoverable there.

Worth knowing before adding the next one: the queue emptying does **not** mean
the analysis is in good shape. The 2026-09 measurement in
[`../experiments/drop_detection/README.md`](../experiments/drop_detection/README.md)
found the shipped section segmentation at 0/7 boundaries within +/-1.0 s of a
human-marked impact. Several closed issues touched that stage and passed narrow
per-song gates anyway. Scope new issues so that closing them means the stage
actually got better, not that one song stopped complaining.
