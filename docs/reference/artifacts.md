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
    genre.json  drum_events.json  loudness.json  arrangement_state.json
    artifacts/
      stems/            bass.wav drums.wav harmonic.wav vocals.wav metadata.json
      essentia/         beats.json fft_bands.json fft_bands.{bass,drums,harmonic,vocals}.json
                        hpcp.json rms_loudness.json loudness_envelope.json
      allin1/           raw.json
      section_segmentation/  sections.json
      symbolic_transcription/  drum_events.json  omnizart/drums.mid
      validation/       phase_1_report.{json,md}  human_hints_alignment.{json,md}
                        drops_score.json
      layer_a_harmonic.json  layer_c_energy.json  genre.json
      section_function_contest.json
    reference/
      human/            human_hints.json  song_facts.json  block_energy.json  lyric_validations.json
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
`demucs`, `gestures`, `arrangement_state`, `section_function`, `genre`, `human`,
`inference`.
`unknown` is legal and
means no producer cleared its confidence floor — it is never a synonym for
"we didn't record it".

`source` (which producer) is distinct from `provenance` (how much human review a
claim has had: `machine-only`, `reviewed`, `human-confirmed`). A row can carry
both.

## Top-level deliverables

| File | Contents | Open it to |
| --- | --- | --- |
| `info.json` | `{ schema_version, song_name, bpm, duration, field_sources }` — song metadata only | read `bpm`, `duration`, `song_name`. v3.1 item 8 removed `song_path` / `artifacts` / `outputs` / `debug` / `generated_from`: they embedded absolute host paths and a per-song file manifest — a client discovers a song's files from the fixed top-level layout, not a manifest |
| `beats.json` | `{ field_sources, beats[] }`; each beat `time`, `type`, `bar`, `beat`, `chord`, `downbeat_confidence` | place cues on exact beat/downbeat times. `downbeat_confidence` (renamed from `confidence`) is allin1's downbeat-phase strength — `null` on `"beat"` rows and on unresolved downbeats, never the beat time's confidence |
| `sections.json` | `{ field_sources, sections[] }`; each section `section_id`, `start`, `end`, `label`, `description`, `function`, `function_confidence`, `function_status`, `same_label_as`, `key`, `chord_progression`, `confidence` | fast section summaries and show pacing. Section names are on the row (`function` + `function_confidence` + `function_status`) — read them here, never from `section_segmentation/sections.json`. `label` is `"003 Chorus (0.81)"`, or the raw token marked `[unverified]` when `function_status` is `"unknown"`. `function_status` is `"known"` / `"unknown"` / `"contested"` — `"contested"` (v3.4, phase-3 `contest-section-function`) means allin1's label is kept but its measured energy contradicts the following section; such a row also carries `contested_by: "energy"`. `same_label_as` is label repetition, not acoustic identity |
| `hints.json` | `field_sources`; `sections[].hints[]` of `{ id, source, category, text, anchor_refs }` | per-section guidance; match by `section_id`, never by repeated labels |
| `song_event_timeline.json` | `field_sources`; flat `events[]`: gesture phases + section transitions, `schema_version` `"3.0"` | event-aware cue planning. Gesture-phase rows sharing one composite gesture carry the same `gesture_id` (`"gesture-003"`); section-transition rows carry no `gesture_id`. No nested `phases[]`, no `composite`, no `member_event_ids` — every row is flat and carries its own `evidence_summary` |
| `genre.json` | `field_sources`; `genres`, `confidence`, `top_predictions[]`, `guidance[]` | advisory style context. A **fused view** of `artifacts/genre.json` with host paths stripped — the artifact stays for the analyzer and the debugger. `genres: ["unknown"]` is a valid outcome |
| `drum_events.json` | `field_sources`; `events[]` of `{ time, event_type, confidence }`; `summary` counts; `supported_event_types` | rhythmic pulse. `event_type` ∈ `kick` / `snare` / `hat` / `crash` / `unresolved` — `crash` is a v3.4 brilliance-gated split of pitch-42 `hat` events; `confidence` is always `null`; `velocity` is not published (constant 100). A fused view of `artifacts/symbolic_transcription/drum_events.json` — full event list, no decimation (~1,164 events/song); `summary` and `supported_event_types` are file-level and provenance-exempt |
| `loudness.json` | `field_sources`; `metadata.interval_ms` `20`; `sources[]` of `{ id, label, kind }` (stems, not producers); `frames[]` of `{ time, values, normalized_values }` | fine-resolution per-source loudness. `artifacts/essentia/rms_loudness.json` decimated 10 ms → 20 ms by **averaging pairs** (transient peaks preserved; an unpaired trailing frame is dropped). 20 ms is the floor a caller may request, not what every read returns. The `path` field is dropped from `sources[]` |
| `arrangement_state.json` | `field_sources`; `stems[]` (stem vocabulary, file-level); `blocks[]` of `{ start_s, end_s, playing[], entered[], left[], margin_db, confidence }` | who is playing and where that changes (sub-section stem-state spans). Fused view of `artifacts/arrangement_state.json` (phase-3 `detect-arrangement-state`, reads only published `loudness.json`). `confidence` is `1 - exp(-margin_db/6)` — dB headroom at the stem flip, not a tuned score. Leading block carries `margin_db: null` / `confidence: null`. **Optional** — absent on pre-v3.2 songs. Intended extension point: a CLAP `feel` field fused into the same rows later |

### `field_sources` per file

Default producer per field, declared once in each file's header. A row overrides
it with `source` only where it departs from the default; no `beats.json` row
does (a repeated per-row map would be pure token cost).

| File | `field_sources` |
| --- | --- |
| `info.json` | `bpm`, `duration` → `essentia`. No other fused fields — `song_path` / `artifacts` / `outputs` / `debug` / `generated_from` were removed in v3.1 item 8 |
| `beats.json` | `time`, `beat`, `bar`, `type` → `essentia`; `chord` → `harmonic`; `downbeat_confidence` → `allin1` |
| `sections.json` | `section_id`, `start`, `end`, `function`, `function_confidence`, `function_status`, `same_label_as`, `confidence` → `allin1`; `label`, `description` → `human`; `key`, `chord_progression` → `harmonic`. On a song with a contested row: `function_status` → `section_function` and `contested_by` → `section_function` (present only on contested rows); byte-identical header otherwise |
| `hints.json` | `summary`, `sections` → `inference` (each hint row also carries its own `source`: `human` \| `inference` \| `user`) |
| `song_event_timeline.json` | all event fields (`gesture_id` included) → `gestures`, except `section_id` / `section_name` → `allin1` |
| `genre.json` | `genres`, `confidence`, `top_predictions`, `guidance` → `genre` (`unknown` where the estimate is absent) |
| `drum_events.json` | `time`, `event_type` (incl. the v3.4 `crash` split), `confidence` → `omnizart`. `summary` / `supported_event_types` are file-level aggregates, provenance-exempt like `schema_version` |
| `loudness.json` | `time`, `values`, `normalized_values` → `essentia`. `metadata` / `sources` are file-level, provenance-exempt |
| `arrangement_state.json` | `start_s`, `end_s`, `playing`, `entered`, `left`, `margin_db`, `confidence` → `arrangement_state`. `stems` is a file-level aggregate, provenance-exempt like `schema_version` |

## Artifacts

| File | Contents | Open it to |
| --- | --- | --- |
| `stems/*.wav` + `metadata.json` | Demucs output; `generated_from.engine` and stem paths | confirm which isolated sources exist before trusting stem-specific analysis |
| `essentia/beats.json` | canonical timing grid: BPM, duration, `beats[]` with `time`, `bar`, `beat_in_bar`, `type`, `confidence` | the timing spine for everything else |
| `essentia/hpcp.json` | `hpcp_by_beat[].vector` — 12-bin chroma per beat | lower-level harmonic evidence when chord labels feel too coarse. Skip if `layer_a_harmonic.json` answers it |
| `essentia/fft_bands.json` | `bands[]`, `frames[]`, `metadata.interval_ms` — 7 bands / 50 ms, mix only | check whether bass-, mid- or top-driven motion explains a boundary |
| `essentia/fft_bands.bass.json` | same schema + `metadata.stem: "bass"` — FFT of the Demucs bass stem, normalised against that stem's own 5th–95th percentile | check whether bass-driven motion explains a boundary, attributed to the stem. Inherits Demucs separation error before the transform — the mix file cannot attribute but inherits none |
| `essentia/fft_bands.drums.json` | same schema + `metadata.stem: "drums"` | drums-stem sub-band (kick weight) and brilliance (hat vs. crash) — the only route to "how hard was this hit" (drum events carry constant velocity). Separation-error caveat as above |
| `essentia/fft_bands.harmonic.json` | same schema + `metadata.stem: "harmonic"` (Demucs `other`) | mid/top-driven motion attributed to the harmonic bed. Separation-error caveat as above: the harmonic stem reads ~0.009 RMS through the `Queen of Kings` drop where the chord decoder still finds Am at 0.716 |
| `essentia/fft_bands.vocals.json` | same schema + `metadata.stem: "vocals"` | presence/upper-mid motion attributed to the vocal. Separation-error caveat as above |
| `essentia/rms_loudness.json` | `sources[]`, `frames[]`, 10 ms | which source is physically active at fine resolution. Values are per-song display values, not calibrated LUFS |
| `essentia/loudness_envelope.json` | same shape, 200 ms windows | macro-dynamics against section transitions |
| `allin1/raw.json` | allin1 segments + `downbeat`/`label` frame activations at 100 Hz | internal cache only. Written by `analyzer.allin1_cache` so `timing.py` and `segmentation.py` share one model run. Not a contract; nothing else reads it |
| `section_segmentation/sections.json` | `section_id`, `start`, `end`, `function`, `function_confidence`, `function_status`, `same_label_as`, `confidence` | the structural backbone. Treat `function` as unverified where `function_status` is `"unknown"`, and `same_label_as` as label repetition only |
| `symbolic_transcription/drum_events.json` | `events[]` of `time`, `event_type` (`kick`/`snare`/`hat`/`crash`/`unresolved`), `confidence` (always `null`); summary counts | rhythmic pulse. No harmonic or vocal information. `crash` is a v3.4 brilliance-gated split of pitch-42 events (see `drums.py`); `velocity` is a constant 100, kept in the artifact but not published |
| `symbolic_transcription/omnizart/drums.mid` | raw Omnizart MIDI cache | first stop when the normalized counts look wrong. GM pitches 35/38/42 = kick/snare/hat — a pitch-42 hit is `hat` or `crash` depending on the drums-stem brilliance band |
| `layer_a_harmonic.json` | `global_key`, `chords[]` | chord-change timing and tonal identity |
| `layer_c_energy.json` | `global_energy`, `section_energy[]`, `accent_candidates[]` | macro intensity and accent timing. `hit` and `rise` accents should not look the same |
| `layer_b_symbolic.json` | note events (pitch, velocity, duration, source stem) | **stale — no producer since v3.0** (`58b9764`, 2026-09-05). Present only on ~17 pre-v3.0 analyses, absent on all four gold songs, read by nothing. Ignore it; do not rely on it |
| `genre.json` | `genres`, `confidence`, `top_predictions[]`, `guidance[]` | advisory style context. `unknown` is a valid outcome — never invent a genre from heuristics |
| `section_function_contest.json` | `schema_version`, `generated_from` (thresholds + the 3 published inputs), `sections[]` of `{ section_id, function, contested, contested_by, margin }` (`margin` = dB gap of the next section's drums, `null` on the last section) | phase-3 `contest-section-function` scratch output. The `contested` rows are fused into the top-level `sections.json` as `function_status: "contested"` + `contested_by: "energy"` — read them there, not here |
| `validation/phase_1_report.{json,md}` | per-domain scores and mismatch detail | judge where output is trustworthy. Mismatch rows are caution signals, never generation input |
| `validation/human_hints_alignment.{json,md}` | hint windows vs. generated sections/events | issue triage; written only when human hints exist |
| `validation/drops_score.json` | advisory `--compare drops` score | never gates the exit code |

## Reference — validation only

**Never a generation input** (`reference/` is validation-only). No pipeline stage takes over
a canonical artifact from any of these.

**Every file here is optional.** Moises files exist only for the gold songs, and
human hints only after someone has reviewed a song in the debugger. A song with
neither must analyze identically: validation reports `skipped` for the domains
that lost their reference, and the first run infers every value it can so there
is something to review. A score computed from these files covers only the songs
that have them — say which.

| File | What it is | Use it to |
| --- | --- | --- |
| `human/human_hints.json` | hand-authored ground truth: `id`, `title`, `start_time`, `end_time`, `summary`, `lighting_hint`, optional `captured_from`, optional `type` | the only real ground truth. `captured_from` is informative-only prose written by the debugger; `type` is `"review"` for a hint seeded from an experiment/event block to review or annotate a finding, absent (equivalent to `"hint"`) for one authored from scratch — editable in the hint editor, not a hard link to its origin. No analyzer code reads either field |
| `human/song_facts.json` | song-level human-confirmed `genre`, `form_family`, `has_drop`, each `{ value, provenance, confirmed_on }` | written **only** by the debugger on explicit save |
| `human/block_energy.json` | operator's 1–5 `energy` / `tension` rating per `human_hints.json` block: `{ schema_version, song_name, ratings: [{ hint_id, energy?, tension? }] }`, joined by `hint_id`; unrated ⇒ absent from `ratings` (v3.4 item 4) | written **only** by the debugger's Human Hints events panel on explicit Save (`PUT /api/block-energy/<song>`, dev-only). One producer (the operator) — no `field_sources`/`source`. Nothing in `src/` or `mcp/` reads it |
| `human/lyric_validations.json` | operator's hand-verification of Moises lyric-token timing: `{ schema_version, song_name, validated_ids: [int] }` — the ids of `moises/lyrics.json` word tokens checked against the waveform (v3.4 item 5) | written **per-click** (not on Save — D5.1) by the debugger's Moises Lyrics events panel ✔ button (`PUT /api/lyric-validations/<song>`, dev-only). An **overlay**: the lane shows a listed token at confidence `1` with a distinct tint; `moises/lyrics.json` is never edited. One producer (the operator) — no `field_sources`/`source`. Nothing in `src/` or `mcp/` reads it |
| `moises/chords.json` | Moises.ai **inference**, not human truth — no confidence field, so no row is curated | measure *agreement with a second model*, never correctness |
| `moises/segments.json` | Moises.ai inference — no confidence field | boundary-quality comparison. Labels advisory; the boundary timing is the point |
| `moises/lyrics.json` | word-level timing with `text`, `start`, `end`, `line_id`, `<SOL>`/`<EOL>` markers and per-word confidence | lyric-synced moments; vocal-presence priors. **Only `"0.99"`-confidence rows are operator-curated.** Read-only, inference-only — operator timing checks are recorded in `human/lyric_validations.json` (v3.4 item 5 / D6), never by editing this file |
| `proposals/*.json` | unpromoted experiment output | audition against the song in the debugger. Not a contract; see the source experiment's README |

## Where to start

| Task | Order |
| --- | --- |
| Show briefing | `sections.json` → `song_event_timeline.json` → `hints.json` |
| Cue generation | `sections.json` → `beats.json` → `layer_c_energy.json` |
| Harmonic / colour logic | `layer_a_harmonic.json` → `essentia/beats.json` |
| Trust and QA | `validation/phase_1_report.md` → `.json` → the matching `reference/` files |
| Debugger work | invert: `artifacts/` first, top-level files only as compact projections |
