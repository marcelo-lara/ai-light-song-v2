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


---

## 6. New top-level file: `drum_events.json`

`data/analysis/{song}/drum_events.json` — a fused view of
`artifacts/symbolic_transcription/drum_events.json`. The full event list, **no
decimation** (~1,164 events / ~600 KB per song). Host paths in `generated_from`
are gone; per-event rows are trimmed to the three fields a cue author needs.

```json
{
  "schema_version": "3.0",
  "song_name": "...",
  "field_sources": { "time": "omnizart", "event_type": "omnizart", "confidence": "omnizart" },
  "summary": { "event_count": 1164, "kick_count": 326, "snare_count": 182,
               "hat_count": 656, "unresolved_count": 0 },
  "supported_event_types": ["kick", "snare", "hat", "unresolved"],
  "events": [ { "time": 0.19, "event_type": "hat", "confidence": null }, ... ]
}
```

`summary` and `supported_event_types` are file-level aggregates and carry no
`field_sources` entry (provenance-exempt, like `schema_version`). `confidence` is
`null` on every row today — Omnizart does not emit a per-event confidence.

---

## 7. New top-level file: `loudness.json`

`data/analysis/{song}/loudness.json` — `artifacts/essentia/rms_loudness.json`
**decimated 10 ms → 20 ms by averaging consecutive pairs** (not by dropping every
other frame: a dropped-frame series loses the transient peaks that a drop impact
*is*). An unpaired trailing frame (odd source count) is dropped so every
published interval is exactly 20 ms — at most 10 ms is lost at the end of the
song. The 10 ms artifact is unchanged and stays the debugger's source.

```json
{
  "schema_version": "3.0",
  "song_name": "...",
  "field_sources": { "time": "essentia", "values": "essentia", "normalized_values": "essentia" },
  "metadata": { "sample_rate": 44100, "duration": 194.0,
                "normalization_scope": "per-song-per-source-peak-rms",
                "source_order": ["mix","bass","drums","harmonic","vocals"],
                "interval_ms": 20, "total_frames": 9700 },
  "sources": [ { "id": "mix", "label": "Mix", "kind": "mix" }, ... ],
  "frames": [ { "time": 0.01, "values": [ ...5 ], "normalized_values": [ ...5 ] }, ... ]
}
```

- `metadata.interval_ms` is `20` — the **floor** a caller may request, not what
  every read returns. `get_detail`'s `interval_ms` parameter decimates this
  series further per request; a request finer than 20 ms is an error.
- `sources[]` here means **stems**, not producers. Its `path` field (a host-path
  leak) is dropped. Producer attribution stays in `field_sources`; `sources[]` is
  not overloaded with it.
- `frames[]` values are per-song display values in `source_order`, not
  calibrated LUFS. `history` (rolling windows), `frame_index`, `start_s` and
  `end_s` are not published — a caller computes windows from the series it asks
  for.

---

## 8. 🚨 `info.json` — fields REMOVED (the only removal in the release)

Every other v3.1 item **adds** fields. This one **removes** five that a consumer
may read today. A consumer that reads any of them must stop.

`info.json` is now **only** song metadata:

```json
{
  "schema_version": "3.0",
  "song_name": "Armin - Revolution",
  "bpm": 129.41,
  "duration": 194.01,
  "field_sources": { "bpm": "essentia", "duration": "essentia" }
}
```

| Field | Status | Why |
| --- | --- | --- |
| `schema_version`, `song_name`, `bpm`, `duration` | **kept** | `bpm` / `duration` are a shipped, tested contract (`list_songs()` reads them) |
| `field_sources` | kept (added in item 2) | attribution header |
| `song_path` | **removed** | absolute host path (`/data/songs/…`) |
| `artifacts` | **removed** | a per-song `{name: absolute host path}` manifest of `artifacts/` files — all `/data/analysis/…` host paths, and pointing into `artifacts/` which the MCP server may not read anyway |
| `outputs` | **removed** | absolute host paths to the other top-level files |
| `generated_from` | **removed** | absolute host paths to input artifacts |
| `debug` | **removed** | internal counters (`fft_band_count`, …), never a consumer contract |

**Consumer action:** discover a song's files from the fixed top-level layout
(`data/analysis/{song}/{info,beats,sections,hints,song_event_timeline,genre,drum_events,loudness}.json`)
— there is no per-song manifest to read, and there is no host path anywhere in
`info.json`. `list_songs()` continues to return `song_name` + `bpm` + `duration`
unchanged.
