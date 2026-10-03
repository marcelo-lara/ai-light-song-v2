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
    drum_events.json  loudness.json  arrangement_state.json  vocal_cadence.json
    artifacts/
      stems/            bass.wav drums.wav harmonic.wav vocals.wav metadata.json
      essentia/         beats.json fft_bands.json fft_bands.{bass,drums,harmonic,vocals}.json
                        rms_loudness.json loudness_envelope.json
      allin1/           raw.json
      section_segmentation/  sections.json  sections_display.json
      symbolic_transcription/  drum_events.json  omnizart/drums.mid
      gestures/         song_event_timeline.json
      harmonic_spectrum/  half_beats.json            # v3.12 item 32 — `extract-harmonic-spectrum` (1.5)
      kick_attacks/     kick_attacks.json            # v3.12 item 32 — `detect-kick-attacks` (2.6)
      light_changes/    bar_features.json  light_changes.json   # v3.12 item 32 — `light-changes` (3.3)
      validation/       phase_1_report.{json,md}  human_hints_alignment.{json,md}
                        drops_score.json
      _run_request.json   _run_progress.json   # v3.8 item 1 — host watcher queue/status, not a delivery artifact
    reference/
      human/            human_hints.json  song_facts.json  lyric_validations.json
      moises/           chords.json  lyrics.json  segments.json
      pre-analysis/     structure.json   # v3.10 item 7 — web-researched prior, written only by the mcp write_structure_hint
                        verdict.json     # v3.11 item 21 — version_check block (`version-check` stage) + verdicts block (`hint-verdict` stage)
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

The producer vocabulary is closed: `essentia`, `allin1`, `omnizart`,
`demucs`, `gestures`, `arrangement_state`, `whisperx_vad`, `vocal_sibilance`,
`human`, `inference`.
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
| `beats.json` | `{ field_sources, beats[], off_grid_spans[] }`; each beat `time`, `beat`, `bar`, `type`, `downbeat_confidence`; each span `{ start, end, max_deviation_ms }` | place cues on exact beat/downbeat times. `downbeat_confidence` (renamed from `confidence`) is allin1's downbeat-phase strength — `null` on `"beat"` rows and on unresolved downbeats, never the beat time's confidence. **v3.6 item 8 dropped `chord`** (unread; chord labels are "informative, not settled"). **v3.9 item 3 adds `off_grid_spans`** (file-level, always present, `[]` when the grid is clean throughout) — a stretch where essentia's tracker left the song's fitted constant-tempo grid; beat times inside a span are unchanged (D3.1), just not evenly spaced there. `get_detail`'s derived `position` reports `resolved: false` for a time inside a span |
| `sections.json` | `{ field_sources, sections[] }`; each section `section_id`, `start`, `end`, `function`, `function_confidence`, `function_status`, `same_label_as`, `confidence`; no `key`, `energy`, `tension`, `rhythm` or `impact_alignment` (removed in v3.10 item 8); optional file-level `sections_tier_note` | fast section summaries and show pacing. Section names are on the row (`function` + `function_confidence` + `function_status`) — read them here, never from `section_segmentation/sections.json`. `function_status` is `"known"` / `"unknown"`. `same_label_as` is label repetition, not acoustic identity. **v3.6 item 8 dropped `label` / `description` / `chord_progression`** (display string with confidence folded in, restated function+ordinal, and unread — respectively) → `artifacts/section_segmentation/sections_display.json` |
| `hints.json` | `{ schema_version, song_name, field_sources, hints[] }`; each row `{ section_id, title, text, start_time, end_time, lighting_hint }` | per-section guidance; match by `section_id`, never by repeated labels. **v3.6 item 8 restructured the whole file**: no `sections[]` wrapper (duplicated `sections.json`'s join), no `summary` block, no per-row `id` / `category` / `anchor_refs` (dead), no inference rows — the inference-hint generator was deleted, not filtered. Every row is `source: "human"` by construction (declared once in `field_sources`) |
| `song_event_timeline.json` | `{ schema_version, song_name, field_sources, events[] }`; each row `{ type, start_time, end_time, confidence, intensity, section_id }` (+ `gesture_id` on a gesture-phase row, + `peak_time` on an `impact` row) | event-aware cue planning. Gesture-phase rows sharing one composite gesture carry the same `gesture_id` (`"gesture-003"`); section-transition rows carry no `gesture_id`. **v3.6 item 8 dropped `section_name`** (duplicated the `section_id` join), **`summary` / `evidence_summary`** (unread prose) and file-level `generated_from` (provenance now artifacts-only) — the full row shape (every field this file used to carry) is preserved in `artifacts/gestures/song_event_timeline.json`. **v3.9 item 4**: an `impact` row's `start_time` is the onset (walked back from the transient peak, or a stem-anchored boundary onset with no transient at all), never the peak; `peak_time` keeps the peak instant (equal to `start_time` for a stem-entry impact, which has no separate peak) |
| `drum_events.json` | `{ schema_version, song_name, field_sources, summary, supported_event_types, confidence: null, confidence_reason, events[] }`; each event `{ time, event_type }` | rhythmic pulse. `event_type` ∈ `kick` / `snare` / `hat` / `crash` / `unresolved` — `crash` is a v3.4 brilliance-gated split of pitch-42 `hat` events; `velocity` is not published (constant 100). A fused view of `artifacts/symbolic_transcription/drum_events.json` — full event list, no decimation (~1,164 events/song); `summary` and `supported_event_types` are file-level and provenance-exempt. **v3.6 item 8 collapsed per-event `confidence`** (every one of the 32,213 corpus events was already `null` — Omnizart emits no per-hit confidence signal) **to one file-level `confidence: null` + `confidence_reason`** stating why, instead of repeating the `null` on every row |
| `loudness.json` | `{ schema_version, song_name, field_sources, interval_ms: 20, source_order, frames[] }`; each frame `{ time, values, normalized_values }` | fine-resolution per-source loudness. `artifacts/essentia/rms_loudness.json` decimated 10 ms → 20 ms by **averaging pairs** (transient peaks preserved; an unpaired trailing frame is dropped). 20 ms is the floor a caller may request, not what every read returns. **v3.6 item 8 moved `interval_ms` / `source_order` out of a `metadata` wrapper to flat top-level fields, and dropped `sources[]`** (stem-identity list, unread) **and `metadata.sample_rate` / `duration` / `total_frames` / `normalization_scope`** (unread) — all remain on `artifacts/essentia/rms_loudness.json`, which the debugger UI reads directly for stem identity and full metadata; the two internal phase-3 stages that read `source_order` (`section_function.py`, `arrangement_state.py`) were updated to the new flat top-level path |
| `arrangement_state.json` | `field_sources`; `stems[]` (stem vocabulary, file-level); `blocks[]` of `{ start_s, end_s, playing[], entered[], left[], margin_db, confidence }`; `vocals_phrase` (array of `{ start_s, end_s, confidence, sibilance }`); `vocals_sibilance_song_mean` | who is playing and where that changes (sub-section stem-state spans). Fused view of `artifacts/arrangement_state.json` (phase-3 `detect-arrangement-state`, reads only published `loudness.json`). `confidence` is `1 - exp(-margin_db/6)` — dB headroom at the stem flip, not a tuned score. Leading block carries `margin_db: null` / `confidence: null`. **Required** on every song (v3.6 item 9 — no degraded mode; `mcp/` errors naming this file if absent). `vocals_phrase` (v3.5 item 7; compute moved in-pipeline into the `whisperx` Compose service in v3.6 item 2) is a second, independent read on the vocals stem — whisperX VAD's phrase spans, read from `artifacts/whisperx-vad/whisperx_vad.json`, which `publish-arrangement-state` fails explicitly against if absent (never `null`, never a silent skip — run `docker compose run --rm whisperx --song <path>` first). Every span's `confidence` is hardcoded `1.0` by operator directive (a detected phrase is asserted certain, never graded). Each span also carries `sibilance` (v3.5 item 4, promoted 2026-09-13) — the mean of the promoted sibilance cue over that span, the stem-bleed discriminator, read against `vocals_sibilance_song_mean` rather than in absolute terms (the cue has a per-song noise floor). A span far below the song mean is the detector firing on instrument bleed. `sibilance` is `null` when the span covers no frame — never 0.0 standing in for "no evidence". No gate is applied at publish time: the value is reported, the decision is the consumer's. Intended extension point: a CLAP `feel` field fused into the `blocks` rows later |
| `vocal_cadence.json` (v3.9 item 1) | `{ schema_version, song_name, field_sources, source, reason, lines[], sections[], calls[] }`. `lines[]`: `{ line_id, start_s, end_s, start_position, end_position, duration_beats, token_count, resolve_time_s, resolve_position, pickup }`. `sections[]`: `{ section_id, start_s, end_s, lead_in_bars, lead_in_line_id, lead_in_resolve_time_s, lead_in_resolve_position, lead_in_reason, rests[], held_notes[], tokens_per_bar[], cadence_repeats[] }`. `calls[]`: `{ time_s, position }` | where a vocal line sits on the bar, and which earlier section a section's vocal cadence repeats (and at what bar offset) — timing only, **no lyric text anywhere in this file**; the only text ever read from `lyrics.json` is whether a token is a `<SOL>`/`<EOL>` marker or fully parenthesised (a call, e.g. `(hey)`). `source` is `"human"` (`reference/human/lyrics.json`) or `"moises"` (`reference/moises/lyrics.json`); `null` with `reason` set when the song has neither tier (D1.1) — `lines`/`sections`/`calls` are then all `[]`, never inferred. **Required** on every song, same no-degraded-mode rule as `arrangement_state.json`. `lead_in_bars` is the downbeat a section's first line *resolves on* (after its own pickup), in whole bars relative to the section's boundary bar — 0 = lands on the hit, -1 = a bar early; `lead_in_reason` explains a `null`. `cadence_repeats[]` rows are `{ section_id, bar_offset, match_fraction, onsets_matched, onsets_total, median_error_ms, best }` for every earlier section scoring >= 0.5 match fraction, the highest flagged `best`. Promoted from `experiments/vocal_cadence/` (12/12 on Queen of Kings — `docs/archive/experiments.promoted.vocal-cadence.md`); reads the published `beats.json`/`sections.json`/`info.json`, never `reference/human/segments.json` |

### `field_sources` per file

Default producer per field, declared once in each file's header. A row overrides
it with `source` only where it departs from the default; no `beats.json` row
does (a repeated per-row map would be pure token cost).

| File | `field_sources` |
| --- | --- |
| `info.json` | `bpm`, `duration` → `essentia`. No other fused fields — `song_path` / `artifacts` / `outputs` / `debug` / `generated_from` were removed in v3.1 item 8 |
| `beats.json` | `time`, `beat`, `bar`, `type` → `essentia`; `downbeat_confidence` → `allin1` (`chord` dropped in v3.6 item 8); `off_grid_spans` → `beat_grid_fit` (v3.9 item 3 — a fit over the beats themselves, file-level, not a raw producer) |
| `sections.json` | `section_id`, `start`, `end`, `function`, `same_label_as`, `confidence` → `human` if `reference/human/segments.json` has at least one row for the song, else `moises` if `reference/moises/segments.json` has one, else `allin1` — full precedence and rationale in [`analysis.segments.md`](analysis.segments.md). `function_confidence`, `function_status` → always `allin1`. (`label` / `description` / `chord_progression` dropped in v3.6 item 8; `key`, `energy`, `tension`, `rhythm`, `impact_alignment` and `contested_by` removed in v3.10 item 8) |
| `hints.json` | `title`, `text`, `start_time`, `end_time`, `lighting_hint` → `human` (declared once — every row is human by construction since v3.6 item 8; no per-row `source` override exists any more); `section_id` → `sections` (v3.7 item 6 — attributed by timestamp against the published `sections.json`, never `artifacts/section_segmentation/sections.json`) |
| `song_event_timeline.json` | `type`, `start_time`, `end_time`, `confidence`, `intensity`, `gesture_id`, `peak_time` (v3.9 item 4) → `gestures`; `section_id` → `sections` (v3.7 item 6 — attributed by timestamp against the published `sections.json`, never `artifacts/section_segmentation/sections.json`; `build-gestures` now runs after `build-ui-data` for this reason) |
| `drum_events.json` | `time`, `event_type` (incl. the v3.4 `crash` split) → `omnizart`. `summary` / `supported_event_types` are file-level aggregates, provenance-exempt like `schema_version`; file-level `confidence` / `confidence_reason` are likewise provenance-exempt (v3.6 item 8 collapsed per-event `confidence`, which was always `omnizart` / always `null`, to this one file-level pair) |
| `loudness.json` | `time`, `values`, `normalized_values` → `essentia`. `interval_ms` / `source_order` are file-level, provenance-exempt (v3.6 item 8 flattened them out of a `metadata` wrapper; `sources[]` and the rest of `metadata` were dropped, not just flattened) |
| `arrangement_state.json` | `start_s`, `end_s`, `playing`, `entered`, `left`, `margin_db`, `confidence` → `arrangement_state`; `vocals_phrase` → `whisperx_vad` (or `unknown` when no proposal cache exists for the song), except `vocals_phrase.sibilance` → `vocal_sibilance` — the one genuinely two-producer row on the delivery surface, so the header names the nested field explicitly. `vocals_sibilance_song_mean` → `vocal_sibilance`. `stems` is a file-level aggregate, provenance-exempt like `schema_version` |
| `vocal_cadence.json` | `lines`, `sections`, `calls` → `human` if `reference/human/lyrics.json` exists for the song, else `moises` if `reference/moises/lyrics.json` exists, else `unknown` (D1.1 no-lyrics case). `source`/`reason` are file-level, provenance-exempt like `schema_version` — they already state the tier |

## Artifacts

| File | Contents | Open it to |
| --- | --- | --- |
| `stems/*.wav` + `metadata.json` | Demucs output; `generated_from.engine` and stem paths | confirm which isolated sources exist before trusting stem-specific analysis |
| `essentia/beats.json` | canonical timing grid: BPM, duration, `beats[]` with `time`, `bar`, `beat_in_bar`, `type`, `confidence` | the timing spine for everything else |
| `essentia/fft_bands.json` | `bands[]`, `frames[]`, `metadata.interval_ms` — 7 bands / 50 ms, mix only | check whether bass-, mid- or top-driven motion explains a boundary |
| `essentia/fft_bands.bass.json` | same schema + `metadata.stem: "bass"` — FFT of the Demucs bass stem, normalised against that stem's own 5th–95th percentile | check whether bass-driven motion explains a boundary, attributed to the stem. Inherits Demucs separation error before the transform — the mix file cannot attribute but inherits none |
| `essentia/fft_bands.drums.json` | same schema + `metadata.stem: "drums"` | drums-stem sub-band (kick weight) and brilliance (hat vs. crash) — the only route to "how hard was this hit" (drum events carry constant velocity). Separation-error caveat as above |
| `essentia/fft_bands.harmonic.json` | same schema + `metadata.stem: "harmonic"` (Demucs `other`) | mid/top-driven motion attributed to the harmonic bed. Separation-error caveat as above: the harmonic stem reads ~0.009 RMS through the `Queen of Kings` drop where the chord decoder still finds Am at 0.716 |
| `essentia/fft_bands.vocals.json` | same schema + `metadata.stem: "vocals"` | presence/upper-mid motion attributed to the vocal. Separation-error caveat as above |
| `essentia/rms_loudness.json` | `sources[]`, `frames[]`, 10 ms, full `metadata` (`sample_rate`, `duration`, `total_frames`, `normalization_scope`, `interval_ms`, `source_order`) | which source is physically active at fine resolution. Values are per-song display values, not calibrated LUFS. Since v3.6 item 8 this is where the debugger UI reads `sources[]` and full `metadata` — the top-level `loudness.json` carries only `interval_ms` / `source_order` |
| `essentia/loudness_envelope.json` | same shape, 200 ms windows | macro-dynamics against section transitions |
| `allin1/raw.json` | allin1 segments + `downbeat`/`label` frame activations at 100 Hz | internal cache only. Written by `analyzer.allin1_cache` so `timing.py` and `segmentation.py` share one model run. Not a contract; nothing else reads it |
| `section_segmentation/sections.json` | `section_id`, `start`, `end`, `function`, `function_confidence`, `function_status`, `same_label_as`, `confidence` | the structural backbone. Treat `function` as unverified where `function_status` is `"unknown"`, and `same_label_as` as label repetition only |
| `section_segmentation/sections_display.json` | **New in v3.6 item 8.** `{ schema_version, song_name, generated_from, sections[] }`; each row `{ section_id, label, description }`, joined to `sections.json` by `section_id` | the display text dropped from top-level `sections.json` (`label` — the confidence-folded display string; `description` — a restated function+ordinal sentence). Written by the publish stage (`ui_data.py`'s `build_ui_data`). **Not MCP-exposed** — read by the debugger UI only |
| `harmonic_spectrum/half_beats.json` | `{ schema_version, song_name, generated_from, half_beats[] }`; one row per half-beat window of the published `beats.json` (`beat_index`, `half`, `start_s`, `end_s`) with `peak_hz`, `sharpness`, `hl_db` (10 log10 of energy > 2 kHz over < 500 Hz), `roll_hz` (99 % rolloff), `level_db` of the harmonic stem; `null` where silent or empty. Phase 1: a measurement, no confidence (v3.12 item 32; port of `experiments/filter_sweep_v2`) | the only audio input of the sweep columns; `light-changes` turns it into `sweep_slope` / `sweep_state`. `peak_hz` is reported but drives nothing (it jumps between chord tones) |
| `kick_attacks/kick_attacks.json` | `{ schema_version, song_name, generated_from, beat_len, events[] }`; each event `{ time, confidence, echo_of, on_grid, grid, rise_db, click_db, pitch_drop }`. Phase 2: kick attacks on the **mix** (40-120 Hz rise + 2-5 kHz click); `echo_of` non-null = a delay echo, not a kick; off-grid attacks keep the event at confidence x 0.4 (v3.12 item 32; port of `experiments/kick_attacks`) | the only audio input of `kick_attacks` / `kick_present`. Recall is near zero where a hat bed hides the click (Armin, Sash, Charli-VonDutch); Medicine bar 18 is missed |
| `light_changes/bar_features.json` | `{ schema_version, song_name, generated_from, bars[], half_beats[] }`; a bar row carries loudness (`loud_rms`, `loud_norm` per source), 7 bands per source, `brightness`, `transient_mean/std`, omnizart `kick/snare/hat`, `kick_attacks`, `kick_present`, `vocals_cover`, `entered/left/playing`, `sweep_slope` `{hl, roll}`, `sweep_state`, `irregular`, `beats_in_bar`, `beat_index`, `off_grid`; `half_beats[]` the signal columns only. A bar that is not 4 beats is flagged, never repaired (v3.12 item 32; phase 3) | one table instead of nine artifacts; input of the detector and of the item-33 `bar_features.json` projection |
| `light_changes/light_changes.json` | `{ schema_version, song_name, generated_from, points[] }`; each point `{ time, bar, beat, bar_edge_offset_beats (-1/0/+1), bar_edge_time, role, source ("step"/"sweep"), score, features[], z{}, sweep ({direction, rise_db} or null), sweep_state, irregular_bar, confidence }`. `time` is on a `beats.json` beat. `role` in `groove_in`/`build`/`break`/`drop`/`gap`/`fill`/`unknown` (unclaimed change = `unknown`). `confidence` is `null`: the score is uncalibrated; a sweep point has no `score` (v3.12 item 32; phase 3) | where the light should change inside a section; item 33 publishes it as `light_change` rows |
| `symbolic_transcription/drum_events.json` | `events[]` of `time`, `event_type` (`kick`/`snare`/`hat`/`crash`/`unresolved`), `confidence` (always `null`); summary counts | rhythmic pulse. No harmonic or vocal information. `crash` is a v3.4 brilliance-gated split of pitch-42 events (see `drums.py`); `velocity` is a constant 100, kept in the artifact but not published. Since v3.6 item 8 this per-event `confidence` (always `null`) is unchanged here but collapsed on the top-level `drum_events.json` to one file-level `confidence`/`confidence_reason` pair — the debugger UI still reads the per-event field from here |
| `symbolic_transcription/omnizart/drums.mid` | raw Omnizart MIDI cache | first stop when the normalized counts look wrong. GM pitches 35/38/42 = kick/snare/hat — a pitch-42 hit is `hat` or `crash` depending on the drums-stem brilliance band |
| `gestures/song_event_timeline.json` | **New in v3.6 item 8.** `{ schema_version, song_name, generated_from, events[] }`; each row the full pre-trim shape: `type`, `start_time`, `end_time`, `confidence`, `intensity`, `section_id`, `section_name`, `gesture_id` (phase rows), `provenance`, `summary`, `evidence_summary` | the full event shape the top-level `song_event_timeline.json` used to carry, before that file was trimmed to only the fields the MCP server reads. Written by the publish stage (`gestures.py`'s `build_gestures`), first, before the trimmed top-level file. **Not MCP-exposed** — read by the debugger UI only, for `section_name` / `summary` / `evidence_summary` / `provenance` |
| `layer_b_symbolic.json` | note events (pitch, velocity, duration, source stem) | **stale — no producer since v3.0** (`58b9764`, 2026-09-05). Present only on ~17 pre-v3.0 analyses, absent on all four gold songs, read by nothing. Ignore it; do not rely on it |
| `whisperx-vad/whisperx_vad.json` | `{ schema_version, song_name, generated_from, metadata, frames[], vocal_phrase[] }` — per-50ms-frame `voiceness` plus hysteresis-binarized `vocal_phrase` spans | fused into the top-level `arrangement_state.json`'s `vocals_phrase` field. Written by the `whisperx` Compose service (`whisperx_vad/export.py`), before `./analyze` runs |
| `whisperx-vad/vocal_onsets.json` | **New in v3.6 item 10 (D10.1).** `{ schema_version, song_name, generated_from, metadata: { total_words }, words[] }`; each word `{ time, word, confidence }` — `faster_whisper` large-v3 word timestamps over the vocal stem | Nothing in `src/` or `mcp/` reads it since v3.10 item 8 removed its only consumer (`section_clues.py`). Written by the same `whisperx` service run (`whisperx_vad/export.py`'s `export_vocal_onsets`) |
| `validation/phase_1_report.{json,md}` | per-domain scores and mismatch detail | judge where output is trustworthy. Mismatch rows are caution signals, never generation input |
| `validation/human_hints_alignment.{json,md}` | hint windows vs. generated sections/events | issue triage; written only when human hints exist |
| `validation/drops_score.json` | advisory `--compare drops` score | never gates the exit code |
| `_run_request.json` | **New in v3.8 item 1.** `{ song, requested_at }` | queue a full `./analyze` run — written by the debugger's Run analysis button and the MCP `request_analysis` tool, consumed and deleted by `./analysis-watcher` (host process, not a container). Never MCP-exposed as a top-level file; `mcp/runs.py` is a bounded, documented exception (D3.1) |
| `_run_progress.json` | **New in v3.8 item 1.** `{ song, status: "queued"\|"running"\|"done"\|"failed", stage, requested_at, started_at, finished_at, error }` | poll a queued run's state — written by `./analysis-watcher`, read by the debugger and the MCP `get_analysis_progress` tool (D3.1 exception, same as above). Overwritten per run; no history kept |

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
| `human/lyric_validations.json` | operator's hand-verification of Moises lyric-token timing: `{ schema_version, song_name, validated_ids: [int] }` — the ids of `moises/lyrics.json` word tokens checked against the waveform (v3.4 item 5) | written **per-click** (not on Save — D5.1) by the debugger's Moises Lyrics events panel ✔ button (`PUT /api/lyric-validations/<song>`, dev-only). An **overlay**: the lane shows a listed token at confidence `1` with a distinct tint; `moises/lyrics.json` is never edited. One producer (the operator) — no `field_sources`/`source`. Nothing in `src/` or `mcp/` reads it |
| `human/segments.json` | hand-marked gold section boundaries: a flat `[{ start, end, label }]` list, `label` in `docs/segments-vocabulary.md` terms (v3.5); any `energy` / `tension` / `rhythm` keys in it (v3.6 item 10) are ignored since v3.10 item 8 and never rewritten | validation (`human_segments` boundary recall/precision/F1 in the phase-1 report) **and** publish fusion — `ui_data.build_ui_data` rebuilds `sections.json`'s boundaries/labels from these spans outright when present for a song, at fixed `confidence: 0.8`, `function_confidence`/`function_status`/`same_label_as` still inherited from the best-overlapping allin1 section. Full boundary/label precedence in [`analysis.segments.md`](analysis.segments.md) |
| `moises/chords.json` | Moises.ai **inference**, not human truth — no confidence field, so no row is curated | measure *agreement with a second model*, never correctness |
| `moises/segments.json` | Moises.ai inference: a flat `[{ start, end, label }]` list — no confidence field, so no row is curated | boundary-quality comparison, **and** publish fusion — one tier below `human/segments.json`, at fixed `confidence: 0.6`. Full precedence in [`analysis.segments.md`](analysis.segments.md) |
| `moises/lyrics.json` | word-level timing with `text`, `start`, `end`, `line_id`, `<SOL>`/`<EOL>` markers and per-word confidence | lyric-synced moments; vocal-presence priors. **Only `"0.99"`-confidence rows are operator-curated.** Read-only, inference-only — operator timing checks are recorded in `human/lyric_validations.json` (v3.4 item 5 / D6), never by editing this file |
| `pre-analysis/structure.json` | web-researched prior (v3.10 item 7): `schema_version "1.1"` (`1.0` files stay readable; `write_structure_hint` refuses them), `track` (artist, title, version, remixer, `version_duration_s`), `genre` (family, subgenre, bpm), `shape` (`drops`, `chorus_is_drop`, `has_build_ups` each `{value, basis, source, quote}`; `vocals` a plain enum), `confidence`, `sources[]`; unknown = `null`, never a time. Schema in `docs/mcp-definition.md`, "Pre-analysis structure hint" | a prior for experiments only; the `src/` readers are the `version-check` stage (v3.11 item 21, compares its duration and BPM with `info.json`) and `hint-verdict` (item 22). Corpus: 27 of 27 are `1.1`, 6 of 81 `shape` evidence fields non-null Written only by `write_structure_hint` |
| `pre-analysis/verdict.json` (v3.11 item 21) | `{ schema_version, song_name, generated_from, version_check: { version_mismatch, duration_delta_s, bpm_delta_pct } }`. `duration_delta_s` = hint `track.version_duration_s` - `info.json` `duration` (signed, s); `bpm_delta_pct` = gap between hint `genre.bpm` and `info.json` `bpm` after folding half/double time, in percent of `bpm`; either is `null` when a side is `null`. `version_mismatch` is `true` when `abs(duration_delta_s) > 5` or `bpm_delta_pct > 3`. Item 22 adds `verdicts: { generated_from, status: "evaluated"\|"skipped", reason: null\|"version_mismatch"\|"family"\|"hint_schema", fields }`; `fields` holds one row per non-null hint field among `drops`, `has_build_ups`, `chorus_is_drop`, `vocals`, `bpm`, each `{ verdict: "confirmed"\|"refuted"\|"unresolved", evidence }` where `evidence` is the expected value plus section ids and counts (`drop_runs`, `drop_section_ids`, `drop_like_chorus_section_ids`, `build_up_section_ids`, `sung_section_ids`, `vocals_phrase_count`, `coverage_pct`, `analysed_bpm`, `bpm_delta_pct`), never a time. `fields` is empty when `status` is `skipped`. Item 23 adds a `second_pass: { fields: { <field>: { verdict: null\|"confirmed"\|"refuted", wrong: null\|"hint"\|"analysis", evidence: null\|{ stems, drum_density, dropouts, loudness, web_search }, first_pass_verdict, operator: null\|{ answer: "confirmed"\|"rejected", reason, check_id } } } }` block, written only by `write_verdict_pass` (and `operator` by the debugger's approve flow); `hint-verdict` and `version-check` preserve it | whether the hint describes the recording that was analysed. Written by the `version-check` stage after `info.json`; **absent when the song has no hint** (not an error). Never published at top level, never read by the MCP server; nothing in the analysis reads it. Each stage replaces only its own block (`version_check` / `verdicts`); `hint-verdict` needs the `version_check` block and the published `sections.json`, `arrangement_state.json`, `loudness.json`, `info.json` |
| `proposals/*.json` | unpromoted experiment output | audition against the song in the debugger. Not a contract; see the source experiment's README |

## Where to start

| Task | Order |
| --- | --- |
| Show briefing | `sections.json` → `song_event_timeline.json` → `hints.json` |
| Cue generation | `sections.json` → `beats.json` → `song_event_timeline.json` |
| Trust and QA | `validation/phase_1_report.md` → `.json` → the matching `reference/` files |
| Debugger work | invert: `artifacts/` first, top-level files only as compact projections |
