# MCP definition — the boundary with the downstream server

**The contract analysis quality is judged against.** The MCP server is a
*separate repository* (`backend/src/app/mcp/`); this document says what we owe
it, so pipeline effort lands where it changes the show.

The cue-authoring model never reads `data/analysis/` directly. It reads
**projections**, and every projected field is billed as tokens to the authoring
context.

## What actually reaches the model

| MCP read | Backs which pass | Files it projects |
| --- | --- | --- |
| `get_song_brief(song)` | concept pass (whole song) | `info.json`, `beats.json`, `sections.json` + `artifacts/section_segmentation/sections.json`, `artifacts/genre.json` |
| `get_analysis(song, part=…, section=…)` | section pass (one section) | `sections.json` (+ segmentation), `beats.json`, `hints.json`, `song_event_timeline.json`, `genre.json` |
| `get_analysis_detail(song, artifact, start_ms, end_ms)` | sub-section moments | **only** `artifacts/essentia/rms_loudness.json` and `artifacts/symbolic_transcription/drum_events.json` |

**Everything else under `artifacts/` is invisible to cue authoring.** The layer
files and the `validation/` reports are not on the MCP surface. They are worth
generating as *upstream inputs* to the files above, but polishing their prose or
schema does nothing for the show unless the signal is promoted into one of them.

This table is the reach test (the reach test — docs/mcp-definition.md). Before building anything, name
the row it lands in.

## The join key: `section_id`

`section_id` (e.g. `"section-004"`) ties the whole analysis together. The
section pass is selected by it, and the server filters hints, events and the
beat grid by matching it.

- **`artifacts/section_segmentation/sections.json` is the only file that carries
  `section_id`.** Rows need `section_id`, `function`, `function_confidence`,
  `function_status`, `same_label_as`, `confidence`, `start`, `end`.
- The top-level `sections.json` list is **matched by array index** — same count,
  same order. A mismatch silently misaligns every label and confidence.
- `hints.json` `sections[].section_id` and every `song_event_timeline.json`
  event's `section_id` must use these exact ids. One that does not resolve is
  dropped from the section read.

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

## File-by-file contract

Times are **seconds (float)**; the MCP layer multiplies by 1000. Keep prose
short — projected strings are either truncated or paid for in full.

### `sections.json` (top-level array) — highest priority

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
  ([`analysis-definition.md`](analysis-definition.md)).
- Row order and count must equal the segmentation file.

### `artifacts/section_segmentation/sections.json` — highest priority

- `function` — the Harmonix label allin1 predicts: `intro`, `verse`, `chorus`,
  `bridge`, `inst`, `solo`, `break`, `outro`. A **fixed model vocabulary**; do
  not extend it by hand.
- `function_confidence` — `1 −` normalised entropy of allin1's frame-level label
  posterior over the section's span. How sure the *model* was, independent of
  `confidence`.
- `function_status` — `"known"` or `"unknown"`. `"unknown"` means allin1's
  labelling for the *whole song* is outside the distribution it can reliably
  name. The boundary is still usable; the name is not.
- `same_label_as` — **label repetition, not acoustic identity.** It points at
  the first section given the same functional label: "the third thing it called
  a chorus," never "the same music as the first chorus." It drives
  `get_song_brief`'s `similar_sections` grouping, so surface it with that
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

### `beats.json` (top-level array) — high priority

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
  trusted** ([`analysis-definition.md`](analysis-definition.md), "Downbeats").
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

### `artifacts/genre.json`

`genres`, `confidence`, `top_predictions[] {label, confidence}`, `guidance[]` —
all passed through to the concept pass.

### The two detail artifacts

`artifacts/essentia/rms_loudness.json` and
`artifacts/symbolic_transcription/drum_events.json` are the **only** dense
artifacts a section pass can pull, and only in windows ≤ 15 s.

- `rms_loudness.json` — `metadata.interval_ms`, `sources[]` (mix, drums, bass,
  vocals, harmonic), `frames[] { time, values[] }` aligned to `sources`. Keep
  the stem set complete and the interval regular.
- `drum_events.json` — `events[] { time, event_type, confidence }`. Accurate
  onsets and a small consistent `event_type` set; this is the rhythmic backbone
  for chase and strobe timing.
- A new dense signal (spectral flux, onset strength) is one registry entry in
  the server's `detail.py` — **propose it** rather than hoping a layer file gets
  read.

## Priorities, in order

1. **Section boundaries + `section_id` + `function` + honest confidences + a
   one-line `description`.** Everything hangs off this.
2. **`song_event_timeline.json`** — a lean set of well-timed gesture phases and
   transitions with `intensity`, honest `confidence` and an actionable `summary`.
3. **`hints.json`** — short, concrete, per-section, human hints merged.
4. **`beats.json`** — correct, continuous downbeats and bar numbers.
5. **`rms_loudness.json` + `drum_events.json`** — accurate, regular, complete.
6. **`genre.json`** — honest, with the guidance prose kept.

## Not worth optimizing for this consumer

- Intermediate layer files and `validation/` reports — not on the MCP surface.
- Multi-paragraph prose anywhere in the top-level files.
- Per-beat feature streams and dense series other than the two detail artifacts.
- Confidence inflated to look authoritative — the consumer is explicitly built
  to distrust it.

## Changing this contract

A change to any file above requires a handoff note to the downstream repo
(measured evidence does not go stale), delivered and then deleted. Compatibility is **not** a
constraint (musical correctness outranks compatibility) — musical correctness outranks it.
