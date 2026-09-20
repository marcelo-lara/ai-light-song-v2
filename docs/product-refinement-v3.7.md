# Product refinement — v3.7

**Status: backlog.** No implementation plan yet, nothing started. This doc is
the worklist the next release draws from; items are added here as they are
decided and only turn into `implementation-plan-v3.7.md` when the release opens.

**Goal:** make the debugger's review verdicts measurable. The corpus has 21
songs and 4 with operator-reviewed segments, so "how good is this producer"
is answerable on the gold four and nowhere else. Hand-marking is what costs;
a per-block verdict is cheap, and it measures the one thing hand-marked truth
cannot — whether what a producer *emitted* is real.

---

## 1. Block verdicts — a precision instrument in the debugger — `ui/`, `experiments/truth_common/`

**Current behaviour.** Every experiment and inference lane can be played
against the waveform, and the operator can hear that a block is wrong — but
there is nowhere to record that. The only operator-writable review surfaces are
`human_hints.json` (authored spans), `segments.json` (authored sections),
`block_energy.json` (per-block 1-5 ratings) and `lyric_validations.json` (a
`validated_ids` list). All four record *what the operator asserts*; none
records *a judgement on what a producer emitted*.

The consequence is written up as the largest unmeasured risk in the shipped
pipeline ([`issues.md`](issues.md), "`gestures` — per-primitive precision has
never been audited by ear"): gestures is scored on impact **recall** against
seven hand-clicked impacts, so a phantom riser or build — a cue that
contradicts the song — moves no metric at all. That issue's stated validation
method is already "auditioned in the debugger against the waveform"; it is
blocked only on having somewhere to put the verdict.

**Change.** A three-state verdict control on each block of a claim-bearing
lane, written to a new operator file.

`data/analysis/{song}/reference/human/block_reviews.json`:

```json
{
  "schema_version": "1.0",
  "song_name": "Armin - Revolution",
  "reviews": [
    {
      "lane_id": "gestures",
      "start": 48.712,
      "verdict": "correct",
      "reason": null,
      "note": "",
      "reviewed_at": "2026-09-19T14:02:11Z"
    }
  ]
}
```

| Field | Values |
| --- | --- |
| `verdict` | `correct` — real and correctly described · `wrong` — nothing is here, a phantom · `misplaced` — something real is here but this block gets it wrong |
| `reason` | `null` on `correct`; otherwise one of `boundary` (right event, wrong start/end), `label` (right span, wrong type or name), `value` (right span and label, wrong number) |
| `note` | free text, for the human reader only — never parsed |

`verdict` and `reason` are fixed vocabularies because they are counted;
`note` is not. This is the opposite of `human_hints.json`, which stays
informative-only prose — a reviews file exists to be tallied.

**Join key.** `(lane_id, start)`, `start` rounded to 3 decimal places — the
convention the UI already uses to match spans. On a re-run a review whose
`start` matches no emitted block within **±0.25 s** (the repo's own
beat-alignment tolerance) is **stale**: shown as stale in the lane and skipped
by the scorer, never silently dropped and never silently re-attached to a
neighbouring block. Block ids (`gesture-003`, `segment-seed-007`) are array
positions and must not be the key — they shift on every re-run.

**Lanes.** Every lane carrying an `experiment` field in
[`ui/src/timeline/laneState.ts`](../ui/src/timeline/laneState.ts), plus
`gestures` (shipped, and the lane the open issue names). Not the reference
lanes (`moisesSections`, `moisesLyrics`) or the human lanes — those are truth
or authored input, not claims to be judged.

**UI.** The verdict control sits in the block inspector and on each card of the
lane events panel, following `SegmentedRating`'s existing per-block pattern; a
reviewed block is tinted in the lane so coverage is visible without opening
anything. Saved per click through `PUT /api/block-reviews/{song}` in
[`ui/vite.config.ts`](../ui/vite.config.ts), beside the four existing write
handlers.

**Scorer.** A new family in `experiments/truth_common/` reads
`block_reviews.json` — it is under `reference/human/`, the only tier that
module reads — and emits a per-lane, per-song table: block count, reviewed
count, and the three-way split, with `wrong` reported separately from
`misplaced` because a phantom and a late boundary are different defects with
different fixes. Precision is `correct / reviewed`.

**Why it matters.** It measures precision, which no current instrument does at
all, and it does so on any song rather than the gold four — the coverage
problem that leaves 17 songs unscored. It also gives rival producers for one
signal (the three `rhythm*` lanes, `energyLevel` vs. `tensionShape`) a
head-to-head on the same song without a ground-truth file existing for it.

**Out of scope.**

- **Recall.** Verdicts attach only to blocks that were emitted, so a producer
  that emits nothing scores a perfect precision. Recall stays measured against
  hand-marked truth on the gold songs, and a precision figure must never be
  quoted as an accuracy figure. Marking misses costs roughly what hand-marking
  costs, which is the expense this item exists to avoid.
- **Any effect on published output.** A verdict scores a producer and does
  nothing else. `wrong` does not suppress a block at publish time: the shipped
  files must be identical whether or not a song has been reviewed, or the show
  a song gets starts depending on how much attention it happened to receive.
  Promotion and fusion precedence stay operator decisions informed by the
  number, not automatic gates on it.
- **Reaching the authoring model.** Nothing here is published. `block_reviews.json`
  is `reference/`, validation-only; it reaches the show only by changing which
  producer an operator promotes.

| | |
| --- | --- |
| Writes | `data/analysis/{song}/reference/human/block_reviews.json` (new, operator-written); a new `experiments/truth_common/` scorer family + its report rows |
| Reads changed | `ui/vite.config.ts` (new PUT handler), `ui/src/data/` (paths, loader, parser, save module), `ui/src/panel/BlockInspector.tsx`, `ui/src/panel/LaneEventsPanel.tsx`, `ui/src/timeline/laneState.ts` |
| Done when | a verdict survives a page reload and an analyzer re-run of the same song; a re-run that moves a block past ±0.25 s marks its review stale rather than re-attaching it; and a per-primitive precision figure exists for each gesture phase across the four gold songs — closing [`issues.md`](issues.md)'s gestures entry, with the false-positive bound written into `CLAUDE.md` |
