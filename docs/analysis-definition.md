# Analysis definition — the pipeline, and how good each part is

The **what** and the **how honest**. Every stage, which phase it belongs to, and
what it measures against ground truth. Read this before trusting any output.

- Why the system exists: [`product-definition.md`](product-definition.md)
- Rules you must not break: [`../CLAUDE.md`](../CLAUDE.md) "Rules that are load-bearing"
- What reaches the authoring model: [`mcp-definition.md`](mcp-definition.md)
- Exact fields and paths: [`reference/artifacts.md`](reference/artifacts.md)

> `STAGE_PIPELINE_IDS` in [`../src/analyzer/pipeline.py`](../src/analyzer/pipeline.py)
> is the **authoritative** stage list, ahead of any prose here. Each stage's
> module docstring carries its own measured numbers and caveats.

---

## The four phases

The split is not organisational tidiness. It puts a line in the codebase past
which everything is a claim that can be wrong, which is what makes the honesty
rules enforceable.

The test for the 1/2 line is **not** DSP vs. ML — stems, beat tracking and
transcription all use trained models, and excluding them would leave phase 1
empty. The test is: **does this stage assert something that could be musically
wrong?** A loudness curve cannot be wrong; it is a measurement. A chord label
can. A section name can.

Four rules govern the phases:

1. **Phase 1 carries no `confidence` field**, because there is nothing to be
   uncertain about. From phase 2 onward, confidence and provenance are mandatory.
2. **Phase 3 is defined by its input, not its determinism.** Chord-pattern
   mining is deterministic arithmetic and still belongs in phase 3. The rule is
   structural: phase 3 reads earlier phases' output — phase 2's claims, and
   phase-1 series such as `loudness.json` — and **never opens the audio**.
   That is what makes it the layer where the show gets its shape — which
   sections are the same one returning, that a transition is `chorus → inst`,
   that a **drop is derived from a named section pair rather than detected**.
   Inferring a composite gesture straight from raw features, without named
   structure to hang it on, is the mistake this phase exists to prevent.
3. **Feedback is allowed; mutation is not.** Phase 3 may improve on phase 2 —
   snapping a boundary to a phrase grid it derived — but it writes a *new*
   artifact with provenance. It never edits phase 2's output in place. Once a
   later phase can silently overwrite an earlier one, it stops being possible to
   say which stage was wrong.
4. **Phase 4 publishes everything that ships, and nothing else.** A signal that
   reaches no top-level file did not ship, whatever earlier phases computed.
   Phase 4 is also the only writer of the delivery surface: MCP-exposed JSON
   lives exclusively at `data/analysis/{song}/*.json`, and `artifacts/`
   is readable only by the analyzer and the debugger UI.

## Phase 4 fuses; it does not copy

A published file is **not** a projection of one artifact. It is assembled from
whichever producers are most trustworthy for each field, and **which producer
wins can differ per song and per row.** Publishing is therefore a decision, and
like every decision in this pipeline it has to be recorded.

**Every published value carries a `source`.** The value alone is not enough,
because the reader cannot otherwise tell whether a number came from the trusted
beat tracker or from a model measuring 0.226 F1.

This is already true and currently unrecorded. One `beats.json` row fuses three
producers:

| Field | Producer | Trust |
| --- | --- | --- |
| `time` | essentia `RhythmExtractor2013` | trusted — 7/7 impacts within 0.25 s |
| `type`, `bar`, `beat` | allin1 downbeat activation | 0.226 F1, short of target |
| `chord` | HPCP chord decoding | 1.00–0.38 agreement by song |

and its single `confidence` describes **only the downbeat phase**, not the beat
time — so the row reads as though a trusted field carried a weak confidence. A
`sections.json` row likewise fuses allin1's boundaries and labels with the
harmonic stage's `key` and `chord_progression`, gated on a different producer's
confidence than the row's own `confidence` field.

`hints.json` is the one file that already gets this right: every hint carries
`source: "human" | "inference"`. That is the pattern to generalise.

The rules that follow from it:

- **A confidence is attached to the thing it measures**, never to a row
  generically. A row fusing two producers needs two named confidences, or
  per-field attribution.
- **Attribution is declared cheaply** — the default producer per field once at
  file level, with a per-row override only where a row actually took a different
  producer. Repeating an identical source map on every one of 500 beat rows is
  pure token cost.
- **Fusion draws only from generated artifacts.** It never reads `reference/`,
  which stays validation-only.
- **If no producer clears its floor, the answer is `unknown` or `null` with the
  reason** — never the least-bad guess.

Re-filing existing stages is not the point and is not worth doing on its own.
The phases are the shape a *rewrite* takes: replacement structural inference
lands as phase 2, identity and transitions as phase 3, and code belonging to
neither is deleted rather than relocated.

### Phase 1 — measure (audio in; facts that cannot be musically wrong)

| Module | Produces |
| --- | --- |
| `stems.py` | Demucs separation → `artifacts/stems/{bass,drums,harmonic,vocals}.wav`, seeded |
| `timing.py` | `artifacts/essentia/beats.json` — essentia beat *times* plus allin1-derived downbeat *phase* |
| `fft_bands.py` | `artifacts/essentia/fft_bands.json` — 7 fixed bands every 50 ms |
| `loudness.py` | `artifacts/essentia/rms_loudness.json` (10 ms) and `loudness_envelope.json` (200 ms), per source |

No `confidence` field anywhere in phase 1 — there is nothing to be uncertain about.

### Phase 2 — interpret (phase 1 + audio; claims that can be wrong)

| Module | Produces |
| --- | --- |
| `harmonic.py` | `artifacts/essentia/hpcp.json`, `artifacts/layer_a_harmonic.json` — HPCP, global key, chord events; also projects compact `key` / `chord_progression` into `sections.json` |
| `drums.py` | `artifacts/symbolic_transcription/drum_events.json` — Omnizart drum hits on the isolated drums stem; GM 35/38/42 only, plus a v3.4 `crash`/`hat` split on pitch 42 from the drums-stem brilliance band |
| `genre.py` | `artifacts/genre.json` — genre with honest confidences and `guidance` prose |
| `segmentation.py` | `artifacts/section_segmentation/sections.json` — All-In-One named functional segmentation |
| `energy.py` | `artifacts/layer_c_energy.json` — energy states, per-section cards, accent candidates |

Chroma extraction and chord decoding stay **two stages, not one** — fusing them
would make a chroma bug and a decoding bug indistinguishable in the artifact,
which is exactly the ambiguity that made past chord issues hard to attribute.

### Phase 3 — relate (phases 1-2, **never audio**)

| Module | Produces |
| --- | --- |
| `gestures.py` | `song_event_timeline.json` — gesture phases + section-pair transitions |
| `arrangement_state.py` | `artifacts/arrangement_state.json` — per-stem RMS state blocks: who is playing, and where that changes |
| `hint_alignment.py` | `find_primary_section`, the shared window→section matcher |

`arrangement_state.py` (`detect-arrangement-state`) reads the published
`loudness.json` — a phase-1 series, not audio — and asserts *who is playing* and
where a stem enters or leaves. It measures F1 0.59 @0.5 s / 0.75 @1.0 s on
`_test_song` against `sections.json`'s 0.00; corpus-wide it sits at the noise
floor of the labels (32 of 47 gold hints are drop stages `gestures.py` owns).
`confidence` is dB headroom at the stem flip (`margin_db`-derived), not a trained
score, and is `null` for the leading block that has no flip.

### Phase 4 — publish

| Module | Produces |
| --- | --- |
| `hints.py` | `hints.json` — inference hints merged with `reference/human/human_hints.json` |
| `ui_data.py` | `sections.json`, `beats.json`, `info.json`, `genre.json`, `drum_events.json`, `loudness.json` — the compact top-level deliverables, each fused from its producers with a `field_sources` header |

Together with `hints.py`'s `hints.json` and phase 3's `song_event_timeline.json`,
these are the eight top-level files the `mcp/` server reads. Nothing the delivery
surface needs still lives only under `artifacts/`.

### Validation — orthogonal to all four

`validation/{beats,chords,sections,drums,drops}.py` score generated artifacts
against `reference/`; `report.py` aggregates into
`artifacts/validation/phase_1_report.{json,md}`.

Validation and the human/reference loop **observe** every phase rather than
occupying a position in the sequence, and must not be interleaved as ordinary
stages — doing so is what previously scattered `validate-beats` and
`validate-chords` through the middle of extraction. Human corrections may enter
at any phase, subject to the promotion rules.

### Shared infrastructure

| Module | Role |
| --- | --- |
| `cli.py` | `./analyze` / `python -m analyzer` argument parsing |
| `pipeline.py` | the stage DAG; `STAGE_PIPELINE_IDS` is authoritative |
| `allin1_cache.py` | runs All-In-One **once per song**, seeded with the pipeline's own stems, cached to `artifacts/allin1/raw.json`. Both `timing.py` (downbeat phase) and `segmentation.py` read it |
| `paths.py` | `SongPaths` — all `/data/` path resolution |
| `models.py`, `io.py`, `config.py`, `exceptions.py` | schema version, disk I/O, CLI config, error types |
| `_omnizart_runtime.py` | subprocess isolation for Omnizart |

---

## What to trust

Measured against hand-labelled ground truth on the four gold songs
(`_test_song`, `Titanium - David Guetta ft Sia`, `Armin - Revolution`,
`Hideaway - Kiesza`; 7 human-marked drop impacts), plus `reference/moises/` — a
second model's *inference*, not ground truth, but 5–200× more evaluation signal.
Reproduction: [`../experiments/drop_detection/README.md`](../experiments/drop_detection/README.md).

### Trusted — deterministic DSP, ~1,950 lines

`stems.py`, the beat-*time* grid in `timing.py`, `fft_bands.py`, `loudness.py`,
`harmonic.py`, `drums.py`, `energy.py`. Byte-reproducible and independently
checked.

- **Beat tracking is good.** 7/7 human-marked impacts land within 0.25 s of an
  essentia beat. Beat times are essentia's throughout.
- **Chord labels are informative, not settled.** Root+quality agreement with
  Moises varies widely by song: **1.00 / 0.69 / 0.51 / 0.38** across the four
  gold songs. `sections.json`'s `chord_progression` is confidence-gated on
  exactly this uncertainty, and `null` there is honest, not a bug.
- **The drum vocabulary is bounded, and the bound is written down.** Omnizart
  emits three GM pitches only — 35 (kick), 38 (snare), 42 (hi-hat). `velocity`
  is a constant 100 and is **not published** (a zero-information column is worse
  than its absence). `confidence` is `null` — Omnizart exposes no per-hit score.
  Toms and congas are folded into kick or snare: a *known* wrong label, not a
  silent one. **v3.4 crash/hat split:** a pitch-42 event is relabelled
  `hat` → `crash` when the drums-stem 6–16 kHz brilliance band in
  `fft_bands.drums.json` shows a sustained wash (normalized level ≥ 0.90) *and*
  a strong broadband onset (`transient_strength` ≥ 0.40) within ±0.12 s of the
  event. Constants are measured, not per-song tuned (see `drums.py` docstring).
  Measured split: `Armin - Revolution` 10 / 656 (2%); `Queen of Kings -
  Alessandra` 43 / 476 (9%), with a `crash` 0.08 s from the operator-marked
  48.7 s drop; `_test_song` 35 / 179 (20%, synthetic). `Titanium` / `Hideaway`
  measurement-pending (no `fft_bands.drums.json` yet; Omnizart is CPU-only
  here). If `fft_bands.drums.json` is absent the stage fails (`DependencyError`)
  — there is no fallback to "everything is hat".
- **The vocal stem's RMS level is not a trustworthy voice-presence signal on
  every song, and the bound is written down.** `arrangement_state.json`'s
  `vocals` channel (and `fft_bands.vocals`/`loudness.json`'s per-stem RMS more
  generally) reads energy in Demucs's `vocals.wav`, which on most of this
  corpus tracks a sung voice well — but on `ayuni` the stem is largely leaked
  flute, and the rule reports `vocals` present for **40.8 % of the song
  (67.2 s of 164.8 s)**. **Self-normalisation is the mechanism, not a level
  problem**: the stem spans 34.7 dB from its own p50 to p98, and **39.0 %** of
  its 20 ms frames sit within 18 dB of p98 — exactly the presence rule's own
  threshold — so whatever is in the stem (voice or flute) gets stretched to
  full scale. `fft_bands._robust_normalize` (per-source 5th–95th percentile)
  and `loudness.json`'s `normalization_scope: per-song-per-source-peak-rms`
  apply the identical stretch and inherit the identical caveat; no cleaner
  level fixes it, and a flute is not noise a filter can remove without also
  removing vocal energy (implementation-plan-v3.5, product-refinement §review).
  **Not yet fixed in `src/`.** Four competing voiceness detectors
  (`experiments/vocal_voiceness`, `clap_voiceness`, `svd_tagger`,
  `whisperx_vad` — `docs/experiments.md`) were built and measured against a
  shared scorer. On the two songs carrying real `type: "vocal"` ground truth
  so far (`ayuni`, 4 spans; `Armin - Revolution`, 7 spans — the other three
  scoring-corpus songs carry none yet), `vocal_voiceness` and `whisperx_vad`
  both cut the false-vocal rate below the incumbent's (`ayuni`: 0.109 / 0.120
  vs 0.290; `Armin`: 0.051 / 0.120 vs 0.460), and `whisperx_vad` additionally
  wins boundary F1 by a wide margin (`ayuni` 0.583 vs the incumbent's 0.385).
  `clap_voiceness` does not beat the incumbent on either song.
  **`svd_tagger` is unmeasured** — its sandbox image never finished building
  in this environment (a checkpoint-fetch throughput issue, not a dead pin).
  This is two songs and eleven marked spans, not a corpus-wide result, and a
  gating fix into `src/` awaits the operator's by-ear review of the winning
  lane — see implementation-plan-v3.5.md item 8's `D8.1`.

### Structure — `segmentation.py`, a real improvement, not solved

Replaced `stages/sections/` (1,403 lines of deterministic-DSP phrase detection
plus an invented 13-value `section_character` vocabulary), which measured **0/7
within ±1.0 s** of hand-marked impacts and **0.29 F1** against 38 Moises segment
boundaries — worse than an evenly spaced grid at the same boundary budget.

| Against 38 interior boundaries, ±1.0 s | recall | precision | F1 |
| --- | --- | --- | --- |
| `segmentation.py` (allin1) | **0.53** | **0.91** | **0.67** |
| old `sections/` segmenter | 0.32 | 0.27 | 0.29 |

Honest caveats that ship with it:

- `function_status: "unknown"` is set on **every row** of a song where allin1's
  own labelling is degenerate (fewer than 3 distinct labels, or one label over
  90% of the track). The boundary stays usable; the name does not.
- `function_confidence` is `1 −` normalised Shannon entropy of allin1's
  frame-level label posterior over the section's span — how sure the *model* was.
- `same_label_as` means **label repetition** — "the third thing allin1 called a
  chorus" — never verified acoustic identity. See "Known gaps".
- Boundaries are quantised to **8 bars**. At `_test_song`'s ~1.85 s/bar that is
  a 14.8 s floor, so nothing shorter can be expressed however clearly it is
  audible. This is the origin of the intra-section gap below, and it is a
  property of allin1's output, not a tuning choice.
- allin1's `chorus` prior can invert against energy. The phase-3
  `contest-section-function` stage (`section_function.py`) cross-checks each
  `function` against the published `loudness.json` + `arrangement_state.json`
  and, where a `chorus` is quieter and thinner than the `verse` / `bridge` that
  follows, **keeps the label and flags it** `function_status: "contested"` +
  `contested_by: "energy"` in `sections.json` — it never flips (refinement
  `D5`). Measured across all 23 analysed songs
  (`experiments/section_function_contest/measurement.md`): the contradiction is
  **not corpus-wide** — 4 sections across 2 songs (`Queen of Kings` ×3, `It's a
  fine day - Opus III` ×1), the other 21 flag nothing. So the rule ships
  conservative (next-section drums ≥ 3 dB louder, mix not > 1.5 dB quieter,
  arrangement_state stem count not clearly thinner, allin1
  `function_confidence` ≤ 0.9). On a normal song `sections.json` is
  byte-identical to before.

**v3.5 item 10 — `reference/human/segments.json` and the vocabulary switch.**
A new optional, gold-song-only reference file (`_test_song`, `ayuni`, `"What
a Feeling - Courtney Storm"` carry it today): a flat `[{start, end, label}]`
list. Where it exists for a song, `ui_data.build_ui_data` rebuilds
`sections.json` from its spans outright — boundaries/label/description/
confidence (fixed `0.8`) come from it; `function_confidence`/
`function_status`/`same_label_as` are still inherited from whichever allin1
section overlaps most, never invented. Scored separately in the phase-1
report (`human_segments`, same recall/precision/F1 method as the `moises`
comparison above, advisory). Also switches the `function` vocabulary itself,
for every song regardless of whether it carries this file: allin1's Harmonix
set (`intro outro break bridge inst solo verse chorus`) is mapped onto
`docs/segments-vocabulary.md` terms by `section_vocabulary.py` before
`function` leaves `segmentation.py` — `same_label_as` identity is still keyed
on allin1's raw token, computed before that mapping.

### Downbeats — honest, and short of target

The old `beat_in_bar` was pure modulo: there was no downbeat *detection* at all,
and it scored **0.16 F1 @±70 ms** against 385 Moises downbeats.
`timing.py` now derives the downbeat *phase* (never the beat times) from
allin1's `downbeat` frame activation, by majority vote of local arg-maxes in
16-bar windows — a single song-wide offset was tried first and scored worse than
the modulo baseline.

**Combined F1 is 0.226 — short of the 0.50 target.** Stating that plainly
matters more than rounding up:

| Song | F1 | Why |
| --- | --- | --- |
| `_test_song` | 0.604 | clears target |
| `Armin - Revolution` | 0.593 | clears target |
| `Titanium - David Guetta ft Sia` | 0.000 | allin1's activation confidently peaks (0.24–0.47) where the reference calls beat 3 and sits near zero (~0.001–0.02) at the true downbeat — a reproducible ~2-beat disagreement. Its *beat* grid was independently confirmed aligned to ~10 ms first, so this is not an indexing bug |
| `Hideaway - Kiesza` | 0.050 | essentia's beat *tracker* — untouched by this work — finds ~0.66 s intervals against the reference's ~0.48 s. The one gold song where essentia trails Moises. No phase choice on a wrong-tempo grid can land within ±70 ms |

Neither failure is fixable without fabricating a downbeat allin1 does not
support (forbidden — never invent a plausible default) or reworking essentia's beat tracker.

**Bar numbers are therefore not to be assumed correct.** A `null` confidence is
the honest "we don't know", not a snapped guess — `validate_beats` excludes
`null` rows from the predicted set entirely, because an abstention is not a claim.

### Gestures — `gestures.py`, better than what it replaced

Replaced the ~3,800-line Epic-5 `event_*` chain, which measured **0/7 @±0.25 s
and 2/7 @±1.0 s** — largely on the strength of `layer_add`/`layer_remove`, a
per-beat energy delta with one of three template sentences attached, and 52% of
every event it ever emitted.

| @±1.0 s | @±0.25 s | |
| --- | --- | --- |
| **4/7** | **2/7** | `gestures.py` |
| 2/7 | 0/7 | old `event_*` stack |

It reads only trusted phase-1/2 artifacts and assembles named primitives
(riser, downlifter, reverse cymbal, snare roll, pre-drop gap, impact) into
phases `approach → build → tension → impact → release` anchored on a detected
impact. A phase absent from a gesture means **no supporting primitive was
found** — never guessed. **A drop is never named directly**; naming stays with
the section-pair transition.

---

## Known gaps

### Identity — the largest remaining gap

No section identity reaches the authoring model. `same_label_as` is label
repetition, not acoustic identity. [`../experiments/clap/README.md`](../experiments/clap/README.md)
tried CLAP embeddings and **lost to 20 MFCC coefficients** (mean pair AUC 0.68
vs 0.73). The useful finding: CLAP scores 0.83 at telling a section from
*itself* but 0.68 at matching two occurrences of the same part — so identity
needs a representation trained for **invariance between occurrences**, not a
bigger general-purpose embedding. **MFCC 0.73 is the number any next attempt
must beat.** Archived as concluded; a follow-on is queued in
[`experiments.md`](experiments.md).

### Nothing describes what happens *inside* a section

Distinct from the identity gap above, and the one an operator hits first. On
`_test_song` the entire delivery surface says this about 43 of its 58 seconds:

```
section-002   14.82 → 58.05   "chorus [unverified]"   confidence 0.446
```

One row covering a vocal approach, a drop, a high-energy region, a spacer and
the whole outro — regions the operator distinguishes at a glance from the
debugger's per-stem RMS lane, and has hand-marked as fifteen separate hints.

The cause is structural, not acoustic, and it is worth stating precisely because
the instinct is to blame the model that reads the output:

| producer | reads | therefore cannot see |
| --- | --- | --- |
| `segmentation.py` | mix spectrogram, argmax over 10 labels, 8-bar quantised | any change shorter than ~15 s on a mid-tempo track |
| `harmonic.py` | HPCP | anything that is not pitch — the chord is `D#m` on both sides of every boundary above |
| `gestures.py` | mix FFT + drum onsets | a *state*; it emits build/impact/release events, never "who is playing now" |
| `loudness.py` | per-stem RMS ✅ | — it publishes the series and draws no conclusion from it |

**The signal is already on the delivery surface as numbers.** This was a
plumbing gap, not a perception one, and v3.2 closed it for the arrangement axis:
`arrangement_state.py` (`detect-arrangement-state`, phase 3) turns the published
`loudness.json` into per-stem state blocks and publishes them as top-level
`arrangement_state.json`. It recovers 9 of `_test_song`'s 15 hand-marked
boundaries to a **median 0.07 s** (F1 0.59 @±0.5 s, where `sections.json` scores
0.00), with no model and no audio read, and finds the Armin `Breath` block at
83.00–95.50 against 81.39–96.33 hand-marked — tighter on both edges than the
CLAP forward pass. Full measured record:
[`archive/experiments_promoted.md`](archive/experiments_promoted.md).

Three findings from that work that generalise beyond it:

- **Smoothing a presence signal before thresholding destroys the boundary.**
  F1 0.59 → 0.27 with ±1 s smoothing, and a hand-marked boundary displaced by
  6 s. Detect fine, gate on persistence, and report the unsmoothed edge — this
  is "the physical onset wins over the nearest grid position" as a measurement.
- **These boundaries are a family, not one detector.** `_test_song`'s fifteen
  hints split into arrangement-state changes, gesture internals (`gestures.py`),
  vocal-phrase splits (the vocal-phrase experiment) and one fade. Together the
  four account for all fifteen; three already exist. No single stage should be
  expected to find them all.
- **The gold corpus cannot currently measure this.** 32 of its 47 hand-marked
  hints are the five stages of a drop; outside `_test_song` there are exactly
  two texture hints. Any texture detector scored corpus-wide is being scored
  against an absence of labels. **Mark texture blocks on the other three gold
  songs before tuning anything against this corpus.**

### Character blocks — measured, not shipped

The operator's hand-marked texture blocks (`Armin - Revolution` `hint-006`,
"Breath") are a deliverable no artifact carries. [`../experiments/clap/README.md`](../experiments/clap/README.md)
finds them from the stems plus one CLAP axis (calm vs intense), cutting the
detector's false territory from 73% of the corpus to 41% with no loss.

Two rules from that work: **ask CLAP how a passage *feels*, never what is
playing** — its drum and bass probes are confidently wrong where the stems are
exact. And allin1 contributes **shadow labels**: with `include_activations=True`
its frame-level posterior holds sustained mass on labels its own 8-bar
segmentation never used, which is how a breakdown inside an `inst` stretch
becomes visible. Not in `src/`; open in [`experiments.md`](experiments.md).

A third rule, added by the arrangement-state work above: **CLAP is not needed to
find the block at all.** The stems locate `Breath` more tightly than CLAP does.
What the calm/intense axis earns is *specificity* — cutting the detector's
claimed territory from 73% of the corpus to 41%. The two experiments want the
same contract change, a character/texture surface at top level, and should be
settled in one decision rather than each adding a file.

### Gesture precision has never been audited

Gestures are scored on impact *recall*. A phantom primitive — a riser or tension
span asserted where the music has none — moves that metric not at all, yet fires
a cue that contradicts the song. Tracked in [`issues.md`](issues.md).

---

## Deleted in v3.0 — do not reintroduce

~6,000 lines and ~20 MB/song of per-song artifact left `src/` in this release.
Recover any of it with `git log --diff-filter=D --name-only`.

| Removed | Why |
| --- | --- |
| The ML event stack (`event_ml.py`, training script, seeded models) | 0 events on 21 of 21 songs |
| `event_benchmark.py` | `status: "skipped"` on 21 of 21 songs; the annotation directory it scored against never existed |
| `unified.py` (`music_feature_layers.json`) | a re-packaging of files nothing downstream read |
| `patterns.py` | chord-pattern mining that reached no projected file |
| Symbolic note transcription (`symbolic/`, Basic Pitch, ~1,341 lines, 7.0 MB/song) | its only route to the model was a templated `motif_recall` hint sentence, itself deleted. `drums.py` and its Omnizart path are unaffected. **`artifacts/layer_b_symbolic.json` on ~17 pre-v3.0 analyses is a stale leftover with no current producer** — nothing reads it, and the four gold songs never had it because they were re-analysed after `58b9764` (2026-09-05). v3.4 confirmed it cannot be regenerated without resurrecting the deleted module, which is a promotion-gate decision left to the operator |
| The whole `event_*` stack (~3,800 lines) | measured at chance — see Gestures above |
| The old `stages/sections/` segmenter (1,403 lines) | measured at chance — see Structure above |
| The Moises takeover of the canonical grid | `run_phase_1` no longer substitutes `reference/`-derived beats or chords. `reference/` is validation-only |
| `validation/events.py`, `validation/energy.py`, the `form` target | no labels to score against |
| `light_design.py`, `lighting.py`, `beatdrop_visualizer.py` (~1,066 lines) | out of scope; removed 2026-09-02; the lighting-score stage had been throwing on every run with its failure swallowed by a bare `except` |
