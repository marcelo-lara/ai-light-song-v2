# Analysis Input Guide — what the light-show MCP server needs from `data/analysis/`

**Audience:** the ML pipeline (`ai-song-analysis`) that generates
`data/analysis/<Song_Name>/`. This repo treats that folder as a **read-only
input** (see [data_folder_reference.md](../data_folder_reference.md)). This
document says which parts of that input actually reach the model that authors
a light show, so pipeline effort lands where it changes the result.

## 1. How this repo consumes analysis (post-v1.4)

The cue-authoring model never reads `data/analysis/` files directly. It reads
**projections** served by the MCP server (`backend/src/app/mcp/`), and every
field in a projection is charged as tokens to the authoring context. v1.4
scoped those reads hard, so the surface is now small and specific:

| MCP read | Backs which pass | Source files it projects |
| --- | --- | --- |
| `get_song_brief(song)` | concept pass (whole song) | `info.json`, `beats.json`, top-level `sections.json` + `artifacts/section_segmentation/sections.json`, `artifacts/genre.json` |
| `get_analysis(song, part=…, section=…)` | section pass (one section) | `sections.json` (+ segmentation), `beats.json`, `hints.json`, `song_event_timeline.json`, `genre.json` |
| `get_analysis_detail(song, artifact, start_ms, end_ms)` | section pass, sub-section moments | **only** `artifacts/essentia/rms_loudness.json` and `artifacts/symbolic_transcription/drum_events.json` |

**Everything else under `artifacts/` is invisible to cue authoring.** The
layer files (`layer_a_harmonic`, `layer_c_energy`), the
`event_inference/` internals, and the `validation/`
reports are not on the MCP surface. They can still be worth generating as
*upstream inputs to the seven top-level files*, but polishing their prose or
schema does nothing for the show unless the signal is promoted into one of
the files in the table above.

## 2. The join key: `section_id`

`section_id` (e.g. `"section-004"`) is the primary key that ties the whole
analysis together. The section pass is selected by `section_id`, and the MCP
server filters hints, events, and the beat grid by matching it.

Requirements:

- **`artifacts/section_segmentation/sections.json` is the only file that
  carries `section_id`.** Its `sections[]` rows must each have
  `section_id`, `function`, `function_confidence`, `function_status`,
  `same_label_as`, `confidence`, `start`, `end`.
- The top-level `sections.json` list is **matched to the segmentation list by
  array index** — same count, same order. A mismatch silently misaligns
  every section's label and confidence.
- `hints.json` `sections[].section_id` and every
  `song_event_timeline.json` event's `section_id` must use these exact ids.
  An event or hint whose `section_id` does not resolve is dropped from the
  section read.

## 3. The confidence posture (load-bearing)

The operator's standing rule: confidence-bearing analysis is **inference,
never premise**. The MCP server enforces this structurally, and the pipeline
must feed it:

- **Confidence is always its own numeric field.** Never fold it into a
  display string. The top-level `sections.json` `label` (`"003 Chorus
  (0.81)"`) is a display convenience only; the real value must also exist as
  the segmentation row's `function_confidence: 0.81`.
- **Pass through the source's own `guidance` prose.** `genre.json`'s
  `guidance` array is surfaced verbatim; keep writing it, and add the
  equivalent to any other inferred artifact.
- **A low confidence is a useful signal — do not inflate it.** The concept
  pass reads a weak label as "don't spend tokens corroborating this." An
  honest `0.27` is more valuable than a manufactured `0.7`. `genre.json`
  predicting `"ambient" @ 0.27` for a 130 BPM track is a correct, useful
  output.
- Every discrete event and every section carries `confidence` **and**
  `provenance` (`"machine-only"`, `"reviewed"`, `"human-confirmed"`, …).

## 4. File-by-file contract

Times are **seconds (float)** in every top-level file; the MCP layer
multiplies by 1000. Keep prose short — projected string fields are billed to
the model, and long fields are either truncated by the projection or paid for
in full.

### `sections.json` (top-level, JSON array) — highest priority

One row per section, in time order. Consumed fields: `start`, `end`,
`label`, `description`.

- `description`: **one sentence**, concrete and lighting-relevant ("Energy
  and motion climb together into a more assertive forward push"). This is the
  concept pass's main per-section signal. Not a paragraph.
- Row order and count must equal `artifacts/section_segmentation/sections.json`.

### `artifacts/section_segmentation/sections.json` — highest priority

`sections[]` with `section_id`, `function`, `function_confidence`,
`function_status`, `same_label_as`, `confidence`, `start`, `end`.

- `function` is the Harmonix functional label allin1 predicts:
  `intro`, `verse`, `chorus`, `bridge`, `inst`, `solo`, `break`, `outro`. It is
  a fixed model vocabulary, not an editable tag set — do not extend it by hand.
- `function_confidence` is `1 −` normalised entropy of allin1's own frame-level
  label posterior across the section's span — how certain the model itself
  was about this name, independent of `confidence`.
- `function_status` is `"known"` or `"unknown"`. `"unknown"` means allin1's
  labelling for the *whole song* is outside the distribution it can reliably
  name (too few distinct labels, or one label dominating the track); the
  section's boundary is still usable, its name is not. Treat an `"unknown"`
  row's `function` as unverified, never as a confident label.
- `function` + `same_label_as` drives `get_song_brief`'s `similar_sections`
  grouping (sections sharing a `function`, chained through `same_label_as`,
  are proposed as reusable look pairs). **`same_label_as` names label
  repetition, not acoustic identity** — it points at the first section
  allin1 gave the same functional label, which says "the third thing it
  called a chorus," not "the same music as the first chorus." Surface it to an
  operator or a cue author with that caveat; do not describe grouped sections
  as verified-identical.

### `song_event_timeline.json` (top-level) — high priority

Generated for model consumption (`engine: llm-friendly-event-timeline-v1`).
`events[]`, each with: `type`, `start_time`, `end_time`, `confidence`,
`intensity`, `section_id`, `section_name`, `provenance`, `summary`, and
optionally `lighting_hint`, `evidence_summary`.

- Unscoped, the MCP server projects **only** `type`, `start_time`,
  `end_time`, `intensity`, `section_id` (a table of contents). The prose
  `summary` / `lighting_hint` are delivered **only** when a section pass asks
  for its own section.
- So: make `type`, the time window, and `intensity` (0–1) precise — those are
  what the concept pass sees for the whole song. Make `summary` genuinely
  actionable for the section pass — a musical description of the moment, not
  boilerplate ("Impact hits remain single-beat candidates" is an internal
  note, not a cue hint).
- Favor **few high-value discrete events** (drops, builds, impacts, energy
  resets, breakdowns, layer adds/drops, vocal entries) with tight time
  ranges over a dense stream. Tighter `[start_time, end_time]` = better cue
  placement.
- `lighting_hint` should stay musical/high-level ("treat as a musical cue,
  not a fixture instruction") — this repo owns the fixture mapping.

### `beats.json` (top-level, JSON array) — high priority

One row per beat: `time`, `type` (`"beat"` / `"downbeat"`), `bar`, `beat`.

- The default projection derives tempo, `beats_per_bar`, `bar_count`, and
  the **downbeat list**. Cue placement snaps to downbeats and bar numbers, so
  downbeat detection and bar numbering must be correct and continuous.
- The full per-beat list is available on request; per-beat *features* are
  not consumed — don't attach them here.

### `hints.json` (top-level) — high priority

The editable-merge document (`engine: editable-hints-merge-v1`):
`sections[]` keyed by `section_id`, each with `hints[]` of `{ id, source,
category, text, anchor_refs }`, plus `summary.user_hint_count` /
`inference_hint_count`.

- `source` distinguishes `"inference"` from human hints. **Merge
  `data/analysis/<song>/reference/human/human_hints.json` in as
  `source: "human"` hints** under the matching section — the human hints are
  timed, specific, and high-signal (this is already done for
  `human_hints_alignment.json`; extend it to the consumer `hints.json`).
- Keep inference hints **few and concrete**. Vague shape descriptions
  ("layered section with undulating contour, dense activity") cost tokens and
  rarely change a cue. A hint earns its place if it names a moment, a
  contrast, or an intent.
- `category` should be a short tag (`strobe`, `movement`, `intensity`,
  `transition`, `color`, `phrase_boundary`, `motif_recall`).
- Drop hints with an empty `lighting_hint` / `text`; fold any useful
  `summary` into `text`.

### `info.json` (top-level)

Consumed: `bpm`, `duration`. The beat grid is the primary tempo source;
`info.json` `bpm` is the fallback. Keep `duration` accurate — it sets the
show's end.

### `artifacts/genre.json`

`genres`, `confidence`, `top_predictions[] {label, confidence}`,
`guidance[]`. All passed through to the concept pass. See §3 — honest
confidences, keep the guidance prose.

### `artifacts/essentia/rms_loudness.json` and `artifacts/symbolic_transcription/drum_events.json`

The **only** two dense artifacts a section pass can pull, and only in windows
≤ 15 s.

- `rms_loudness.json`: `metadata.interval_ms`, `sources[]` (e.g. `mix`,
  `drums`, `bass`, `vocals`, `harmonic`), `frames[] { time, values[] }` with
  `values` aligned to `sources`. Per-stem loudness at fixed interval is what
  lets a section pass drive intensity from the mix or a single stem — keep
  the stem set complete and the interval regular.
- `drum_events.json`: `events[] { time, event_type, confidence }`. Accurate
  onset times and a small, consistent `event_type` set (kick, snare, hat,
  fill, …) matter; this is the rhythmic backbone for chase and strobe timing.
- If a new dense signal would be valuable (e.g. a spectral-flux or
  onset-strength stream), it is one registry entry in `detail.py` — propose
  it rather than hoping a layer file gets read.

## 5. Priorities for the ML module

1. **Section boundaries + `section_id` + `function` + honest
   `function_confidence` / `confidence` + a one-line `description`.**
   Everything hangs off this.
2. **`song_event_timeline.json`:** a lean set of well-timed discrete events
   with `intensity`, honest `confidence`, `section_id`, and an actionable
   `summary`.
3. **`hints.json`:** short, concrete, per-section; human hints merged in.
4. **`beats.json`:** correct, continuous downbeats and bar numbers.
5. **`rms_loudness.json` + `drum_events.json`:** accurate, regular,
   complete stem/'event-type coverage.
6. **`genre.json`:** keep it honest and keep the guidance prose.

## 6. What is *not* worth optimizing for this consumer

- The intermediate layer files, `event_inference/` internals, pattern
  mining, and `validation/` reports — not on the MCP surface. Useful only as
  upstream inputs to the seven top-level files.
- Multi-paragraph prose anywhere in the top-level files — projections keep
  short fields and the model pays per token.
- Per-beat feature streams and sub-100 ms dense series other than the two
  registered detail artifacts.
- Confidence values inflated to look authoritative — the consumer is
  explicitly built to distrust them.
