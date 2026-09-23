# Product refinement — v3.7

**Status: implemented.** See
[`implementation-plan-v3.7.md`](implementation-plan-v3.7.md) for what shipped
per item, including two user-facing decisions (D10.1, D11.1) that changed the
MCP write-mount posture and dropped an auto-rerun mechanism from the plan as
originally scoped.

**Goal:** make the debugger's review verdicts measurable. The corpus has 21
songs and 4 with operator-reviewed segments, so "how good is this producer"
is answerable on the gold four and nowhere else. Hand-marking is what costs;
a per-block verdict is cheap, and it measures the one thing hand-marked truth
cannot — whether what a producer *emitted* is real.

**Second goal:** make the MCP answer in the terms its readers reason in —
sections, bars and beats — and serve the derived views a reader currently
computes by hand from raw series (items 2–7). Every item here was needed, and
worked around, during one review of *What a Feeling – Courtney Storm*.

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

---

## 2. `impact_alignment` — a late payoff as data, not as a cross-reference — `src/analyzer/stages/section_clues.py`

**Current behaviour.** `sections.json` carries each section's `start`/`end`;
`song_event_timeline.json` carries each gesture's `impact_time`. Nothing joins
them, so "does this section's payoff land on its boundary?" is answerable only
by a reader holding both files open and subtracting. Downstream, the authoring
model's concept pass makes one `get_song_overview` call that returns both — and
has no instruction to compare them.

**Change.** A derived `impact_alignment` object on each section row, fused by
`section-clues` (3.4), which already reads `sections.json` and
`song_event_timeline.json` for `tension_shape`.

```json
"impact_alignment": {
  "gesture_id": "gesture-034",
  "impact_time": 131.1,
  "offset_s": 3.83,
  "offset_beats": 7.9,
  "impact_position": {"bar": 66, "beat": 2, "resolved": true}
}
```

| Field | Meaning |
| --- | --- |
| `gesture_id`, `impact_time` | the gesture impact nearest this section's `start` |
| `offset_s` | signed, `impact_time - start`. **Positive means the payoff is late** — the boundary is not the peak |
| `offset_beats` | `offset_s` in beats at the song's BPM, so a threshold can be musical rather than absolute |
| `impact_position` | the impact's musical position, per item 3 |

`null` when no impact falls within **±2 bars** of the boundary — an honest
omission, never a nearest-match at any distance. `field_sources` gains
`impact_alignment: "impact_alignment"`.

**Why it matters.** A late payoff is invisible in every field that exists
today. On *What a Feeling – Courtney Storm* it happens twice: section-008
starts 127.27 s against an impact at 131.10 (`+3.83`), section-010 starts
157.95 against 158.45 (`+0.50`). Both sections read `energy 5, tension 3` —
flat and released — while the section is still building. A show lit on the
boundary peaks early, which is one of the two failures that actually cost a
light show.

**Out of scope.**

- **Moving any boundary.** This field describes the gap; it never closes it.
  `start`/`end` stay exactly as their tier produced them.
- **Deriving `tension` from it.** `tension` is operator-set on reviewed songs
  and outranks inference. A late impact is evidence a human may want to raise
  a section's tension, not a trigger that raises it.
- **A "late" flag.** The threshold is the consumer's: a 0.5 s offset matters
  to a cue and not to a plan narrative. Publish the number, not a verdict.

| | |
| --- | --- |
| Writes | `impact_alignment` on each `sections.json` row, plus its `field_sources` entry |
| Reads changed | `src/analyzer/stages/section_clues.py` (fusion + the nearest-impact search); `docs/reference/downstream-contract.md`, `docs/reference/source-map.md` |
| Done when | both *What a Feeling* boundaries above emit the stated offsets; a section with no impact within ±2 bars emits `null`; and the field survives a `--stage section-clues` re-run |

---

## 3. Musical addressing — every time carries its bar, beat and section — `mcp/serializers.py`, `mcp/server.py`, `src/analyzer/stages/hints.py`, `src/analyzer/stages/gestures.py`

**Current behaviour.** Every time the MCP returns is seconds. Bar and beat
exist only on `beats` rows, so "where is this in the song" means scanning the
beat list by hand, and "what happens in bar 79" means fetching a whole section
to find bar 79's time. Separately, hint and gesture rows carry a `section_id`
attributed against allin1's own segmentation
(`artifacts/section_segmentation/sections.json`), not the published sections
table — so a hint inside the human pre-chorus is tagged `section-003`.

**Change.**

- **Every time field gains a `position` beside it:** `{"bar", "beat",
  "section_id", "resolved"}`. Seconds stay — they are the join key and the
  render contract. Applies to section edges, gesture phases and impacts,
  transitions, hints, arrangement blocks, vocal phrases, and dense-frame and
  drum-event rows.
- **`get_detail` accepts a bar range** as a fourth scope selector:
  `bars: [79, 80]`, inclusive. Still exactly one selector per call.
- **`section_id` everywhere means the published sections table.** Hints and
  gestures attribute by timestamp against `sections.json`, never allin1's
  segmentation.

`resolved: false` where the bar number is derived by tempo arithmetic from a
downbeat with null `downbeat_confidence`, rather than read from a detected
downbeat. This is load-bearing: on songs with a partly unresolved grid, a
guessed bar number presented as detected is worse than no bar number.

**Out of scope.** Changing any stored time to bars. Positions are derived on
read; seconds remain the only stored and joined unit.

| | |
| --- | --- |
| Writes | `position` on every time-bearing row; the `bars` selector |
| Reads changed | `mcp/serializers.py`, `mcp/server.py`; `hints.py` and `gestures.py` attribution input |
| Done when | on *What a Feeling*, `get_detail(bars=[79,80])` returns 155.83–159.70 s; the `Drums cut` hint reports `section-007`, not `section-003`; a bar derived across a null downbeat reports `resolved: false` |

---

## 4. Intensity summaries — per phrase, and per span above the dense cap — `mcp/serializers.py`, `src/analyzer/stages/arrangement_state.py`

**Current behaviour.** `vocals_phrase` rows carry start, end and sibilance but
no level. Above the 5 s cap, `get_detail` withholds the dense series entirely
and returns nothing about loudness. Answering "how loud is the chatter" took
twelve 5-second windows and a hand-computed peak and mean per phrase.

**Change.**

- `vocals_phrase` rows gain `peak` and `mean` (normalized vocals loudness) and
  the `position` of the peak.
- `get_detail`'s structural view gains `stem_summary`: per requested stem,
  `peak`, `mean` and peak `position` over the resolved span. **Served on every
  call, including over the cap** — the cap withholds frames, not facts.

**Out of scope.** Raising or removing the 5 s cap. A summary answers the
question the cap was blocking without reintroducing the payload it guards
against.

| | |
| --- | --- |
| Writes | `peak`/`mean`/peak `position` on `vocals_phrase`; `stem_summary` in `get_detail` |
| Done when | a `section_id`-scoped `get_detail` on *What a Feeling* section-006 returns per-stem levels with dense frames withheld |

---

## 5. Rhythm inside a section — per-bar drum density — `mcp/serializers.py`

**Current behaviour.** `rhythm.drums.subdivision` is one label per section.
The two findings that mattered most on *What a Feeling* — snares going to every
beat at bar 61 beat 3, the kick doubling in bar 79 — were invisible in it and
came only from hand-computing inter-onset intervals over raw `drum_events`.

**Change.** `get_detail`'s structural view gains `drum_density`: one row per
bar in the span, per instrument (`kick`, `snare`, `hat`, `crash`), with
`count` and the implied `subdivision` (`quarter`, `eighth`, `sixteenth`,
`none`, or `mixed`). A change in subdivision between consecutive bars is what
a reader is looking for, so it must be readable without diffing rows by hand:
each row carries `changed_from_previous`.

**Out of scope.** Per-hit confidence. omnizart emits none, and the existing
null stays null.

| | |
| --- | --- |
| Writes | `drum_density` in `get_detail` |
| Done when | on *What a Feeling*, snare subdivision reads `quarter` from bar 61 beat 3 and the kick reads `eighth` in bar 79, both flagged `changed_from_previous` |

---

## 6. Dropouts — spans where a stem goes silent — `mcp/serializers.py`

**Current behaviour.** Nothing lists absence. Two of *What a Feeling*'s key
findings were silences — a 2.6 s total drum cut before the chorus, and the
chatter going silent under each synth pulse — and both were found by noticing
that events stopped. Meanwhile `arrangement_state` reported the pre-chorus
drums absent for 14 s where `drum_events` shows them playing throughout, at a
0.163 confidence nobody downstream checks.

**Change.** `get_detail`'s structural view gains `dropouts`: per stem, every
span of **two beats or more** with no onsets (drums) or at the stem's noise
floor (the rest), with `position` at both edges. Where `arrangement_state`
calls a stem absent and onsets are present — or the reverse — the span is
emitted with `disagreement: true` and both producers named, so a low-margin
"absent" is visibly contested rather than silently wrong.

**Out of scope.** Resolving the disagreement. Report both; which producer is
right is a promotion decision, and item 1's verdicts are how it gets measured.

| | |
| --- | --- |
| Writes | `dropouts` in `get_detail` |
| Done when | *What a Feeling*'s drum cut is emitted at bar 62 beat 4 – bar 64 beat 1, its start `resolved: false` (bar 62's downbeat has null confidence); each chatter gap under a synth pulse is emitted; the pre-chorus drums span is emitted with `disagreement: true` |

---

## 7. Corrections through the MCP — as proposals, never as writes — `mcp/server.py`, `ui/`

**Current behaviour.** The MCP is read-only. Correcting an operator-set field
or adding a hint means editing `reference/human/*.json` on the host, then
running the one analyzer stage that consumes it — and a wrong stage name
reports success and writes nothing.

**Change.** Two MCP tools that **queue** a correction, never apply it:

- `propose_hint(song, start, end, title, summary, evidence)`
- `propose_section_field(song, section_id, field, value, evidence)` — `field`
  one of `energy`, `tension`, `rhythm.<stem>`

Proposals land in `reference/proposals/pending.json`, with `evidence` required.
The debugger UI lists them beside the existing operator-write surfaces; an
approval writes the change to `reference/human/` through the existing PUT
handlers and re-runs the stage that consumes it (`section-clues` for section
fields, `generate-section-hints` for hints). A rejection is kept, with its
reason, so the same proposal is not re-queued.

**Why proposals and not writes.** A human field outranks every inferred field
*because a person set it*. An MCP that writes `reference/human/` directly makes
`source: "human"` mean "whoever called the tool last" and dissolves the one
precedence rule the rest of the system trusts. The render server's
`propose_hint` already works this way for the authoring guide; this mirrors it.

**Out of scope.** Boundary edits. Moving a section edge changes every derived
field and needs a full pipeline run, not a single-stage republish.

| | |
| --- | --- |
| Writes | `reference/proposals/pending.json`; UI approve/reject surfaces |
| Reads changed | `mcp/server.py` (two tools), `ui/vite.config.ts`, `ui/src/panel/` |
| Done when | a proposed tension change, once approved in the UI, is served by `get_detail` with `tension_source: "human"` and no manual stage run; nothing proposed and unapproved ever appears in published output |
