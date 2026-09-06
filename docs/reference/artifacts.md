# Reference — every file under `data/`

Lookup table. The *why* is in [`../analysis-definition.md`](../analysis-definition.md);
what reaches the authoring model is in [`../mcp-definition.md`](../mcp-definition.md).
Governance rules are in [`../../CLAUDE.md`](../../CLAUDE.md).

## Layout

```text
data/
  songs/{song}.mp3
  analysis/{song}/
    info.json  beats.json  hints.json  sections.json  song_event_timeline.json
    genre.json  drum_events.json
    artifacts/
      stems/            bass.wav drums.wav harmonic.wav vocals.wav metadata.json
      essentia/         beats.json fft_bands.json hpcp.json
                        rms_loudness.json loudness_envelope.json
      allin1/           raw.json
      section_segmentation/  sections.json
      symbolic_transcription/  drum_events.json  omnizart/drums.mid
      validation/       phase_1_report.{json,md}  human_hints_alignment.{json,md}
                        drops_score.json
      layer_a_harmonic.json  layer_c_energy.json  genre.json
    reference/
      human/            human_hints.json  song_facts.json
      moises/           chords.json  lyrics.json  segments.json
      proposals/        <experiment output — not a contract>
```

## Two tiers, and the boundary is the directory level

| Tier | Who may read it |
| --- | --- |
| `data/analysis/{song}/*.json` | the `mcp/` server, the analyzer, the debugger UI |
| `…/artifacts/**`, `…/reference/**` | **the analyzer and the debugger UI only** |

The restriction binds `mcp/` alone. **The debugger reads anything under `data/`
at any depth** — a file it cannot open is a bug it cannot diagnose.

The top-level files are the delivery surface; adding or removing one is a
contract change. Inner folders are the raw material phase 4 uses to build them
and are never exposed downstream, whatever their quality.

`data/fixtures/` does not exist and never has — do not create it (fixture
orchestration is out of scope).

## Attribution on the delivery surface

Top-level files are **fused** from several producers, not copied from one
artifact each — see [`../analysis-definition.md`](../analysis-definition.md)
"Phase 4 fuses; it does not copy". Every published value therefore says where it
came from, in two parts:

| Where | What |
| --- | --- |
| file header — `field_sources` | the default producer for each field, declared once |
| row — `source` | present **only** where that row took a different producer than the header declares |

`beats.json` and `sections.json` are **objects**, not bare arrays — an array
cannot carry a header. Their rows sit under `beats` / `sections` respectively.
`info.json`, `hints.json` and `song_event_timeline.json` were already objects.

So the common case costs one small header block, and a row that departs from the
default is visible precisely because it is the only kind of row that carries a
`source`.

The producer vocabulary is closed: `essentia`, `allin1`, `harmonic`, `omnizart`,
`demucs`, `gestures`, `genre`, `human`, `inference`. `unknown` is legal and
means no producer cleared its confidence floor — it is never a synonym for
"we didn't record it".

`source` (which producer) is distinct from `provenance` (how much human review a
claim has had: `machine-only`, `reviewed`, `human-confirmed`). A row can carry
both.

## Top-level deliverables

| File | Contents | Open it to |
| --- | --- | --- |
| `info.json` | song metadata; `artifacts` / `outputs` path manifest | discover a song's canonical files; read `bpm`, `duration` |
| `beats.json` | `{ field_sources, beats[] }`; each beat `time`, `type`, `bar`, `beat`, `chord`, `downbeat_confidence` | place cues on exact beat/downbeat times. `downbeat_confidence` (renamed from `confidence`) is allin1's downbeat-phase strength — `null` on `"beat"` rows and on unresolved downbeats, never the beat time's confidence |
| `sections.json` | `{ field_sources, sections[] }`; each section `section_id`, `start`, `end`, `label`, `description`, `function`, `function_confidence`, `function_status`, `same_label_as`, `key`, `chord_progression`, `confidence` | fast section summaries and show pacing. Section names are on the row (`function` + `function_confidence` + `function_status`) — read them here, never from `section_segmentation/sections.json`. `label` is `"003 Chorus (0.81)"`, or the raw token marked `[unverified]` when `function_status` is `"unknown"`. `same_label_as` is label repetition, not acoustic identity |
| `hints.json` | `field_sources`; `sections[].hints[]` of `{ id, source, category, text, anchor_refs }` | per-section guidance; match by `section_id`, never by repeated labels |
| `song_event_timeline.json` | `field_sources`; flat `events[]`: gesture phases + section transitions, `schema_version` `"3.0"` | event-aware cue planning. Gesture-phase rows sharing one composite gesture carry the same `gesture_id` (`"gesture-003"`); section-transition rows carry no `gesture_id`. No nested `phases[]`, no `composite`, no `member_event_ids` — every row is flat and carries its own `evidence_summary` |
| `genre.json` | `field_sources`; `genres`, `confidence`, `top_predictions[]`, `guidance[]` | advisory style context. A **fused view** of `artifacts/genre.json` with host paths stripped — the artifact stays for the analyzer and the debugger. `genres: ["unknown"]` is a valid outcome |
| `drum_events.json` | `field_sources`; `events[]` of `{ time, event_type, confidence }`; `summary` counts; `supported_event_types` | rhythmic pulse. Kick/snare/hat only. A fused view of `artifacts/symbolic_transcription/drum_events.json` — full event list, no decimation (~1,164 events/song); `summary` and `supported_event_types` are file-level and provenance-exempt |

### `field_sources` per file

Default producer per field, declared once in each file's header. A row overrides
it with `source` only where it departs from the default; no `beats.json` row
does (a repeated per-row map would be pure token cost).

| File | `field_sources` |
| --- | --- |
| `info.json` | `bpm`, `duration` → `essentia`. `song_path` / `artifacts` / `outputs` / `debug` are orchestration metadata, not fused values, and carry no entry (removed in a later v3.1 item) |
| `beats.json` | `time`, `beat`, `bar`, `type` → `essentia`; `chord` → `harmonic`; `downbeat_confidence` → `allin1` |
| `sections.json` | `section_id`, `start`, `end`, `function`, `function_confidence`, `function_status`, `same_label_as`, `confidence` → `allin1`; `label`, `description` → `human`; `key`, `chord_progression` → `harmonic` |
| `hints.json` | `summary`, `sections` → `inference` (each hint row also carries its own `source`: `human` \| `inference` \| `user`) |
| `song_event_timeline.json` | all event fields (`gesture_id` included) → `gestures`, except `section_id` / `section_name` → `allin1` |
| `genre.json` | `genres`, `confidence`, `top_predictions`, `guidance` → `genre` (`unknown` where the estimate is absent) |
| `drum_events.json` | `time`, `event_type`, `confidence` → `omnizart`. `summary` / `supported_event_types` are file-level aggregates, provenance-exempt like `schema_version` |

## Artifacts

| File | Contents | Open it to |
| --- | --- | --- |
| `stems/*.wav` + `metadata.json` | Demucs output; `generated_from.engine` and stem paths | confirm which isolated sources exist before trusting stem-specific analysis |
| `essentia/beats.json` | canonical timing grid: BPM, duration, `beats[]` with `time`, `bar`, `beat_in_bar`, `type`, `confidence` | the timing spine for everything else |
| `essentia/hpcp.json` | `hpcp_by_beat[].vector` — 12-bin chroma per beat | lower-level harmonic evidence when chord labels feel too coarse. Skip if `layer_a_harmonic.json` answers it |
| `essentia/fft_bands.json` | `bands[]`, `frames[]`, `metadata.interval_ms` — 7 bands / 50 ms | check whether bass-, mid- or top-driven motion explains a boundary |
| `essentia/rms_loudness.json` | `sources[]`, `frames[]`, 10 ms | which source is physically active at fine resolution. Values are per-song display values, not calibrated LUFS |
| `essentia/loudness_envelope.json` | same shape, 200 ms windows | macro-dynamics against section transitions |
| `allin1/raw.json` | allin1 segments + `downbeat`/`label` frame activations at 100 Hz | internal cache only. Written by `analyzer.allin1_cache` so `timing.py` and `segmentation.py` share one model run. Not a contract; nothing else reads it |
| `section_segmentation/sections.json` | `section_id`, `start`, `end`, `function`, `function_confidence`, `function_status`, `same_label_as`, `confidence` | the structural backbone. Treat `function` as unverified where `function_status` is `"unknown"`, and `same_label_as` as label repetition only |
| `symbolic_transcription/drum_events.json` | `events[]` of `time`, `event_type`, `confidence`; summary counts | rhythmic pulse. Kick/snare/hat only — no harmonic or vocal information |
| `symbolic_transcription/omnizart/drums.mid` | raw Omnizart MIDI cache | first stop when the normalized counts look wrong. GM pitches 35/38/42 = kick/snare/hat |
| `layer_a_harmonic.json` | `global_key`, `chords[]` | chord-change timing and tonal identity |
| `layer_c_energy.json` | `global_energy`, `section_energy[]`, `accent_candidates[]` | macro intensity and accent timing. `hit` and `rise` accents should not look the same |
| `genre.json` | `genres`, `confidence`, `top_predictions[]`, `guidance[]` | advisory style context. `unknown` is a valid outcome — never invent a genre from heuristics |
| `validation/phase_1_report.{json,md}` | per-domain scores and mismatch detail | judge where output is trustworthy. Mismatch rows are caution signals, never generation input |
| `validation/human_hints_alignment.{json,md}` | hint windows vs. generated sections/events | issue triage; written only when human hints exist |
| `validation/drops_score.json` | advisory `--compare drops` score | never gates the exit code |

## Reference — validation only

**Never a generation input** (`reference/` is validation-only). No pipeline stage takes over
a canonical artifact from any of these.

| File | What it is | Use it to |
| --- | --- | --- |
| `human/human_hints.json` | hand-authored ground truth: `id`, `title`, `start_time`, `end_time`, `summary`, `lighting_hint`, optional `captured_from` | the only real ground truth. `captured_from` is informative-only prose written by the debugger; no analyzer code reads it |
| `human/song_facts.json` | song-level human-confirmed `genre`, `form_family`, `has_drop`, each `{ value, provenance, confirmed_on }` | written **only** by the debugger on explicit save |
| `moises/chords.json` | Moises.ai **inference**, not human truth — no confidence field, so no row is curated | measure *agreement with a second model*, never correctness |
| `moises/segments.json` | Moises.ai inference — no confidence field | boundary-quality comparison. Labels advisory; the boundary timing is the point |
| `moises/lyrics.json` | word-level timing with `text`, `start`, `end`, `line_id`, `<SOL>`/`<EOL>` markers and per-word confidence | lyric-synced moments; vocal-presence priors. **Only `"0.99"`-confidence rows are operator-curated** |
| `proposals/*.json` | unpromoted experiment output | audition against the song in the debugger. Not a contract; see the source experiment's README |

## Where to start

| Task | Order |
| --- | --- |
| Show briefing | `sections.json` → `song_event_timeline.json` → `hints.json` |
| Cue generation | `sections.json` → `beats.json` → `layer_c_energy.json` |
| Harmonic / colour logic | `layer_a_harmonic.json` → `essentia/beats.json` |
| Trust and QA | `validation/phase_1_report.md` → `.json` → the matching `reference/` files |
| Debugger work | invert: `artifacts/` first, top-level files only as compact projections |
