# Contract changes — v3.1 delivery surface

Handoff note for the external cue-authoring consumer (`ai-dmx-light-render`).
One section per Phase B item of [`implementation-plan-v3.1.md`](implementation-plan-v3.1.md).
`SCHEMA_VERSION` moves `2.0` → `3.0` in this release (bumped once, in item 2).

---

## 2. The attribution convention

### ⚠️ `beats.json` and `sections.json` are now OBJECTS, not bare arrays

This is the change most likely to break a consumer **silently**. A reader that
iterates the file will now get an object and read nothing, with no error.

| File | Before | After |
| --- | --- | --- |
| `beats.json` | `[ {beat…}, … ]` | `{ "field_sources": {…}, "beats": [ {beat…}, … ] }` |
| `sections.json` | `[ {section…}, … ]` | `{ "field_sources": {…}, "sections": [ {section…}, … ] }` |

Migration: read `doc["beats"]` / `doc["sections"]` instead of iterating `doc`.
`info.json`, `hints.json` and `song_event_timeline.json` were already objects and
keep their top-level shape; they gain a `field_sources` key.

### `field_sources` header

Every top-level file now carries a `field_sources` object: the **default
producer for each field, declared once**. A row carries its own `source` string
**only** where it departs from that default (no `beats.json` row does — a
repeated per-row map on ~500 rows is pure token cost).

The producer vocabulary is **closed**: `essentia`, `allin1`, `harmonic`,
`omnizart`, `demucs`, `gestures`, `genre`, `human`, `inference`, `unknown`. An
unrecognised producer is a pipeline error, not a passthrough string. `unknown`
means no producer cleared its confidence floor — never "we didn't record it".

Per-file defaults are tabulated in
[`reference/artifacts.md`](reference/artifacts.md) "`field_sources` per file".

`source` (which producer) stays distinct from `provenance` (how much human
review: `machine-only` / `reviewed` / `human-confirmed`).

### `beats.json`: `confidence` → `downbeat_confidence`

The field renamed. It measures allin1's **downbeat-phase** strength (0.226 F1),
not essentia's beat time (trusted). The old unqualified name invited reading a
weak downbeat number as if it qualified the trusted beat time. Value semantics
are unchanged: `null` on `"beat"` rows and on downbeats where essentia's and
allin1's phases disagree by a whole beat or more.

### Fusion reads generated artifacts only

The publish path never reads `reference/` (a test enforces this on the fusion
stage). `reference/` stays validation-only.

---

## 3. Section function fields merged into top-level `sections.json`

Each `sections[]` row gains four fields, read from the allin1 segmentation at
build time and joined on `section_id` (never array position):

| Field | Source | Meaning |
| --- | --- | --- |
| `function` | `allin1` | Harmonix functional label (`verse`, `chorus`, …), or `null` |
| `function_confidence` | `allin1` | numeric confidence in that label, or `null` |
| `function_status` | `allin1` | `"known"` or `"unknown"` — treat `function` as unverified when `"unknown"` |
| `same_label_as` | `allin1` | `section_id` of the first section allin1 gave the same label; **label repetition, not acoustic identity** |

Before / after one row:

```
// before
{ "section_id": "section-003", "start": 41.2, "end": 66.8, "label": "003 Chorus (0.81)",
  "description": "...", "confidence": 0.81, "key": "C# minor", "chord_progression": "..." }
// after
{ "section_id": "section-003", "start": 41.2, "end": 66.8, "label": "003 Chorus (0.81)",
  "description": "...", "function": "chorus", "function_confidence": 0.81,
  "function_status": "known", "same_label_as": "section-002",
  "confidence": 0.81, "key": "C# minor", "chord_progression": "..." }
```

`label`, `description`, `key`, `chord_progression`, `confidence`, `section_id`,
`start`, `end` are unchanged.

**Consumer action:** a consumer may now read section names from the top-level
`sections.json` alone and **must stop reading
`artifacts/section_segmentation/sections.json`** — that inner file is not on the
delivery surface and the MCP server cannot serve it. The old array-index match
between the two files is dissolved: the top-level row now carries the join key
and the names together.

---

## 4. `gesture_id` added to `song_event_timeline.json`

Every gesture-phase row (`approach` / `build` / `tension` / `impact` /
`release`) belonging to one composite gesture now carries a shared
`gesture_id` string, e.g. `"gesture-003"` (source: `gestures`). Section-pair
transition rows carry **no** `gesture_id` key at all.

Consumers can now reconstruct "a drop's five-phase envelope" by grouping rows on
`gesture_id` without re-deriving the gesture assembly. Rows sharing a
`gesture_id` are time-ordered and non-overlapping. No field is removed; a
consumer that ignores `gesture_id` is unaffected.

---

## 5. New top-level file: `genre.json`

`data/analysis/{song}/genre.json` is now published — a **fused view** of
`artifacts/genre.json` with the `generated_from` host-path block stripped and a
`field_sources` header added. The artifact is untouched (the analyzer and the
debugger keep reading it); the MCP server reads only the top-level file.

```json
{
  "schema_version": "3.0",
  "song_name": "...",
  "field_sources": { "genres": "genre", "confidence": "genre",
                     "top_predictions": "genre", "guidance": "genre" },
  "genres": ["electronic", "dance"],
  "confidence": 0.38,
  "top_predictions": [ { "label": "electronic", "confidence": 0.38 }, ... ],
  "guidance": [ "..." ]
}
```

`genres: ["unknown"]` with a low `confidence` is a valid honest outcome. The
value is written through a per-field fusion path (one producer, `genre`, today)
so a second producer can join without a rewrite.

