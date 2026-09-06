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
