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
| `get_detail(song, section_id\|gesture_id\|start_ms+end_ms, interval_ms, sources)` | one span (section, gesture, or arbitrary window) | `loudness.json` + `drum_events.json` dense frames (**at most 5 s**), plus the overlapping structural rows (phases, transitions, hints, `arrangement_state` blocks) with no decimation |

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

- **Confidence is always its own numeric field.** `sections.json`'s `label`
  (`"003 Chorus (0.81)"`) is a display convenience; the real value must also
  exist as `function_confidence: 0.81`.
- **Pass through the source's own `guidance` prose** — `genre.json`'s
  `guidance` array is surfaced verbatim.
- **Never inflate.** The concept pass reads a weak label as "don't spend tokens
  corroborating this." An honest `0.27` beats a manufactured `0.7`;
  `genre.json` predicting `"ambient" @ 0.27` for a 130 BPM track is a correct,
  useful output.
- Every event and section carries `confidence` **and** `provenance`.
- Every top-level file carries a `field_sources` header: the default producer
  per field, declared once. A row carries its own `source` only where it
  departs from that default — a repeated per-row map on hundreds of rows is
  pure token cost. `source` (which producer) is distinct from `provenance`
  (how much human review). Per-file defaults:
  [`artifacts.md`](artifacts.md) "`field_sources` per file".

## File-by-file contract

Times are **seconds (float)**; the MCP layer multiplies by 1000. Keep prose
short — projected strings are either truncated or paid for in full.

### `sections.json` (top-level **object**, rows under `sections`) — highest priority

Consumed: `start`, `end`, `label`, `description`, `key`, `chord_progression`.

- `description` — **one sentence**, concrete and lighting-relevant. This is the
  concept pass's main per-section signal. Not a paragraph.
- `key` — the whole-song HPCP key estimate (`"C# major"`), or `null` when too
  low-confidence to state. One value for the whole song; every row carries the
  same string or the same `null`, never a per-section key.
- `chord_progression` — the section's dominant repeating sequence (`"Am–F–C–G"`),
  or `null` when any overlapping chord event falls below the confidence floor.
  **`null` is expected and honest on low-agreement songs**, not a bug — chord
  agreement measures 1.00/0.69/0.51/0.38 across the four gold songs
  ([`../analysis-definition.md`](../analysis-definition.md)).
- Row order and count must equal the segmentation file.

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

### `song_event_timeline.json` (top-level) — high priority

Produced by the phase-3 `gestures` stage. `events[]`, each a **flat** row
(never a composite with nested `phases[]`): `type`, `start_time`, `end_time`,
`confidence`, `intensity`, `section_id`, `section_name`, `provenance`,
`summary`, `evidence_summary`.

- `type` is either a gesture-phase name (`approach`, `build`, `tension`,
  `impact`, `release`) or a section-pair transition `"<from> → <to>"`. **A drop
  is never named directly** — the vocabulary can say "a build of this shape
  happens here," never "this is the drop" (a drop is derived from a named section pair, never detected). A missing phase
  means no supporting primitive was found, never a guess.
- Unscoped, the server projects **only** `type`, `start_time`, `end_time`,
  `intensity`, `section_id` — a table of contents. `summary` and
  `evidence_summary` arrive only when a section pass asks for its own section.
- So: make `type`, the window and `intensity` (0–1) precise — that is what the
  concept pass sees for the whole song. Make `summary` actionable for the
  section pass ("a rising riser builds into an impact here"), never an internal
  implementation note.
- Every row already carries its own evidence (`"high-band r2=0.82 over 4 bars,
  delta=0.31x range"`). There is no separate machine-events file.
- Every gesture-phase row belonging to one composite gesture carries a shared
  `gesture_id` (e.g. `"gesture-003"`), letting a consumer reconstruct a drop's
  full `approach → release` envelope by grouping on it without re-deriving the
  assembly. Section-transition rows carry no `gesture_id` key. Rows sharing a
  `gesture_id` are time-ordered and non-overlapping.

### `beats.json` (top-level **object**, rows under `beats`) — high priority

`time`, `type` (`"beat"` / `"downbeat"`), `bar`, `beat`, `confidence`.

- Beat *times* are essentia's; the downbeat *phase* comes from allin1's
  activation, not a modulo. **Bar numbers shifted on most songs** when this
  changed — do not assume continuity with an older artifact.
- `confidence` is `null` on `"beat"` rows always. On a `"downbeat"` row it is
  the activation strength, **unless** essentia and allin1 disagree by a whole
  beat or more for that bar, where it is `null` too. A consumer ranking cue
  placements should read `null` as "do not snap a cue here with confidence."
- The default projection derives tempo, `beats_per_bar`, `bar_count` and the
  **downbeat list**. Cue placement snaps to downbeats, so downbeat detection and
  bar numbering must be correct and continuous — and today they are **not fully
  trusted** ([`../analysis-definition.md`](../analysis-definition.md), "Downbeats").
- Per-beat *features* are not consumed; don't attach them here.

### `hints.json` (top-level) — high priority

`engine: editable-hints-merge-v1`. `sections[]` keyed by `section_id`, each with
`hints[]` of `{ id, source, category, text, anchor_refs }`, plus
`summary.user_hint_count` / `inference_hint_count`.

- `source` distinguishes `"inference"` from `"human"`.
  `reference/human/human_hints.json` is merged in under the matching
  `section_id` via `hint_alignment.find_primary_section`.
- Keep inference hints **few and concrete**. "Layered section with undulating
  contour, dense activity" costs tokens and changes no cue. A hint earns its
  place if it names a moment, a contrast, or an intent.
- `category` is a short tag (`strobe`, `movement`, `intensity`, `transition`,
  `color`, `phrase_boundary`) — **inference hints only**. Human hints never
  carry one: they span everything from a drop impact to a calm vocal passage
  ("Breath"), and none of the six tags honestly fits that range, so the key is
  omitted rather than guessed (no silent fallbacks — never guess to keep a run green).
- A human hint's `text` is its `summary` verbatim, falling back to `title`. It
  is dropped only when both are empty — never for having no overlapping section
  (it lands under a synthetic `"unsectioned"` section) and never for an empty
  `lighting_hint`. `lighting_hint`, `title`, `start_time` and `end_time` pass
  through as their own fields.

### `info.json`

Consumed: `bpm`, `duration`. The beat grid is the primary tempo source;
`info.json` `bpm` is the fallback. Keep `duration` accurate — it sets the show's
end.

### `genre.json` (top-level)

`genres`, `confidence`, `top_predictions[] {label, confidence}`, `guidance[]` —
all passed through to the concept pass.

### The detail files

`loudness.json` and `drum_events.json` are the **only** dense files a section
pass can pull. `arrangement_state.json` is structural, not dense — it is
returned whole (no decimation) alongside a dense read whenever its blocks
overlap the requested span.

**The window is capped at 5 s — that is a maximum, not a default.** A caller
asking for a whole section gets a refusal, not a truncation. Most detail reads
should be much shorter than the cap; the cap exists so one read can never
swallow the authoring context.

**The resolution is the caller's choice.** `interval_ms` is a request parameter,
not a property baked in at publish time: the server decimates the published
series to whatever the client asks for. A concept pass wanting a coarse envelope
and a section pass chasing a transient are the same file read at different
resolutions.

- `loudness.json` — `metadata.interval_ms` (**20 ms**, the published floor and
  the finest a client may request), `sources[]` (mix, drums, bass, vocals, harmonic),
  `frames[] { time, values[] }` aligned to `sources`. Keep the stem set complete
  and the interval regular. This is a **published projection** of the 10 ms
  `artifacts/essentia/rms_loudness.json`, not a copy — that artifact is ~18 MB
  per song and embeds absolute host paths, neither of which belongs on a
  delivery surface.
- `drum_events.json` — `events[] { time, event_type, confidence }`. Accurate
  onsets and a small consistent `event_type` set (`kick` / `snare` / `hat` /
  `crash` / `unresolved`) — `crash` is a brilliance-gated split of pitch-42
  `hat` events (drums-stem 6–16 kHz gate); a consumer switching on `event_type`
  should treat it as a distinct, brighter cue than `hat`. `confidence` is
  always `null` (Omnizart emits no per-event confidence); `velocity` is not
  published (constant 100). This is the rhythmic backbone for chase and strobe
  timing.
- `arrangement_state.json` — **optional**, absent on a song analysed before
  v3.2. `blocks[] { start_s, end_s, playing[], entered[], left[], margin_db,
  confidence }`: who is playing and where that changes. `confidence = round(1 -
  exp(-margin_db / 6.0), 3)`, a monotone report of the dB headroom at the
  smallest stem flip — not a tuned score, so a consumer wanting its own
  threshold reads raw `margin_db`. The leading block (before the first stem
  change) carries `margin_db: null` / `confidence: null`, never a filled
  default.
- A new dense signal (spectral flux, onset strength) needs a top-level file and
  a registry entry in the server's `detail.py` — **propose it** rather than
  hoping a layer file gets read.

## Priorities, in order

1. **Section boundaries + `section_id` + `function` + honest confidences + a
   one-line `description`, all on the top-level row.** Everything hangs off this.
2. **`song_event_timeline.json`** — a lean set of well-timed gesture phases and
   transitions with `intensity`, honest `confidence` and an actionable `summary`.
3. **`hints.json`** — short, concrete, per-section, human hints merged.
4. **`beats.json`** — correct, continuous downbeats and bar numbers.
5. **`loudness.json` + `drum_events.json`** — accurate, regular, complete.
6. **`genre.json`** — honest, with the guidance prose kept.
7. **`arrangement_state.json`** — optional; when present, accurate stem
   entered/left spans with honest `confidence`/`margin_db`.

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
