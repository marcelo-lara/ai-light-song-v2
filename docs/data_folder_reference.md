# Data Folder Reference

## Purpose

This document explains the current `data/` folder layout, what each file is for, and which files are most useful when designing a light show.

Use this as a navigation guide first, then open the referenced files for the actual song-specific details.

## Working Rules

- `data/analysis/<Song - Artist>/reference/` is reference and validation material. Do not treat it as generation input.
- `data/analysis/<Song - Artist>/artifacts/` contains generated analysis artifacts and intermediate caches, including the separated stems under `artifacts/stems/`.
- `data/analysis/<Song - Artist>/` (outside the nested `artifacts/` and `reference/` folders) contains a stable UI-facing output contract. Each song directory must contain exactly `beats.json`, `hints.json`, `info.json`, `sections.json`, `song_event_timeline.json`, and the `artifacts/` subfolder.
- Do not add or remove the top-level files under `data/analysis/<Song - Artist>/` unless a UI contract change makes that strictly required.
- The internal debugger served from `/ui/` primarily reads `data/analysis/<Song - Artist>/artifacts/` directly and uses the top-level `data/analysis/<Song - Artist>/` files only as supporting context when useful.
- The debugger is read-only against generated data and must not write files into `data/analysis/`, with the single exception below.
- Story 7.8 allows the helper UI to update only `data/analysis/<Song - Artist>/reference/human/human_hints.json` on explicit save.
- `data/fixtures/` contains rig and focus-point context.
- `data/songs/` contains source audio. `data/analysis/<Song - Artist>/artifacts/stems/` contains stem-separated audio derived from those songs.

## Folder Structure

```text
data/
  analysis/
    <Song - Artist>/
      beats.json
      hints.json
      info.json
        song_event_timeline.json
      sections.json
      reference/
        human/
          human_hints.json
        moises/
          chords.json
          lyrics.json
          segments.json
      artifacts/
        stems/
          bass.wav
          drums.wav
          harmonic.wav
          metadata.json
          vocals.wav
        energy_summary/
          features.json
          hints.json
        essentia/
          beats.json
          fft_bands.json
          hpcp.json
        event_inference/
          events.machine.json
          features.json
          rule_candidates.json
          timeline_index.json
        pattern_mining/
          chord_patterns.json
        section_segmentation/
          sections.json
        symbolic_transcription/
          basic_pitch/
            bass.json
            bass.mid
            drums.json
            drums.mid
            full_mix.json
            full_mix.mid
            harmonic.json
            harmonic.mid
            vocals.json
            vocals.mid
          drum_events.json
          omnizart/
            drums.mid
          hints.json
          validation.json
        validation/
          phase_1_report.json
          phase_1_report.md
          song_event_timeline.md
          song_events.overrides.json
          song_events.review.json
          song_events.review.md
        layer_a_harmonic.json
        genre.json
        layer_b_symbolic.json
        layer_c_energy.json
        layer_d_patterns.json
  fixtures/
    fixtures.json
    pois.json
  songs/
    <Song - Artist>.mp3
```

## Best Starting Points For Light Show Design

If you only open a few files, start here in this order:

1. `data/analysis/<Song - Artist>/sections.json`
2. `data/analysis/<Song - Artist>/song_event_timeline.json`
3. `data/analysis/<Song - Artist>/hints.json`
4. `data/analysis/<Song - Artist>/beats.json`
5. `data/analysis/<Song - Artist>/artifacts/section_segmentation/sections.json`
6. `data/analysis/<Song - Artist>/artifacts/layer_c_energy.json`
7. `data/analysis/<Song - Artist>/artifacts/layer_a_harmonic.json`

These are also, near enough, the files the downstream MCP server actually
projects — see [`reference/analysis-input-guide.md`](reference/analysis-input-guide.md).
9. `data/analysis/<Song - Artist>/artifacts/layer_b_symbolic.json`
10. `data/fixtures/fixtures.json`
11. `data/fixtures/pois.json`

For internal debugger work, invert that priority: start with `data/analysis/<Song - Artist>/artifacts/` layer and validation files first, then use `data/analysis/<Song - Artist>/` only as compact helper projections.

## Top-Level Folder Reference

### `data/songs/`

Source song masters, usually `.mp3` files. These are the original inputs to the pipeline.

LLM note: this folder is useful for provenance, but the structured design work should usually rely on generated artifacts instead of raw audio file names.

### `data/analysis/<Song - Artist>/artifacts/stems/`

Per-song separated audio stems and lightweight stem metadata. These are derived from the source song and used by harmonic and symbolic stages.

### `data/analysis/<Song - Artist>/artifacts/`

Per-song generated analysis artifacts. This is the main machine-readable analysis area.

The internal debugger should treat this folder as its primary read surface.

### `data/analysis/<Song - Artist>/`

Per-song consumer-facing outputs, living alongside (but outside) the nested `artifacts/` and `reference/` folders. These files are more compact and presentation-friendly than the artifact files, and the directory is a stable UI contract rather than an open-ended export area.

The internal debugger may read selected files here for quick navigation or compact comparisons, but it must not treat this folder as its primary source of truth and must not write additional files into it.

### `data/fixtures/`

Lighting rig metadata and point-of-interest targeting data.

### `data/analysis/<Song - Artist>/reference/`

Reference and curated external material, nested under each song's analysis folder, including Moises-style chord, segment, and lyric references for validation and review plus the helper UI human-hints file at `data/analysis/<Song - Artist>/reference/human/human_hints.json`.

Each hint in `human_hints.json` carries `id`, `title`, `start_time`, `end_time`, `summary`, `lighting_hint`, and an optional `captured_from`: a single human-readable string naming the experiment or lane an entry was captured from (e.g. `"allin1 Sections · experiments/allin1"`). It is written only by the debugger's "Create human hint" action, is absent on hand-authored hints, and is informative only — no analyzer code reads it (plan v1.5 item 8 / D11).

**v2.1:** `reference/human/song_facts.json` (new) holds song-level human-confirmed facts (`genre`, `form_family`, `has_drop`), each `{ value, provenance: "human-confirmed", confirmed_on }`. It is a sibling of `human_hints.json`, written **only** by the debugger UI on an explicit human save (Story 8.10). The analyzer reads it but never writes `reference/`.

## v2.1 artifact and field changes

- `artifacts/section_segmentation/sections.json` (`schema_version` `"1.1"`): new song-level `form_family` object; per-section `form_role` (primary label, gates the top-level `label`), `form_role_confidence`, `form_role_margin`, `energy_character` (former energy-shape label), `repetition_group` / `variant_of` / `similarity`, and `confidence_terms`. `confidence` now measures boundary/label certainty only and spans the full `[0, 1]` range.
- Top-level `sections.json`: every row carries `section_id` (join key, item 3.2), plus `form_role`, `energy_character`, `repetition_group`, numeric `confidence`.
- `song_event_timeline.json` (`schema_version` `"1.1"`): composite events with `phases[]`; `layer_add`/`layer_remove` removed and replaced by `texture_summary[]`; `intensity` is an absolute cross-song scale.
- `artifacts/validation/review_queue.json` (new): ranked open questions for a human to answer into `song_facts.json`.
- `artifacts/validation/form_score.json`, `drops_score.json` (new): advisory `--compare form,drops` scores.

## File Reference

### `data/fixtures/fixtures.json`

Summary: rig inventory. Each row identifies a fixture, its fixture type, DMX base channel, and normalized stage location.

Why it matters: this is the main file for understanding what hardware exists and where it sits.

LLM hint:
- See: `id`, `fixture`, `base_channel`, and `location`.
- Use: map abstract looks onto real fixture roles such as key mover, mirrored FX heads, center wash, and edge wash.
- Use: keep repeated callbacks on stable fixture groups so motifs feel intentional.
- Avoid: inventing fixture capabilities that are not implied by the fixture type.

### `data/fixtures/pois.json`

Summary: named points of interest with precomputed pan and tilt values for compatible moving fixtures.

Why it matters: this is the fastest way to target real scenic locations without solving pan and tilt yourself.

LLM hint:
- See: `id`, `name`, and `fixtures.<fixture_id>.pan` and `tilt`.
- Use: snap spotlight moments, lyric callouts, or instrumental solos to named stage targets.
- Use: keep focus recalls repeatable across sections by referencing the same POI ids.
- Avoid: inferring geometry from the shared `location` alone when direct pan and tilt values are already provided.

### `data/songs/<Song - Artist>.mp3`

Summary: raw song audio used as the root input for the analysis pipeline.

Why it matters: provenance and audio truth source.

LLM note: useful as a source path, but not the best text-first input for cue design.

### `data/analysis/<Song - Artist>/artifacts/stems/metadata.json`

Summary: stem-generation metadata, including source song path, separation engine, and paths to generated stem files.

Why it matters: explains where the stem files came from and confirms available stem paths.

LLM hint:
- See: `generated_from.engine` and the `stems` object.
- Use: confirm which isolated sources exist before leaning on bass-, vocal-, or harmonic-specific analysis.
- Use: trace unexpected downstream behavior back to a missing or weak stem source.

### `data/analysis/<Song - Artist>/artifacts/stems/bass.wav`

Summary: isolated bass stem audio.

Why it matters: upstream source for bass-oriented symbolic analysis and bass note extraction.

### `data/analysis/<Song - Artist>/artifacts/stems/drums.wav`

Summary: isolated drums stem audio.

Why it matters: upstream source for rhythm- and hit-oriented symbolic review and drum-hit transcription.

### `data/analysis/<Song - Artist>/artifacts/stems/harmonic.wav`

Summary: isolated harmonic stem audio.

Why it matters: upstream source for chord and harmony extraction.

### `data/analysis/<Song - Artist>/artifacts/stems/vocals.wav`

Summary: isolated vocal stem audio.

Why it matters: upstream source for lyric-adjacent phrasing and melodic symbolic analysis.

### `data/analysis/<Song - Artist>/artifacts/essentia/beats.json`

Summary: canonical timing grid. Contains BPM, duration, and a beat-by-beat timeline with bar numbers and beat-in-bar indices.

Why it matters: this is the main timing spine for almost every other artifact.

LLM hint:
- See: `beats[].time`, `bar`, `beat_in_bar`, and `type`.
- Use: place cues on exact beat or downbeat times.
- Use: convert structural ideas like “every bar” or “beat 4 pickup” into deterministic timestamps.
- Use: align accents, blackout hits, chase resets, and camera-style punctuation to the shared grid.

### `data/analysis/<Song - Artist>/artifacts/essentia/hpcp.json`

Summary: beat-aligned harmonic pitch class profiles. Each beat has a 12-bin chroma-like vector.

Why it matters: low-level harmonic color signal that supports key and chord interpretation.

LLM hint:
- See: `hpcp_by_beat[].vector`.
- Use: only when you need lower-level harmonic evidence beyond the resolved chord labels.
- Use: estimate tonal brightness, harmonic ambiguity, or chromatic tension where the chord track feels too coarse.
- Avoid: starting here if `layer_a_harmonic.json` already answers the question.

### `data/analysis/<Song - Artist>/artifacts/energy_summary/features.json`

Summary: dense frame-level energy features including loudness, spectral centroid, spectral flux, and onset strength.

Why it matters: raw support signal behind section energy and accent candidates.

LLM hint:
- See: frame-level `loudness`, `spectral_centroid`, `spectral_flux`, and `onset_strength`.
- Use: design custom micro-accents, motion-speed changes, or brightness sweeps when section-level summaries are too coarse.
- Use: audit whether a proposed cue pattern matches the actual transient behavior.
- Avoid: treating this as the first file for section planning; use `layer_c_energy.json` first.

### `data/analysis/<Song - Artist>/artifacts/essentia/fft_bands.json`

Summary: seven fixed low-to-high spectral band levels sampled every 50 ms from the source mix.

Why it matters: this is the debugger-facing spectral-motion surface for quick low-versus-high energy inspection without opening a full spectrogram tool.

LLM hint:
- See: `bands[]`, `frames[]`, and `metadata.interval_ms`.
- Use: inspect whether bass-driven, mid-driven, or top-end-driven motion explains a cue idea or an event boundary.
- Use: compare broad spectral movement against waveform, drums, and energy lanes when sections feel too coarse.
- Avoid: treating this as a replacement for the stable `data/analysis/` contract. It is an artifact-first debugger surface.

### `data/analysis/<Song - Artist>/artifacts/essentia/rms_loudness.json`

Summary: shared-timeline RMS loudness sampled every 10 ms for the source mix plus the required bass, drums, harmonic, and vocal stems.

Why it matters: this is the fastest debugger-facing view of which source is physically active at fine time resolution.

LLM hint:
- See: `sources[]`, `frames[]`, `metadata.interval_ms`, and `metadata.source_order`.
- Use: compare the mix against the isolated stems when a cue feels driven by drums, bass, vocals, or harmonic bed.
- Use: inspect short-lived loudness bursts that are too brief for section- or beat-level summaries.
- Avoid: treating normalized values as calibrated LUFS. They are per-song per-source display values.

### `data/analysis/<Song - Artist>/artifacts/essentia/loudness_envelope.json`

Summary: slower loudness envelope sampled on 200 ms windows for the source mix plus the required stems.

Why it matters: smooths the faster RMS motion into a source-aware macro-dynamics view that is easier to compare against section transitions.

LLM hint:
- See: `sources[]`, `frames[]`, `metadata.window_ms`, and `metadata.source_order`.
- Use: inspect whether a rise, swell, or release is coming from the full mix or from a specific isolated source.
- Use: compare broad per-source dynamics against sections, phrases, and machine-event boundaries.
- Avoid: assuming this file replaces the denser RMS file when you need short transient detail.

### `data/analysis/<Song - Artist>/artifacts/energy_summary/hints.json`

Summary: producer-scoped named energy-event identifiers such as drops and other later-defined song moments.

Why it matters: this is the contract for event-level energy semantics that go beyond generic accent candidates.

LLM hint:
- See: `supported_identifiers` and `events[]`.
- Use: detect whether a named moment such as `drop` has already been inferred from the energy layer.
- Use: distinguish broad section energy from sharper named event moments.
- Avoid: inventing undocumented identifier labels when this file is absent or incomplete.

### `data/analysis/<Song - Artist>/artifacts/event_inference/features.json`

Summary: normalized event-feature rows aligned to the shared beat, bar, section, and phrase timeline.

Why it matters: this is the canonical feature surface behind rule candidates and machine event inference.

LLM hint:
- See: per-window feature values, timing anchors, and normalized feature names.
- Use: understand why later event stages promoted or rejected a candidate window.
- Use: audit whether a claimed drop, build, or break has support in the upstream normalized features.

### `data/analysis/<Song - Artist>/artifacts/event_inference/timeline_index.json`

Summary: helper index that maps event-analysis windows back to shared timing anchors and upstream layer references.

Why it matters: quickest way to explain where an event window sits in relation to beats, sections, and phrases.

LLM hint:
- See: anchor ids, section ids, and time-window references.
- Use: cross-reference event windows without recomputing alignment logic from multiple source files.

### `data/analysis/<Song - Artist>/artifacts/event_inference/rule_candidates.json`

Summary: baseline rule-generated event candidates before review merging or final machine-event promotion.

Why it matters: this shows the first explicit event hypotheses the pipeline generated.

LLM hint:
- See: candidate labels, supporting features, confidence values, and timing windows.
- Use: inspect why the baseline detector believed a moment might be a drop, build, or other supported event.
- Avoid: treating every rule candidate as final; the reviewed export is the downstream contract.

### `data/analysis/<Song - Artist>/artifacts/event_inference/events.machine.json`

Summary: canonical machine-generated event set after the Epic 5 inference chain applies schema normalization and confidence handling.

Why it matters: this is the structured source for reviewed event exports and lighting-facing event timing.

LLM hint:
- See: canonical event ids, event types, start and end times, confidence, and provenance fields.
- Use: build event-aware cue logic from this file when you need the machine view before human review merges.
- Use: cross-check event provenance against `rule_candidates.json`, `features.json`, and `energy_summary/hints.json`.

### `data/analysis/<Song - Artist>/artifacts/section_segmentation/sections.json`

Summary: canonical structural windows with section ids, start and end times, labels, and confidence scores.

Why it matters: section boundaries are a primary backbone for large cue changes.

LLM hint:
- See: `section_id`, `start`, `end`, `label`, and `confidence`.
- Use: define section-scoped looks, transitions, and intensity arcs.
- Use: group phrase-level callbacks under stable section identity.
- Treat labels as helpful but secondary to the actual time windows.

### `data/analysis/<Song - Artist>/artifacts/symbolic_transcription/validation.json`

Summary: source-level validation and promotion report for symbolic transcription. Explains which transcription sources were promoted into the final symbolic layer.

Why it matters: trust and provenance check for note-driven features.

LLM hint:
- See: `sources[]`, `decision`, `promote_to_final`, `reason`, and `promoted_sources`.
- Use: judge whether bass, vocals, or full-mix notes are reliable enough to drive visible effects.
- Use: explain confidence limits when symbolic content feels noisy or sparse.
- Avoid: treating rejected or auxiliary-only sources as equal to promoted sources.

### `data/analysis/<Song - Artist>/artifacts/symbolic_transcription/hints.json`

Summary: producer-scoped inferred section hints derived from the aligned symbolic timeline.

Why it matters: provenance layer for editable hint generation.

LLM hint:
- See: `sections[].section_id`, `label`, and `hints[]`.
- Use: inspect which hints were inferred deterministically before any user edits were merged.
- Avoid: treating this producer-scoped file as the user-editable source; use `data/analysis/<Song - Artist>/hints.json` for that.

### `data/analysis/<Song - Artist>/artifacts/symbolic_transcription/drum_events.json`

Summary: simple producer-scoped drum-hit review artifact containing kick, snare, and hat event rows plus summary counts.

Why it matters: fastest way to inspect rhythmic pulse and debug drum-hit translation without opening note-heavy symbolic layers first.

LLM hint:
- See: `events[].time`, `event_type`, `confidence`, and the `summary` counts.
- Use: inspect whether kick, snare, and hat placements support the intended rhythmic reading of the song.
- Avoid: treating this phase-1 review artifact as a full replacement for the canonical symbolic layer.

### `data/analysis/<Song - Artist>/artifacts/symbolic_transcription/omnizart/drums.mid`

Summary: raw Omnizart drum-transcription MIDI cache for the isolated drums stem.

Why it matters: first review surface when the normalized `drum_events.json` counts or labels look suspicious.

LLM hint:
- See: GM drum note pitches such as 35, 38, and 42 to confirm kick, snare, and hat placements.
- Use: compare raw Omnizart output against the normalized review artifact when unsupported or unresolved events appear.
- Avoid: treating the raw MIDI as the final review contract; `drum_events.json` is the normalized producer-scoped artifact.

### `data/analysis/<Song - Artist>/artifacts/symbolic_transcription/basic_pitch/bass.json`

Summary: raw Basic Pitch note cache for the bass stem. Includes note timing, MIDI pitch, confidence, and alignment metadata.

Why it matters: direct source for the compact `bass` field in output beat rows.

LLM hint:
- See: `notes[].time`, `end_s`, `pitch`, `confidence`, and alignment fields.
- Use: inspect specific bass entries when debugging pulse logic or bass-driven movement.
- Use: recover more granular bass-note timing than the output beat projection preserves.

### `data/analysis/<Song - Artist>/artifacts/symbolic_transcription/basic_pitch/bass.mid`

Summary: MIDI export of the bass stem transcription.

Why it matters: convenient for DAW inspection or external MIDI tools.

### `data/analysis/<Song - Artist>/artifacts/symbolic_transcription/basic_pitch/drums.json`

Summary: raw Basic Pitch note cache for the drums stem.

Why it matters: mostly auxiliary review data because drums are not promoted by default in the current symbolic assembly.

### `data/analysis/<Song - Artist>/artifacts/symbolic_transcription/basic_pitch/drums.mid`

Summary: MIDI export of the drums stem transcription.

Why it matters: useful for manual review, not usually a primary lighting-design input.

### `data/analysis/<Song - Artist>/artifacts/symbolic_transcription/basic_pitch/full_mix.json`

Summary: raw Basic Pitch note cache for the full mix.

Why it matters: fills gaps left by stem-only transcription and can explain why a note appears in the final symbolic layer.

LLM hint:
- See: `notes[]` when a phrase or motif seems present in the final symbolic layer but not obvious in stem-specific caches.
- Use: as a recovery path for missing melodic texture, not as the first symbolic file to read.

### `data/analysis/<Song - Artist>/artifacts/symbolic_transcription/basic_pitch/full_mix.mid`

Summary: MIDI export of the full-mix transcription.

Why it matters: external review aid.

### `data/analysis/<Song - Artist>/artifacts/symbolic_transcription/basic_pitch/harmonic.json`

Summary: raw Basic Pitch note cache for the harmonic stem.

Why it matters: dense pitched texture source that feeds the final symbolic layer.

LLM hint:
- See: `notes[]` around phrase starts and section changes.
- Use: understand register spread and harmonic-note density when building wash complexity or texture-linked movement.
- Use: cross-check motif claims from `layer_b_symbolic.json` against raw note timing.

### `data/analysis/<Song - Artist>/artifacts/symbolic_transcription/basic_pitch/harmonic.mid`

Summary: MIDI export of the harmonic stem transcription.

Why it matters: external review aid.

### `data/analysis/<Song - Artist>/artifacts/symbolic_transcription/basic_pitch/vocals.json`

Summary: raw Basic Pitch note cache for the vocal stem.

Why it matters: melodic source for vocal contour and phrase emphasis.

LLM hint:
- See: vocal note timing around lyrical phrases or refrain entries.
- Use: support follow-spot style entries, vocal-led accents, or melody-aware beam lifts.
- Combine: with `reference/moises/lyrics.json` if you want word-driven or line-driven moments.

### `data/analysis/<Song - Artist>/artifacts/symbolic_transcription/basic_pitch/vocals.mid`

Summary: MIDI export of the vocal stem transcription.

Why it matters: external review aid.

### `data/analysis/<Song - Artist>/artifacts/layer_a_harmonic.json`

Summary: canonical harmonic layer. Contains global key, chord events, and higher-level harmonic summaries.

Why it matters: main source for harmonic pacing, chord-change timing, and tonal identity.

LLM hint:
- See: `global_key` and `chords[]`.
- Use: trigger scene changes or color-family shifts on meaningful chord changes, not random beat churn.
- Use: keep verse and chorus callbacks harmonically grounded.
- Use: derive harmonic tension and release logic for cue escalation.

### `data/analysis/<Song - Artist>/artifacts/genre.json`

Summary: producer-scoped model-native genre or style winner list and review guidance.

Why it matters: optional context for what kinds of song parts or transitions may deserve closer review.

LLM hint:
- See: `genres`, `confidence`, `top_predictions`, and `guidance`.
- Use: as advisory context when reviewing likely structural or stylistic cues.
- Use: treat `unknown` as an explicit valid outcome.
- Avoid: inventing a genre from heuristics when the artifact says `unknown`.

### `data/analysis/<Song - Artist>/artifacts/layer_b_symbolic.json`

Summary: canonical symbolic layer. Contains note events, density views, phrase windows, motif groups, repetition summaries, and a human-readable description.

Why it matters: best source for phrase structure, rhythmic density, melodic contour, and repetition-driven callbacks.

LLM hint:
- See: `symbolic_summary`, `density_per_beat`, `density_per_bar`, `phrase_windows`, and `motif_summary`.
- Use: scale effect density with note density.
- Use: tie repeated motifs to repeatable looks with controlled variation.
- Use: reserve more articulate motion for dense, active passages and simplify looks when symbolic activity drops.

### `data/analysis/<Song - Artist>/artifacts/layer_c_energy.json`

Summary: canonical energy layer. Contains global energy state, per-section energy cards, and accent candidates.

Why it matters: best source for macro intensity and accent timing.

LLM hint:
- See: `global_energy`, `section_energy[]`, and `accent_candidates[]`.
- Use: drive intensity, strobe decisions, movement speed, and contrast from actual energy behavior.
- Use: separate `hit` accents from `rise` accents; they should not look the same.
- Use: keep outro restraint and chorus payoff aligned with section energy levels.

### `data/analysis/<Song - Artist>/artifacts/pattern_mining/chord_patterns.json`

Summary: producer-scoped repeated harmonic-pattern discovery output before promotion into Layer D.

Why it matters: lower-level view of pattern detection details.

LLM hint:
- See: pattern bar spans, occurrence windows, and mismatch counts.
- Use: inspect this when you need rawer pattern-discovery detail than the canonical Layer D summary exposes.

### `data/analysis/<Song - Artist>/artifacts/layer_d_patterns.json`

Summary: canonical repeated chord-pattern layer. Contains named pattern groups, representative sequences, and exact occurrence windows.

Why it matters: strongest source for structural callback logic based on repeated progression blocks.

LLM hint:
- See: `patterns[]`, UI-facing `sequence`, bar-resolved `bar_sequence`, `occurrence_count`, and `occurrences[]`.
- Use: repeat or evolve looks when the same harmonic loop returns.
- Use: escalate later occurrences of the same pattern rather than inventing unrelated scenes.
- Use: align callback timing to `start_s` and `end_s`, not rough section labels.

### `data/analysis/<Song - Artist>/artifacts/validation/phase_1_report.json`

Summary: machine-readable validation report comparing generated artifacts against reference material and internal consistency checks.

Why it matters: QA and trust report for the current analysis output.

LLM hint:
- See: overall `status`, per-domain validation blocks, and mismatch details.
- Use: judge where the analysis is strong enough to trust directly and where human review may still be needed.
- Avoid: using mismatch rows as generation input; use them as caution signals.

### `data/analysis/<Song - Artist>/artifacts/validation/phase_1_report.md`

Summary: human-readable version of the validation report.

Why it matters: fastest way to scan pass/fail state and major mismatches.

LLM hint:
- Use: as a quick trust summary before consuming lower-level artifacts.
- Use: especially when deciding whether chord-driven or section-driven cues should be treated as high-confidence.

### `data/analysis/<Song - Artist>/info.json`

Summary: output-side index file. Stores song metadata and paths to major artifacts and outputs.

Why it matters: quickest way to discover the canonical files for a song.

LLM hint:
- See: `artifacts` and `outputs`.
- Use: as a manifest for tooling, prompt construction, or navigation.

### `data/analysis/<Song - Artist>/beats.json`

Summary: compact UI-facing beat timeline with beat time, beat number, bar number, active chord, and beat-aligned bass note.

Why it matters: compact timing sheet for downstream consumers.

LLM hint:
- See: `time`, `beat`, `bar`, `chord`, `bass`, and `type`.
- Use: for lightweight cue grids, timeline tables, or beat-synced storyboard prompts.
- Use: `bass` as a simplified pulse hint, not as a replacement for full symbolic detail.

### `data/analysis/<Song - Artist>/sections.json`

Summary: compact UI-facing section timeline with presentation-friendly labels.

Why it matters: quick section overview without opening the fuller artifact files.

LLM hint:
- See: `start`, `end`, and `label`, where `label` embeds the numeric section id prefix and a confidence suffix such as `001 Intro (0.74)`.
- Use: for fast section summaries, section cue lists, and high-level show pacing.
- Avoid: treating `hints` here as the authoritative editable hint contract; use `data/analysis/<Song - Artist>/hints.json`.

### `data/analysis/<Song - Artist>/hints.json`

Summary: editable per-section hint store combining regenerated inference-authored hints with preserved user-authored hints.

Why it matters: direct hint source for the prompt-based downstream consumers.

LLM hint:
- See: `sections[].section_id`, `label`, `start`, `end`, and `hints[]`.
- Use: add or revise human-authored section guidance without losing regenerated inference hints on the next pipeline run.
- Use: match hints by `section_id` instead of relying on repeated section labels alone.
- Avoid: using this file as the canonical store for event windows such as drops or builds; prefer the reviewed event files and event timeline for that role.

### `data/analysis/<Song - Artist>/artifacts/validation/song_events.review.json`

Summary: merged review surface that combines machine-generated event rows with any preserved user-authored review decisions.

Why it matters: this is the main reviewed event contract before timeline export.

LLM hint:
- See: reviewed events, review status fields, and any preserved manual decisions.
- Use: confirm which machine events survived review and which rows need operator attention.
- Use: prefer this file over `events.machine.json` when downstream behavior should reflect the current reviewed state.

### `data/analysis/<Song - Artist>/artifacts/validation/song_events.review.md`

Summary: human-readable companion to the reviewed event JSON payload.

Why it matters: fastest way to scan reviewed event timing and status without opening raw JSON.

### `data/analysis/<Song - Artist>/artifacts/validation/song_events.overrides.json`

Summary: persisted override store for user-authored event edits and suppressions.

Why it matters: preserves manual corrections across reruns of the event inference pipeline.

LLM hint:
- See: override keys, explicit replacements, and suppressed event ids.
- Use: explain why a reviewed event differs from the machine event source.

### `data/analysis/<Song - Artist>/song_event_timeline.json`

Summary: compact LLM-friendly export of the reviewed event timeline.

Why it matters: best single structured event file for downstream lighting logic and prompt-based planning.

LLM hint:
- See: canonical event rows, exact timing windows, and any human-readable summary fields.
- Use: drive event-aware cue planning, especially when fixture overlays or focal changes should line up with drops and other named moments.
- Use: preserve canonical event ids when translating this file into prose or cue sheets.
- Use: preserve the explicit `created_by` provenance on each inferred event row.

### `data/analysis/<Song - Artist>/artifacts/validation/song_event_timeline.md`

Summary: human-readable companion to the reviewed event timeline export.

Why it matters: quick event briefing for review or operator-facing discussion.

### `data/analysis/<Song - Artist>/reference/moises/chords.json`

Summary: read-only chord comparison file from the reference set. Stores beat-like chord rows and multiple chord label formats.

Why it matters: external chord truth source for validation.

LLM hint:
- See: chord label variants such as jazz, pop, and Nashville forms.
- Use: compare against `layer_a_harmonic.json` when checking harmonic plausibility.
- Use: as validation or review input, not as a fallback generation source.

### `data/analysis/<Song - Artist>/reference/moises/segments.json`

Summary: read-only reference structural segments with start, end, and human labels.

Why it matters: external structural guidance for validation.

LLM hint:
- See: segment boundaries and labels.
- Use: compare against `section_segmentation/sections.json` to sanity-check large structural changes.
- Treat labels as advisory. The important part is the boundary timing.
- Use: derive offline boundary-quality metrics such as over-segmentation, under-segmentation, and snap-like late or early offsets.
- Optional promotion rule: if a Story explicitly allows it, this file may rescue low-confidence or clearly failed inferred section boundaries, but only through an explicit confidence gate with preserved inferred output and provenance.

### `data/analysis/<Song - Artist>/reference/moises/lyrics.json`

Summary: read-only word-level lyric timing with line ids and confidence values.

Why it matters: strongest text-based source for lyric-synced visual moments.

LLM hint:
- See: `text`, `start`, `end`, `line_id`, and markers like `<SOL>` and `<EOL>`.
- Use: align spotlight moments, text-reactive effects, or visual punctuation to words and line starts.
- Combine: with vocal symbolic data for melody-aware lyric moments.
- Use: derive beat- or line-aligned features such as lyric density, line starts, line ends, post-line tails, and confidence-weighted vocal-presence priors.
- Optional promotion rule: if a Story explicitly allows it, this file may rescue low-confidence vocal timing or event timing only when the overlapping stem or energy evidence agrees and the promotion is recorded explicitly.
- Debugger: shown as the read-only **Moises Lyrics** lane (directly under Human Hints), one block per token with the block tinted by each word's `confidence`.

## Practical Usage Patterns

### For fast show briefing

Open `data/analysis/<Song - Artist>/sections.json` first, then `data/analysis/<Song - Artist>/song_event_timeline.json`.

### For structured cue generation

Open `data/analysis/<Song - Artist>/artifacts/layer_c_energy.json` and `layer_d_patterns.json`.

### For harmonic color and scene-change logic

Open `layer_a_harmonic.json` and `essentia/beats.json`.

### For phrase and repetition callbacks

Open `layer_b_symbolic.json`.

### For rig-aware targeting

Open `data/fixtures/fixtures.json` and `data/fixtures/pois.json`.

### For trust and QA review

Open `validation/phase_1_report.md`, `validation/phase_1_report.json`, and then the matching reference files under `data/analysis/<Song - Artist>/reference/`.
