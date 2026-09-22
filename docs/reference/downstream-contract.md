# Reference — the downstream cue-authoring contract

**What this repo owes the external cue-authoring server.** That server is a
*separate repository* (`ai-dmx-light-render`, at `backend/src/app/mcp/`); it
reads our published analysis and authors `.cue.json` cue sheets against a rig.
This document is the contract its reads depend on — consult it before changing
anything projected.

Not to be confused with [`../mcp-definition.md`](../mcp-definition.md), which
defines the **in-repo `mcp/` module** — a different server with a different
purpose. Both read the same top-level files; only this one authors cues.

Reciprocal boundary: downstream authors must not reach into analyzer internals.
Downstream services (the cue-authoring server and its siblings) must consume
only the published top-level delivery surface (`data/analysis/{song}/*.json`) and
must not directly read files under `artifacts/` or other analyzer internals. The
contract is enforced both ways: this repo publishes the delivery surface and
downstream services consume it, not the other way around.

Field-level detail for each file: [`artifacts.md`](artifacts.md).

## The exposure rule

> **Exposed JSON lives only at `data/analysis/{song}/*.json`.**
> Nothing inside `artifacts/` or `reference/` is ever projected — to this
> consumer or any other.

There are exactly two tiers, and the boundary is the directory level:

| Tier | Who may read it |
| --- | --- |
| `data/analysis/{song}/*.json` — top level | the MCP server, the analyzer, the debugger UI |
| `…/artifacts/**`, `…/reference/**` | **the analyzer and the debugger UI only** |

Inner folders exist to *produce* the usable top-level files. They are raw
material, not a delivery surface. A signal that should reach the authoring model
must be **promoted into a top-level file by phase 4** — it is not enough that
the value exists somewhere under `artifacts/`.

So a proposal of the form "the server can read
`artifacts/<producer>/<file>.json`" is invalid on its face. The correct shape is
"phase 4 merges this into `<top-level>.json`."

This tightens the reach test rather than replacing it: the reach test asks
*which projected file does this land in*, and this rule constrains the legal
answers to the top-level directory.

## What actually reaches the model

| MCP read | Backs which pass | Files it projects |
| --- | --- | --- |
| `list_songs()` | discovery | `song_name`, `bpm`, `duration` only |
| `get_song_overview(song)` | concept pass (whole song) | `info.json`, `beats.json`, `sections.json`, `genre.json`, `song_event_timeline.json` (transitions only), `arrangement_state.json`, `hints.json` (human hints) |
| `get_detail(song, section_id\|gesture_id\|start_ms+end_ms\|bars, interval_ms, sources)` | one span (section, gesture, arbitrary window, or — v3.7 item 3/5 — a `[start_bar, end_bar]` bar range) | `loudness.json` + `drum_events.json` dense frames (**at most 5 s**), plus the overlapping structural rows (phases, transitions, hints, `arrangement_state` blocks, and — v3.6 item 9 — `beats.json` rows) with no decimation; every time field carries a sibling `position` (v3.7 item 3/5) |

All of these are top-level files. **Everything under `artifacts/` is invisible
to cue authoring** — the layer files and the `validation/` reports are worth
generating as *upstream inputs* to the files above, but polishing their prose or
schema does nothing for the show unless phase 4 promotes the signal into a
top-level file.

This table is the reach test. Before building anything, name the row it lands in.

## The join key: `section_id`

`section_id` (e.g. `"section-004"`) ties the whole analysis together. The
section pass is selected by it, and the server filters hints, events and the
beat grid by matching it.

- **Top-level `sections.json` is the only file the server reads for sections**,
  and it carries `section_id` itself. One row per section, in time order.
- `hints.json` `sections[].section_id` and every `song_event_timeline.json`
  event's `section_id` must use these exact ids. One that does not resolve is
  dropped from the section read.

The exposure rule removes a fragile coupling here. Previously the server read
section *names* from `artifacts/section_segmentation/sections.json` and matched
them to top-level `sections.json` **by array index** — same count, same order,
with a mismatch silently misaligning every label and confidence in the song.
Merging those fields into the one top-level file dissolves that failure mode
entirely.

## The confidence posture

The honesty rules, as the server enforces them structurally:

- **Confidence is always its own numeric field**, never folded into a display
  string. `sections.json` carries `function_confidence` directly — there is no
  `label` field to read a confidence out of.
- **Never inflate.** The concept pass reads a weak label as "don't spend tokens
  corroborating this." An honest `0.27` beats a manufactured `0.7`;
  `genre.json` predicting `"ambient" @ 0.27` for a 130 BPM track is a correct,
  useful output.
- `drum_events.json` states its `null` confidence **once, at file level**
  (`confidence` + `confidence_reason`), not repeated on 32,213 corpus rows with
  no information gained.
- Every top-level file carries a `field_sources` header: the default producer
  per field, declared once. A row carries its own `source` only where it
  departs from that default — a repeated per-row map on hundreds of rows is
  pure token cost. `source` (which producer) is distinct from `provenance`
  (how much human review). Per-file defaults:
  [`artifacts.md`](artifacts.md) "`field_sources` per file".

## File-by-file contract

Times are **seconds (float)**; the MCP layer multiplies by 1000. Keep prose
short — projected strings are either truncated or paid for in full.

**v3.7 item 6.** `hints.json` and `song_event_timeline.json` rows attribute
`section_id` by *timestamp* against the same published `sections.json` —
never `artifacts/section_segmentation/sections.json` (allin1's raw,
coarser-boundary table). Before this fix a hint or gesture event inside a
human-curated finer boundary (e.g. a pre-chorus split out of a coarser
allin1 run) could report the wrong, coarser section's id. `field_sources`
names the attribution producer `"sections"` for this field on both files.

### `position` — musical addressing, `get_detail` only (v3.7 item 3/5)

Seconds remain the only stored/joined unit everywhere in `src/`. `get_detail`
(never `get_song_overview` — its byte budget is load-bearing, see
`docs/issues.md`) derives `{"bar", "beat", "section_id", "resolved"}` on read,
beside every time field it serializes: the resolved span itself, section/
phase/transition/hint edges, `impact_alignment.impact_position`, arrangement
blocks and vocals phrases, drum-event rows, and every dense loudness frame.

- `section_id` is always the **published** `sections.json` (v3.7 item 6 — see
  below), matched by containment.
- `resolved: false` marks a bar read by tempo arithmetic across a downbeat
  whose `downbeat_confidence` is `null`, rather than a bar/beat read straight
  off a detected beat row — never present a guessed bar as detected. Only 3
  of 4 beats in a 4/4 bar carry a non-null `downbeat_confidence` on their own
  row (only the downbeat row does); `resolved` looks up the *bar's* downbeat
  row, never a beat row's own (usually-null) field.
- `get_detail`'s `bars: [start_bar, end_bar]` scope selector (inclusive,
  1-indexed) is the inverse: it resolves to `[start_bar beat 1, (end_bar+1)
  beat 1)` off the same beat grid, extrapolating by tempo arithmetic when a
  bar falls outside the published grid.

### `sections.json` (top-level **object**, rows under `sections`) — highest priority

Row fields: `section_id`, `start`, `end`, `function`, `function_confidence`,
`function_status`, `same_label_as`, `confidence`, `key`, `impact_alignment`
(+ `contested_by` on a flagged row).

- `key` — the whole-song HPCP key estimate (`"C# major"`), or `null` when too
  low-confidence to state. One value for the whole song; every row carries the
  same string or the same `null`, never a per-section key.
- Row order and count must equal the segmentation file.
- **Dropped in v3.6 item 8**: `label` (a display string folding
  `function_confidence` into text, e.g. `"003 Build [unverified] (0.45)"`),
  and `description` (a sentence restating `function` + ordinal). Neither was
  read downstream. Both now live in
  `artifacts/section_segmentation/sections_display.json`, joined by
  `section_id` — **not MCP-exposed**; the debugger UI reads it directly. A
  consumer wanting a per-section headline sentence must build one from
  `function` + `function_confidence` + `function_status` on this row.

### Section function fields — merged into `sections.json`

These come from allin1's segmentation and now belong on the top-level row rather
than in a second file:

- `function` — the Harmonix label allin1 predicts: `intro`, `verse`, `chorus`,
  `bridge`, `inst`, `solo`, `break`, `outro`. A **fixed model vocabulary**; do
  not extend it by hand.
- `function_confidence` — `1 −` normalised entropy of allin1's frame-level label
  posterior over the section's span. How sure the *model* was, independent of
  `confidence`.
- `function_status` — `"known"`, `"unknown"` or `"contested"`. `"unknown"`
  means allin1's labelling for the *whole song* is outside the distribution it
  can reliably name; the boundary is still usable, the name is not.
  `"contested"` means a phase-3 stage (`contest-section-function`) cross-checked
  `function` against the published `loudness.json` + `arrangement_state.json`
  and found the section's measured energy contradicts the label (e.g. a
  `chorus` quieter and thinner than the `verse`/`bridge` that follows it). The
  label is **kept and flagged, never flipped** — `function` and
  `function_confidence` are unchanged. A contested row also carries
  `contested_by: "energy"` (absent on every other row). Treat a contested row
  like `unknown` for pacing purposes (fall back to `loudness.json` /
  `arrangement_state.json`), while noting the label may still be structurally
  correct. Deliberately conservative — flags only a handful of sections across
  the corpus, concentrated on Eurovision-shaped songs.
- `same_label_as` — **label repetition, not acoustic identity.** It points at
  the first section given the same functional label: "the third thing it called
  a chorus," never "the same music as the first chorus." Surface it with that
  caveat; never describe grouped sections as verified-identical.

### Energy / tension / rhythm clue fields — merged into `sections.json` (v3.6 item 10)

A section row optionally carries `energy` (1–5), `energy_confidence`,
`tension` (1–5), `tension_confidence`, and `rhythm` — a musical fact, not a
light instruction: "drums go `quarter` → `sixteenth` across the build" is in
scope, "strobe at 12 Hz" is the authoring model's call.

- `rhythm` is `{<source>: {subdivision, confidence, onsets_per_beat}}` for
  `source` in `drums`, `bass`, `harmonic`, `vocals`. `subdivision` is one of
  `half`, `quarter`, `eighth`, `sixteenth`, `eighth_triplet`, `none`.
  `onsets_per_beat` is present only where a discrete onset count actually
  backs the call (the drum-IOI and vocal-word-onset producers); the
  autocorrelation producer has no onset count and omits the key rather than
  guessing one.
- **Any of these fields may be entirely absent from a row** — a section with
  no resolved clue on a field simply omits it. Never a guessed default.
- **Precedence, per field, per section:** 1) the operator's value in
  `reference/human/segments.json` — source `human`; 2) the highest-confidence
  of the ported candidate producers (`energy_level`, `tension_shape`,
  `rhythm_drum_ioi`, `rhythm_stem_autocorr`, `rhythm_vocal_onsets`) that
  computed a value for that field on that section; 3)
  `reference/human/segments.seed.json` — source `seed_unreviewed`,
  `confidence` explicitly `null` (inferred, not yet operator-reviewed); 4)
  otherwise absent. Produced by the phase-3 `section-clues` stage
  (`src/analyzer/stages/section_clues.py`), which re-fuses the
  already-published `sections.json` — never mutates from scratch.
- **`field_sources` per-row overrides.** The file header declares one default
  producer per field (`energy`, `energy_confidence`, `tension`,
  `tension_confidence`, and the dotted `rhythm.drums` / `rhythm.bass` /
  `rhythm.harmonic` / `rhythm.vocals`, the same per-sub-field convention
  `arrangement_state.json`'s `vocals_phrase.sibilance` already uses). A row
  whose actual source differs from that default carries a sparse override:
  `energy_source` / `tension_source` on the row, or a `source` key inside the
  specific `rhythm.<name>` object. No override key when the row matches the
  file default.
- **Not independent validation while provisional.** All five candidate
  producers were scored against `segments.seed.json`, which shares each
  producer's own method — a self-consistency check, not ground truth. Treat
  any `energy`/`tension`/`rhythm` value on a song outside the 4 segment songs
  (`ayuni`, `Cinderella - Ella Lee`, `_test_song`, `What a Feeling - Courtney
  Storm`) as a first-pass inference, same posture as `function_status:
  "unknown"`.

### `impact_alignment` — merged into `sections.json` (v3.7 item 2)

Every row carries `impact_alignment`, always present (never omitted, unlike
`energy`/`tension`/`rhythm`) but `null` when no gesture `impact` event
(`song_event_timeline.json`) falls within **+-2 bars** of the row's `start` —
an honest omission, never a nearest-match at any distance. When resolved:

```json
"impact_alignment": {
  "gesture_id": "gesture-034",
  "impact_time": 131.1,
  "offset_s": 3.83,
  "offset_beats": 7.889,
  "impact_position": {"bar": 66, "beat": 2, "section_id": "section-008", "resolved": true}
}
```

- `gesture_id` / `impact_time` — the nearest impact event to `start`.
- `offset_s` — signed, `impact_time - start`. **Positive means the payoff is
  late** — the section boundary is not where the gesture peaks.
- `offset_beats` — `offset_s` converted to beats at the song's whole-song
  `bpm` (`info.json`), assuming 4/4 (corpus-wide assumption).
- `impact_position` — the impact's musical position (item 3/5's `position`
  shape). **Stored as `null`** by `section_clues.py` — seconds are the only
  stored/joined unit — and backfilled on read by `mcp/serializers.py`'s
  `position` deriver.
- Never moves a boundary and never derives `tension` from the offset — both
  stay exactly as their own tier produced them. The offset is data for the
  authoring model to weigh, not a verdict.
- `field_sources` gains `impact_alignment: "impact_alignment"` (always —
  the field is never conditionally omitted like the clue fields above it).
- Produced by `src/analyzer/stages/section_clues.py`'s
  `_nearest_impact_alignment`, in the same fusion pass as `energy`/`tension`/
  `rhythm` above (reuses that stage's already-loaded `sections.json` +
  `song_event_timeline.json`).
- `get_song_overview`'s response gains a `review_warning` field — present
  only when at least one section row in the response carries a
  `seed_unreviewed` source on any field, naming the affected `section_id`s.
  Omitted entirely (not `null`, not empty) when none do. Exact text: *"energy/
  tension/rhythm sourced `seed_unreviewed` are inferred, not yet reviewed by
  the operator; verify on the final show."*

### `song_event_timeline.json` (top-level) — high priority

Produced by the phase-3 `gestures` stage. `events[]`, each a **flat** row
(never a composite with nested `phases[]`): `type`, `start_time`, `end_time`,
`confidence`, `intensity`, `section_id` (+ `gesture_id` on a gesture-phase row).

- `type` is either a gesture-phase name (`approach`, `build`, `tension`,
  `impact`, `release`) or a section-pair transition `"<from> → <to>"`. **A drop
  is never named directly** — the vocabulary can say "a build of this shape
  happens here," never "this is the drop" (a drop is derived from a named section pair, never detected). A missing phase
  means no supporting primitive was found, never a guess.
- The server projects `type`, `start_time`, `end_time`, `intensity`,
  `confidence`, `section_id` (+ `gesture_id`) — this is now the *entire* row,
  not a scoped-down table of contents.
- **Dropped in v3.6 item 8**: `section_name` (duplicated the `section_id` join
  — resolve the name via `sections.json`), `summary` and `evidence_summary`
  (human-readable prose, unread downstream), and file-level `generated_from`
  (provenance now lives in `artifacts/` only). The full row shape — every
  field this file used to carry — is preserved in
  `artifacts/gestures/song_event_timeline.json`, **not MCP-exposed**; the
  debugger UI reads it directly.
- So: make `type`, the window, `intensity` and `confidence` (0–1) precise —
  that is now the whole of what a consumer sees for an event. There is no
  separate machine-events file.
- Every gesture-phase row belonging to one composite gesture carries a shared
  `gesture_id` (e.g. `"gesture-003"`), letting a consumer reconstruct a drop's
  full `approach → release` envelope by grouping on it without re-deriving the
  assembly. Section-transition rows carry no `gesture_id` key. Rows sharing a
  `gesture_id` are time-ordered and non-overlapping.

### `beats.json` (top-level **object**, rows under `beats`) — high priority

`time`, `beat`, `bar`, `type` (`"beat"` / `"downbeat"`), `downbeat_confidence`.

- Beat *times* are essentia's; the downbeat *phase* comes from allin1's
  activation, not a modulo. **Bar numbers shifted on most songs** when this
  changed — do not assume continuity with an older artifact.
- `downbeat_confidence` is `null` on `"beat"` rows always. On a `"downbeat"` row
  it is the activation strength, **unless** essentia and allin1 disagree by a
  whole beat or more for that bar, where it is `null` too. A consumer ranking
  cue placements should read `null` as "do not snap a cue here with confidence."
- The default projection derives tempo, `beats_per_bar`, `bar_count` and the
  **downbeat list**. Cue placement snaps to downbeats, so downbeat detection and
  bar numbering must be correct and continuous — and today they are **not fully
  trusted** ([`../analysis-definition.md`](../analysis-definition.md), "Downbeats").
- **Dropped in v3.6 item 8**: `chord` (unread). Chord inference was later
  removed from the analyzer entirely; nothing replaces this field.
- Per-beat *features* are not consumed; don't attach them here.

### `hints.json` (top-level) — high priority

**Restructured in v3.6 item 8, no longer nested.** Flat `hints[]`, each row
`{ section_id, title, text, start_time, end_time, lighting_hint }`. No
`sections[]` wrapper, no `summary` block.

- Every row is `source: "human"` by construction — the inference-hint
  generator was deleted, not just filtered, so there is no `"inference"` case
  left to distinguish. `source` is declared once in the file's `field_sources`
  header (never per row).
- Dropped along with the wrapper: `id`, `category`, `anchor_refs` (all unread;
  `anchor_refs` pointed at stages that no longer exist).
- `reference/human/human_hints.json` is the sole source, matched to a section
  via `hint_alignment.find_primary_section`; a hint with no overlapping section
  gets `section_id: "unsectioned"`, never dropped for that reason.
- A row's `text` is its `summary` verbatim, falling back to `title`; a row is
  dropped only when both are empty. `lighting_hint` is `null` when absent —
  never dropped for that.
- Keep hints **few and concrete**. A hint earns its place if it names a
  moment, a contrast, or an intent — never a restated texture description.

### `info.json`

Consumed: `bpm`, `duration`. The beat grid is the primary tempo source;
`info.json` `bpm` is the fallback. Keep `duration` accurate — it sets the show's
end.

### `genre.json` (top-level)

`genres`, `confidence` — passed through to the concept pass.

- **Dropped in v3.6 item 8**: `top_predictions[]` (unread) and `guidance[]`
  (one identical text across all 23 songs). Item 9 moved the equivalent text
  into the in-repo `mcp/` server's `get_song_overview` tool description
  (`mcp/server.py`) — that surface does not reach this downstream consumer,
  which never sees tool descriptions, only file reads. Both fields stay in
  `artifacts/genre.json`, **not MCP-exposed**; the debugger UI reads it
  directly. This consumer gets no `guidance` text at all any more — if it
  needs the equivalent review-caution prose, it must be restated here or
  re-added to the top-level file, not assumed still present.

### The detail files

`loudness.json` and `drum_events.json` are the **only** dense files a section
pass can pull. `arrangement_state.json` is structural, not dense — it is
returned whole (no decimation) alongside a dense read whenever its blocks
overlap the requested span. `beats.json` (v3.6 item 9) is likewise structural:
every beat inside the resolved span, undecimated, present even when the span
exceeds the 5 s dense cap — the one deliberate exception to "no full beat
list", since it is always scoped to the span, never the whole song.

**The window is capped at 5 s — that is a maximum, not a default.** A caller
asking for a whole section gets a refusal, not a truncation. Most detail reads
should be much shorter than the cap; the cap exists so one read can never
swallow the authoring context.

**The resolution is the caller's choice.** `interval_ms` is a request parameter,
not a property baked in at publish time: the server decimates the published
series to whatever the client asks for. A concept pass wanting a coarse envelope
and a section pass chasing a transient are the same file read at different
resolutions.

- `loudness.json` — flat top-level `interval_ms` (**20 ms**, the published
  floor and the finest a client may request) and `source_order` (the stem
  order `values[]` is indexed against — **v3.6 item 8 moved both out of a
  `metadata` wrapper to flat fields**), `frames[] { time, values[],
  normalized_values[] }` aligned to `source_order`. Keep the stem set complete
  and the interval regular. This is a **published projection** of the 10 ms
  `artifacts/essentia/rms_loudness.json`, not a copy — that artifact is ~18 MB
  per song and embeds absolute host paths, neither of which belongs on a
  delivery surface. **Dropped in v3.6 item 8**: `sources[]` (the stem-identity
  list — unread) and `metadata.sample_rate` / `duration` / `total_frames` /
  `normalization_scope` (unread). All remain on the artifact, **not
  MCP-exposed**; the debugger UI reads it directly for stem identity and full
  metadata.
- `drum_events.json` — `events[] { time, event_type }`. Accurate onsets and a
  small consistent `event_type` set (`kick` / `snare` / `hat` / `crash` /
  `unresolved`) — `crash` is a brilliance-gated split of pitch-42 `hat` events
  (drums-stem 6–16 kHz gate); a consumer switching on `event_type` should treat
  it as a distinct, brighter cue than `hat`. This is the rhythmic backbone for
  chase and strobe timing. **Dropped in v3.6 item 8**: per-event `confidence`
  — every one of the 32,213 corpus events already carried `null` (Omnizart
  emits no per-hit confidence signal), so the file now states this **once, at
  file level**: `confidence: null` + `confidence_reason: "<why>"`. `velocity`
  is still not published (constant 100). The full per-event artifact
  (`artifacts/symbolic_transcription/drum_events.json`, same lack of
  confidence) is unchanged and **not MCP-exposed**; the debugger UI reads it
  directly.
- `arrangement_state.json` — **required** as of v3.6 item 9 (previously
  optional, absent on a song analysed before v3.2; every song in the current
  corpus already carries it). `blocks[] { start_s, end_s, playing[],
  entered[], left[], margin_db, confidence }`: who is playing and where that
  changes. `confidence = round(1 -
  exp(-margin_db / 6.0), 3)`, a monotone report of the dB headroom at the
  smallest stem flip — not a tuned score, so a consumer wanting its own
  threshold reads raw `margin_db`. The leading block (before the first stem
  change) carries `margin_db: null` / `confidence: null`, never a filled
  default.

  **New in v3.5**, alongside `blocks[]` and independent of it:
  `vocals_phrase[] { start_s, end_s, confidence, sibilance }` — a second,
  separate read on the vocals stem from the promoted `whisperx_vad` detector
  (its own pipeline service since v3.6 item 2 — the `whisperx` Compose
  service, run before `./analyze`), and `vocals_sibilance_song_mean` (a
  float, or `null`). These do **not**
  modify `blocks[]`: the `vocals` entry inside `playing[]` is still the
  RMS-derived claim it always was. **`vocals_phrase[]` is the channel to
  trust for voice presence** — a consumer wanting to know whether a voice is
  audible should read it, not `blocks[].playing`. `playing`'s `vocals` is a
  stem-energy reading that also fires on instrument leakage into the vocal
  stem (measured false_vocal_rate 0.0891 on `ayuni`, vs whisperX's 0.0056 on
  the same song). It is kept as-is: gating it on
  whisperX agreement was measured — it raised `frame_acc` on `ayuni` but cost
  more than the 0.01 tolerance on `Cinderella - Ella Lee` (0.9342 → 0.9159 at
  best), so no gate shipped — this is the settled state, not a pending one.

  - `confidence` on a phrase is **always exactly `1.0`** — an operator
    directive, not a measurement: a detected phrase is asserted certain and
    the detector's own graded per-span confidence is discarded at publish.
    Do not weight phrases by it; it carries no information. It is the one
    place in this contract where a confidence is not a graded score, and it is
    deliberate.
  - `vocals_phrase` is **never `null`** once `arrangement_state.json` exists —
    the detector's compute step cannot run inside the `app` image (an
    incompatible torch pin against the natten ABI lock), so it runs as its own
    Compose service (`whisperx`) that must be run for a song before
    `./analyze`; `publish-arrangement-state` fails loudly rather than
    publishing without it. An empty list `[]` is the real claim "ran, found no
    phrases".
  - `sibilance` is a **relative** stem-bleed discriminator and is meaningless
    read absolutely — compare it against the sibling
    `vocals_sibilance_song_mean`, which is the same cue's per-song noise
    floor. A phrase well below the song mean is the vocal detector firing on
    instrument bleed rather than a voice. **No gate is applied at publish
    time**: the value is reported and the judgement is the consumer's.
    `sibilance: null` on a phrase means the span covered no analysed frame —
    never 0.0, which would read as "measured, and silent".
  - **New in v3.7 item 7**: `peak`, `mean` (normalized vocals loudness, off
    `loudness.json`) and `peak_time` (seconds) are stored on the top-level
    `vocals_phrase[]` row. `get_detail`'s projection additionally derives
    `peak_position` (bar/beat) from `peak_time` on read — the bar/beat
    `position` itself is never stored, matching every other `position` field
    in this contract.

**New in v3.7 — `get_detail`'s structural view gains three blocks, none
decimated or dense-cap-gated (structural facts, like `arrangement_state` and
`beats` above):**

- **`stem_summary` (item 7)** — per requested stem (respecting `sources`
  narrowing), `{ peak, mean, peak_position }` over the resolved span, from
  `loudness.json`'s normalized-loudness series. **Served on every call,
  including spans past the 5 s dense cap** — the cap withholds dense frames,
  not this summary. Answers "how loud is X here" without a client having to
  fetch and hand-average multiple 5 s dense reads.
- **`drum_density` (item 8)** — one row per bar in the resolved span, per
  instrument (`kick`, `snare`, `hat`, `crash`): `{ bar, instrument, count,
  subdivision, changed_from_previous, position }`. `subdivision` is
  `quarter`/`eighth`/`sixteenth`/`none`/`mixed`, from the ratio of that bar's
  own average inter-onset interval to that bar's own beat period (never a
  fixed corpus-wide period). `none` for zero onsets; a **single** onset
  reports `mixed` (no spacing to measure a periodicity from — never guessed
  as `quarter`). `changed_from_previous` compares against the previous bar
  actually present in the response (a bar with no published beat is skipped,
  not treated as unchanged). Per-hit confidence stays `null` at source
  (Omnizart) — stated once at block level from `drum_events.json`'s own
  `confidence`/`confidence_reason` pair, never re-derived or repeated per row.
- **`dropouts` (item 9)** — per stem (`bass`, `drums`, `harmonic`, `vocals`),
  every span of **two beats or more** (`min_gap_beats`) with no onset
  (`drums`, from `drum_events.json`) or at that stem's own 5th-percentile
  normalized-loudness floor (the rest, from `loudness.json` — an unvalidated
  per-song heuristic, reported not tuned, same posture as
  `arrangement_state`'s own `margin_db`): `{ stem, start, end, start_position,
  end_position, disagreement }`. Where `arrangement_state` calls a stem
  absent for a block and this item's own measurement finds it present, that
  block is **also** emitted with `disagreement: true` and
  `sources: { measured, arrangement_state }` naming both producers — never
  resolved automatically. Measured on `What a Feeling - Courtney Storm`: the
  pre-chorus block (`start_s: 112.75, end_s: 127.0, confidence: 0.163`)
  disagrees as expected (drum_events shows dense onsets throughout, 4-8
  onsets/s); several further `drums`-absent blocks from 127 s to the end of
  the song disagree the same way at much higher `arrangement_state`
  confidence (up to 0.963) — `arrangement_state`'s own drums call appears
  unreliable for this song past 112.75 s, not just in the one pre-chorus
  block the operator had already flagged by hand.
- A new dense signal (spectral flux, onset strength) needs a top-level file and
  a registry entry in the server's `detail.py` — **propose it** rather than
  hoping a layer file gets read.

## Priorities, in order

1. **Section boundaries + `section_id` + `function` + honest confidences, all
   on the top-level row.** Everything hangs off this.
2. **`song_event_timeline.json`** — a lean set of well-timed gesture phases and
   transitions with `intensity` and honest `confidence`.
3. **`hints.json`** — short, concrete, per-section, human hints.
4. **`beats.json`** — correct, continuous downbeats and bar numbers.
5. **`loudness.json` + `drum_events.json`** — accurate, regular, complete.
6. **`genre.json`** — honest, with `genres` + `confidence` kept.
7. **`arrangement_state.json`** — required (v3.6 item 9); accurate stem
   entered/left spans with honest `confidence`/`margin_db`, plus the
   independent `vocals_phrase[]` read described above.

## Not worth optimizing for this consumer

- Anything under `artifacts/` or `reference/` — structurally not on the MCP
  surface, whatever its quality.
- Multi-paragraph prose anywhere in the top-level files.
- Per-beat feature streams and dense series other than the two detail artifacts.
- Confidence inflated to look authoritative — the consumer is explicitly built
  to distrust it.

## Changing this contract

A change to any file above requires a handoff note to `ai-dmx-light-render`,
delivered and then deleted. Compatibility with this consumer is **not** a
constraint — musical correctness outranks it.
