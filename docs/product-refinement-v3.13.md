# Product refinement — v3.13

**Status: items 1–2 planned** in [`implementation-plan-v3.13.md`](implementation-plan-v3.13.md); item 3 awaits the plan. Theme: land each light change on the moment the band hits, not a beat early, and give every song its vocal cadence. Open v3.12 item 3 stays in [`product-refinement-v3.12.md`](product-refinement-v3.12.md); v3.12 item 7 is superseded by item 3 here. Nothing here re-anchors the grid.

A cue a beat early reads as a miss; a cue a few ms late is forgiven. v3.12 item 37 hit 8 of 8 targets, but three of them (Medicine 8, 19, 23) sit 0.95–1.00 beat early because a half-beat-refined point is floored to the beat that contains the change (`docs/issues.md`).

---

## 1. Light-change point time: round toward the bar edge

**Change.** In `light_changes.py` `locate`, a half-beat shift of ±1 row lands on the bar edge; ±2 rows lands one whole beat either side. Today `shift // 2` sends −1 to the previous beat. `bar_edge_offset_beats` follows. Nothing else in the detector moves: same points, same roles, same count (494 on the corpus).

A half-beat sits between two beats, so "nearest" is a tie; it is resolved toward the bar edge because that is where the band counts the change, and the lights are then never earlier than the physical onset by more than half a beat.

| | |
| --- | --- |
| Writes | `artifacts/light_changes/light_changes.json` `time`, `bar`, `beat`, `bar_edge_offset_beats`; published `light_change` rows and `light_change_role` follow |
| Done when | the 8 v3.12 targets are within ½ beat; Medicine 9/16, Armin 55/59/60 unchanged; Medicine 10–14 empty; corpus point count and roles unchanged |

---

## 2. Snap a point to the kick that plays it

**Change.** After item 1, a point whose grid beat has a trusted kick attack within ¼ beat takes the kick's `time`: `kick_attacks.json` event, `echo_of` null, `on_grid` true, `grid` `trusted`, `confidence` ≥ 0.5, nearest wins. `bar`/`beat` stay the grid beat's. The point records `snap: { source: "kick", offset_ms }` or `snap: null`. Nothing is snapped where kicks are unreliable (hat-bed songs, D1): the rule then abstains and item 1's time stands.

Only the points move, never the grid: this is the cheap half of "restart the metronome on the next inferred kick" — the whole-grid version is v3.12 item 3's open follow-up and needs the drift measurement in the plan's D items first.

**Contract.** `light_changes.json` `time` and the published `light_change` `start_time` are "on a `beats.json` beat or within ¼ beat of one (kick-snapped)", no longer exactly on a beat. `position` on the MCP projection is unchanged (it is computed from time). Producer vocabulary unchanged.

| | |
| --- | --- |
| Writes | `light_changes.json` `time`, new `snap`; `song_event_timeline.json` `light_change` `start_time`; `downstream-contract.md`, `artifacts.md`, `mcp-definition.md` |
| Done when | no point moves more than ¼ beat from its item-1 time; snapped share per song reported; operator lane review on the held-out songs (plan item 42) does not reject it |

---

## 3. Vocal cadence from vocal pitch, not lyrics

**Change.** `vocal_cadence.json` is derived from the vocals stem's pitch track on every song; `lyrics.json` stops being an input to any published inference. A new measurement stage `extract-vocal-pitch` (1.6; pYIN over `artifacts/stems/vocals.wav`, 80–1000 Hz, ~12 ms hop, CPU) writes `artifacts/vocal_pitch/f0.json` rows `{ time, f0_hz, voiced, level_db }`. `publish-vocal-cadence` (7.4) reads that artifact plus the published `beats.json`, `sections.json`, `info.json` and publishes:

- `phrases[]` `{ phrase_id, start_s, end_s, start_position, end_position, duration_beats, resolve_time_s, resolve_position, pickup }` — a voiced run of the stem, split where voicing stops for ≥ 120 ms (a breath); runs under 150 ms dropped. Replaces `lines[]`.
- per section: `lead_in_bars` (+ `lead_in_phrase_id`, resolve time/position, `lead_in_reason`; today's rule, over phrases), `rests[]` (≥ 1 beat unvoiced between phrases), `held_notes[]` `{ start_s, end_s, length_beats, midi }` (pitch within ±1 semitone for ≥ 2 beats, measured on f0 continuity, never on amplitude), `onsets_per_bar[]` (vocals-stem onsets; replaces `tokens_per_bar`), `voiced_per_bar[]` (voiced fraction of each bar), `top_note` `{ midi, time_s, position }` (highest pitch held ≥ 0.3 s in the section), `median_midi`.
- `calls[]` unchanged in shape, read only from `reference/human/lyrics.json` `(hey)` tokens (the operator's hand mark, time only); `[]` otherwise. The moises tier is dropped.
- `source` is `"vocal_pitch"` on every song; `reason` is set only when the stem has no voiced frame (every array then `[]`). The human/moises tiers and their precedence go.

A lyric line is a textual unit, not an acoustic one: on Queen of Kings 9 of 42 line starts follow an audible breath and on Hideaway 16 of 19 line gaps are under a beat, so lines are unrecoverable without text and the v3.12 item 7 gate (F1 ≥ 0.7 against line starts) can never be met — and no cue needs them. What a cue needs — the vocal entrance, the note held under a build, the peak, the rest — is in the pitch track, and it reproduces the operator's own hints (Queen of Kings: the pre-drop held note at bar 24 beat 1, the sustained high note at bar 65 beat 3). Do not re-aim this at lyric lines or at a transcript.

**Removed** (dead or superseded; nothing else reads them):

- `cadence_repeats[]` and the onset-pattern matcher — section repetition is already `sections.json` `same_label_as`.
- `lines[]`, `line_id`, `token_count`, `tokens_per_bar[]`, and lyric word-end `held_notes` (ASR word durations, not notes).
- `whisperx_vad/vocal_onsets.py`, `export_vocal_onsets`, `artifacts/whisperx-vad/vocal_onsets.json`, the `faster_whisper` load in the `whisperx` service and its `WHISPER_DEVICE` note; the service writes `whisperx_vad.json` only.
- `experiments/vocal_phrases/`, its `reference/proposals/vocal_phrases.json` export and the debugger's **Vocal Phrases** lane (superseded; its sustained-note pass scanned amplitude and found nothing).
- `docs/issues.md` entries "`whisperx_vad/vocal_onsets.py` and `vocal_onsets.json` are dead" and "`vocal_cadence` line starts without lyrics are unsolved"; `experiments.md`'s vocal_phrases entry marked superseded.

**Contract.** `vocal_cadence.json` as above; `field_sources` → `vocal_pitch` (`calls` → `human`). `get_song_overview` per-section fields become `lead_in_bars`, `rest_count`, `held_note_count`, `call_count`, `top_note_midi` (`cadence_repeat_best` dropped); byte budget 6900 unchanged. `get_detail` carries `phrases`, `rests`, `held_notes`, `onsets_per_bar`, `voiced_per_bar`. Timing and pitch only — no text, ever. Debugger **Vocal Cadence** lane: phrases as blocks, held notes as a second block row, calls as points.

| | |
| --- | --- |
| Writes | `src/analyzer/stages/vocal_pitch.py` (new), `vocal_cadence.py`, `pipeline.py`, `paths.py`; `whisperx_vad/`, `docker-compose.yml` note; `ui/` Vocal Cadence lane, Vocal Phrases lane removed; `artifacts.md`, `downstream-contract.md`, `mcp-definition.md`, `ui-definition.md`, `cli.md`, `source-map.md`, `issues.md`, `experiments.md`, `CLAUDE.md` row; MCP fixtures |
| Done when | gate below passes on the 5 lyric songs (lyrics are validation only, never read by `src/` except `calls`); all 27 songs carry `source: "vocal_pitch"`; `vocal_onsets.json` and `vocal_phrases.json` are gone from every song dir; `docker compose run --rm test`, MCP `smoke-test`, visual suite green; determinism (one song twice, byte-identical); ≤ 2 min/song for the new stage |

**Gate** (fixed before measuring; fail → experiment only, `source: null` as today, a `D` item):

- Phrase starts: precision ≥ 0.8 within ½ beat of a lyric token start (no phrase begins where nothing is sung); recall ≥ 0.8 within ½ beat of the lyric line starts preceded by a word gap ≥ 120 ms.
- Held notes: every held note overlaps a lyric token span (precision 1.0, none on bleed); every operator hint naming a held, sustained or long note (Queen of Kings 45.0 s and 125.0 s; `_test_song`'s note through the drop build) has one within 1 beat.
- `lead_in_bars` on Queen of Kings equals today's human-lyric value on every section where today's is non-null.

---

## Validation (every item)

Thresholds are fixed before measuring; nothing is tuned on the held-out songs.

| Tier | Songs | Checks |
| --- | --- | --- |
| Tuning (v3.12 set) | *Medicine-MilkInc*, *Armin - Revolution* | the 8 targets, bar start from `bar_features.json`: offset in beats before/after; all within ½ beat; 10–14 empty |
| Held out, kick-rich | *Fascination* (650 trusted kicks ≥ 0.5), *Cinderella* (368, 5 irregular bars), *Titanium* (123, human hints), *Queen of Kings* (71, human hints + lyrics) | item 2 snaps most on-beat points; snapped share and mean \|offset_ms\| per song; operator lane review of every moved point |
| Held out, kick-poor | *Sash - Raindrops* (8), *Charli-VonDutch* (22, no kick in the spans item 3 named), *ayuni* (74) | item 2 abstains where the operator hears no kick; no point moves by more than ¼ beat |
| Vocal pitch (item 3) | *Armin*, *Hideaway*, *Queen of Kings*, *Titanium*, *_test_song* (lyrics as gold) | item 3 gate; on the 22 lyric-less songs: phrases/min, held notes per song, lane review on *Medicine* and *ayuni* |
| Corpus (27 songs) | all | point count 494, roles and points/min unchanged by item 1; histogram of `bar_edge_offset_beats` before/after (the −1 bucket must shrink, +1 unchanged); `drop` points within ±1 beat of a `human_hints.json` boundary on the 15 hinted songs, before/after, must not decrease (informational, hints are coarse); determinism: re-run one song twice, byte-identical |
