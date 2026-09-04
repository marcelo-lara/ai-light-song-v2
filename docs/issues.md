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
- `data/analysis/<Song - Artist>/reference/moises/chords.json` is Moises.ai inference, not chord truth: it carries no confidence field, so a chord comparison against it measures agreement with a second model, not correctness.
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

### `validate-chords` crashes on every song that has a real Moises chord reference

- **Status:** `pending`
- **Found:** 2026-09-04, during plan v3.0 item 5. Not caused by it.
- **Symptom:** `./analyze --song "Titanium - David Guetta ft Sia.mp3"` exits
  non-zero after `extract-hpcp-and-chords` with `KeyError: 'bar_num'`.
- **Cause:** `src/analyzer/stages/validation/chords.py` lines 62-63 read
  `row["bar_num"]` and `row["beat_num"]` from `reference/moises/chords.json`.
  The real file carries no such keys — its rows are
  `curr_beat_time`, `curr_beat`, `prev_chord`, `chord_complex_jazz`,
  `chord_simple_jazz`, `chord_complex_pop`, `chord_simple_pop`. On Titanium
  **487 of 487 rows** lack both. Line 49 of the same function already reads
  `curr_beat_time` correctly, so only those two lines are wrong: the validator
  was written against a Moises schema that the files in `reference/` are not.
- **Why it went unnoticed:** the now-deleted `build_reference_timing_grid` read
  the same two fields defensively, as `int(row.get("bar_num") or 0)`, so it
  never raised — it silently produced `bar: 0` for every row and then fell back
  to the `((index - 1) // 4) + 1` modulo it was supposed to be replacing. The
  validator uses direct subscripting and therefore fails loudly. Nothing had run
  this path against real reference data before.
- **Validation target:** `validate-chords` on the four gold songs.
- **Success condition:** `./analyze` completes on all four gold songs with a
  real chord-agreement number reported for each, and no song reports `skipped`
  because of a schema mismatch. Reading `curr_beat` is not enough on its own —
  the bar/beat position it needs must either be derived honestly from the
  pipeline's own grid or the check must state that it cannot be computed.
- **Blocks:** plan v3.0 item 16 (the corpus re-run). Scheduled into item 10,
  which owns the validation surface.

All ten issues raised so far were closed; their entries were removed in commit
`c227bec` and remain recoverable there.

Worth knowing before adding the next one: the queue emptying does **not** mean
the analysis is in good shape. The 2026-09 measurement in
[`../experiments/drop_detection/README.md`](../experiments/drop_detection/README.md)
found the shipped section segmentation at 0/7 boundaries within +/-1.0 s of a
human-marked impact. Several closed issues touched that stage and passed narrow
per-song gates anyway. Scope new issues so that closing them means the stage
actually got better, not that one song stopped complaining.
