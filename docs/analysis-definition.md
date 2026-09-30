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

and its single `confidence` describes **only the downbeat phase**, not the beat
time — so the row reads as though a trusted field carried a weak confidence. A
`sections.json` row likewise fuses allin1's boundaries and labels with the
harmonic stage's `key`, gated on a different producer's
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
| `harmonic.py` | `artifacts/essentia/hpcp.json`, `artifacts/layer_a_harmonic.json` — HPCP and the whole-song key; projects `key` into `sections.json`. Chord inference was removed — it failed on every song |
| `drums.py` | `artifacts/symbolic_transcription/drum_events.json` — Omnizart drum hits on the isolated drums stem; GM 35/38/42 only, plus a v3.4 `crash`/`hat` split on pitch 42 from the drums-stem brilliance band |
| `genre.py` | `artifacts/genre.json` — genre with honest confidences and `guidance` prose |
| `segmentation.py` | `artifacts/section_segmentation/sections.json` — All-In-One named functional segmentation |
| `energy.py` | `artifacts/layer_c_energy.json` — energy states, per-section cards, accent candidates |

### Phase 3 — relate (phases 1-2, **never audio**)

| Module | Produces |
| --- | --- |
| `gestures.py` | `song_event_timeline.json` — gesture phases + section-pair transitions |
| `arrangement_state.py` | `artifacts/arrangement_state.json` — per-stem RMS state blocks: who is playing, and where that changes |
| `hint_alignment.py` | `find_primary_section`, the shared window→section matcher |
| `section_clues.py` | fuses `energy`, `tension`, `rhythm` onto `sections.json` (v3.6 item 10) |

`arrangement_state.py` (`detect-arrangement-state`) reads the published
`loudness.json` — a phase-1 series, not audio — and asserts *who is playing* and
where a stem enters or leaves. It measures F1 0.59 @0.5 s / 0.75 @1.0 s on
`_test_song` against `sections.json`'s 0.00; corpus-wide it sits at the noise
floor of the labels (32 of 47 gold hints are drop stages `gestures.py` owns).
`confidence` is dB headroom at the stem flip (`margin_db`-derived), not a trained
score, and is `null` for the leading block that has no flip.

**`section_clues.py` (v3.6 item 10) — provisional, seed-only truth.** Fuses
`energy`/`energy_confidence`, `tension`/`tension_confidence` and `rhythm`
(per-source `subdivision`/`confidence`/`onsets_per_beat`) onto `sections.json`,
by precedence: the operator's `reference/human/segments.json` value, else the
highest-confidence of five ported candidate producers
(`energy_level`, `tension_shape`, `rhythm_drum_ioi`, `rhythm_stem_autocorr`,
`rhythm_vocal_onsets`), else `reference/human/segments.seed.json`
(`seed_unreviewed`, `confidence: null`), else absent. The five producers were
promoted from `experiments/` at their v3.6 item 5/6 evidence (corpus
exact-match against `segments.seed.json` — a **self-consistency check**, since
the seed shares each producer's own method, not independent validation):
`rhythm_drum_ioi` drums 0.6415 (34/53); `rhythm_stem_autocorr` bass 1.0000,
harmonic 1.0000, vocals 0.9811, drums 0.1698; `rhythm_vocal_onsets` vocals
0.0377 (2/53 — whisper-large-v3 over short spans yields sparse onsets);
`energy_level` energy 0.9811 seed / 0-of-2 exact but 1-of-2 within-1 against
the operator's own `segments.json` rows; `tension_shape` tension 0.7547 seed /
1-of-2 exact, 2-of-2 within-1 human. **Do not treat any energy/tension/rhythm
value as settled** until the operator has reviewed the seeds — full record:
`docs/archive/experiments.promoted.energy-tension-rhythm-clues.md`.
`rhythm_vocal_onsets`'s compute lives outside this stage, in
`whisperx_vad/vocal_onsets.py` (a second output of the `whisperx` service,
`artifacts/whisperx-vad/vocal_onsets.json`) — `section_clues` reads that file
and raises if the song has not been run through that service.

### Phase 4 — publish

| Module | Produces |
| --- | --- |
| `hints.py` | `hints.json` — inference hints merged with `reference/human/human_hints.json` |
| `ui_data.py` | `sections.json`, `beats.json`, `info.json`, `genre.json`, `drum_events.json`, `loudness.json`, `arrangement_state.json` (`publish_arrangement_state`, fusing phase-3's `artifacts/arrangement_state.json`) — the compact top-level deliverables, each fused from its producers with a `field_sources` header |
| `vocal_cadence.py` | `vocal_cadence.json` (v3.9 item 1) — per-line bar timing, per-section `lead_in_bars`/rests/held notes/cadence-repeats, calls, from `reference/human/lyrics.json` > `reference/moises/lyrics.json` (D1.1: neither → still written, `source: null`) plus the published `beats.json`/`sections.json`/`info.json`. Timing only |

Together with `hints.py`'s `hints.json` and phase 3's `song_event_timeline.json`,
these are the ten top-level files the `mcp/` server reads. Nothing the delivery
surface needs still lives only under `artifacts/`.

### Validation — orthogonal to all four

`validation/{beats,sections,drums,drops}.py` score generated artifacts
against `reference/`; `report.py` aggregates into
`artifacts/validation/phase_1_report.{json,md}`.

Validation and the human/reference loop **observe** every phase rather than
occupying a position in the sequence, and must not be interleaved as ordinary
stages — doing so is what previously scattered `validate-beats`
through the middle of extraction. Human corrections may enter
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
- **Beat-grid honesty (v3.9 item 3).** essentia's *times* stay trusted, but the
  tracker still loses the song's constant-tempo grid on pads-only or ambient
  stretches (e.g. *Rapture*'s Pre-Drop, ~167 BPM against the song's 129.84) or
  drifts before resyncing (*Rapture* before drop 2, ~0.485 s vs 0.462 s). A
  local-anchor fit (`ui_data._compute_off_grid_spans`) marks these as
  file-level `beats.json.off_grid_spans` — never rewrites a beat time (D3.1).
  Deliberately *not* one global regression against the beat's sequential
  index or one global phase: either accumulates ordinary ms-level jitter or a
  slightly-rounded BPM linearly over the whole song, flagging clean, unrelated
  stretches as off-grid (observed directly: an index-based fit flagged
  ~140 s of clean *Rapture* beats). Each beat is instead measured against its
  *nearest* stable neighbour, so error only ever accumulates over the short
  run between a beat and the closest known-good point. A span's `start`/`end`
  are the bounding STABLE beats either side of the unstable run, not the
  run's own first/last beat — every inter-beat interval touching the run is
  itself untrustworthy, including the one leading in and the one leading out
  (*Rapture*'s Pre-Drop span is 47.53–54.94, not the narrower 47.87–54.59: the
  IOI goes wrong exactly on the pair 47.53→47.87 and stays wrong through
  54.59→54.94). Corpus-wide (23 songs, 2026-09-28): 10/23 songs have zero
  spans; the rest range 1.6%–16.4% of duration except two long, genuinely
  different-tempo intros/outros — `_test_song` (35.3%) and `Underworld - Born
  Slippy` (27.5%, ~70 BPM half-time beats against a reported 140.09 BPM for
  the first 71 s) — both judged real tracker/song characteristics on
  inspection, not a fitting artifact.
- **Chord inference was removed.** Root+quality agreement with Moises was
  1.00 / 0.69 / 0.51 / 0.38 across the four gold songs, and the labels never
  helped find where a song repeats. The `key` estimate is a separate claim and
  stays, confidence-gated (`null` when weak).
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
  removing vocal energy.
  **Resolved, additive (2026-09-13): `blocks[].playing`'s `vocals`
  stays RMS-only; `vocals_phrase[]` is the channel to trust for voice
  presence.** Five voiceness detectors were built and scored on one
  three-class scorer (`docs/experiments.md`); `whisperx_vad` was promoted as
  the additive `vocals_phrase` field. Rescored 2026-09-13 on the full corpus
  rebuild, frame_acc / false_vocal on the only two songs that declare
  negatives:

  | detector | `ayuni` | `Cinderella - Ella Lee` |
  | --- | --- | --- |
  | incumbent RMS `arrangement_state` | 0.9042 / 0.0891 | **0.9342 / 0.0035** |
  | `whisperx_vad` (promoted) | **0.9881 / 0.0056** | 0.8614 / 0.0290 |
  | `vocal_voiceness` | 0.8708 / 0.0323 | 0.5480 / 0.0106 |
  | `svd_tagger` mix, per-song p98 rescale | 0.8538 / 0.0077 | 0.5125 / 0.0000 |

  `Cinderella` rescored 2026-09-13 against the repaired Cinderella class map
  (22 positive / 5 negative spans, was 4/4); ~15 of the 22 positives were
  captured from `whisperx_vad`'s own lane, so whisperX's recall there is
  circular — only `false_vocal_rate` (the second number) compares fairly.

  whisperX fixes the flute/guitar leak (`ayuni` residual firing 0.24 vs RMS
  0.82) and loses to RMS on rhythmic plucked-string leaks. No detector wins
  both songs, so the gate was tested — *gating* `playing`'s `vocals` on whisperX
  agreement instead of switching to it outright — `vocals` present only where
  RMS AND the detector rule both agree, published `blocks[]` scored
  frame-wise against the curated hints:

  | gate rule | `ayuni` frame_acc / false_vocal | `Cinderella` frame_acc / false_vocal |
  | --- | --- | --- |
  | additive (incumbent, shipped) | 0.9042 / 0.0891 | 0.9342 / 0.0035 |
  | G1: whisperX ≥0.2 AND stem ≥-38 dBFS | 0.9859 / 0.0074 | 0.9159 / 0.0013 |
  | G2: whisperX ≥0.2 AND sibilance ≥0.20 | 0.9766 / 0.0056 | 0.8361 / 0.0000 |

  Decision rule (fixed before measuring): a gate ships only if it lowers
  `false_vocal_rate` on both songs and costs no more than 0.01 `frame_acc` on
  either. Both gates lower `false_vocal_rate` on both songs but both cost more
  than 0.01 `frame_acc` on `Cinderella` (G1 −0.0183, G2 −0.0981) — neither
  ships. `playing`'s `vocals` remains an RMS-only claim, unchanged in `src/`;
  `vocals_phrase[]` (whisperX) is the field a consumer should read for voice
  presence.

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

**v3.5 — `reference/human/segments.json` and the vocabulary switch.**
A new optional, gold-song-only reference file (`_test_song`, `ayuni`, `"What
a Feeling - Courtney Storm"` and `"Cinderella - Ella Lee"` carry it today): a
flat `[{start, end, label}]` list. Where it exists for a song, `ui_data.build_ui_data` rebuilds
`sections.json` from its spans outright — boundaries/label/description/
confidence (fixed `0.8`) come from it; `function_confidence`/
`function_status` are still inherited from whichever allin1 section overlaps
most, never invented. Scored separately in the phase-1 report
(`human_segments`, same recall/precision/F1 method as the `moises` comparison
above, advisory). Also switches the `function` vocabulary itself, for every
song regardless of whether it carries this file: allin1's Harmonix set
(`intro outro break bridge inst solo verse chorus`) is mapped onto
`docs/segments-vocabulary.md` terms by `section_vocabulary.py` before
`function` leaves `segmentation.py`.

**v3.9 item 2 — `same_label_as` follows the winning `function` tier, not
always allin1.** Previously `same_label_as` was inherited from whichever
allin1 section overlapped most *even when* `function`/boundaries came from a
reference tier — so it pointed at unrelated allin1 sections (Rapture: Drop 2
→ the Breakdown). Now, whenever a reference tier (human/moises) wins
`function` for the song, `same_label_as` is computed from the *published*
label sequence itself — the first earlier published section with the same
normalized `function`, else `null` — and `field_sources` attributes it to
that tier. allin1 inheritance is kept only when `function` is allin1's (no
reference file for the song).

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
| **4/7** | **3/7** | `gestures.py` (v3.9 item 4) |
| 4/7 | 2/7 | `gestures.py` (pre-v3.9) |
| 2/7 | 0/7 | old `event_*` stack |

It reads only trusted phase-1/2 artifacts and assembles named primitives
(riser, downlifter, reverse cymbal, snare roll, pre-drop gap, impact) into
phases `approach → build → tension → impact → release` anchored on a detected
impact. A phase absent from a gesture means **no supporting primitive was
found** — never guessed. **A drop is never named directly**; naming stays with
the section-pair transition.

**v3.9 item 4 — impacts at the physical onset.** An impact's `start` is now
the onset (walked back from the transient peak while the transient stays
above its own threshold, capped at one beat so a preceding riser/roll can
never pull it into their own span); the peak is kept as `peak_time`. A
published section boundary where the bass and drums stems both enter within
one beat gets its own impact even with no supporting transient at all
(`detect_stem_entry_impacts`, `gestures.py`) — this is what raised @±0.25s
from 2/7 to 3/7 without dropping @±1.0s. On the 4 gold songs with hand-marked
drop impacts (`_test_song`, `Hideaway - Kiesza`, `Armin - Revolution`,
`Titanium - David Guetta ft Sia` — a different, smaller gold set than the
segmentation-review 4 above), `Armin - Revolution` and `_test_song` still
score 0: neither has a boundary-aligned, sustained bass+drums entry the
stem-entry detector's on/off-threshold hysteresis clears, and their transient
hits don't walk back far enough on their own. Verified beyond this gold set on
`Rapture - Nadia Ali` (both drops, 55.39s and 169.83s, previously 0/2 —
55.39s had no impact at all; 169.83s read 170.05s, 220ms late, now corrected
in place to 169.845s, `peak_time` keeping 170.05) and
`Queen of Kings - Alessandra` (48.70s, operator-reviewed, correctly stays
untouched — a naive "stems entered first" correction would have moved it to
48.555s, a bass-pickup-and-drum-fill hit ahead of the real downbeat; the
correction is guarded by shape, not strength: it only fires when the raw
drums value never dips to a real trough — below 60% of the onset's own value
— and climbs back up again between the stem onset and the existing impact. A
recovering trough means a separate, later hit exists in between (QoK dips to
~53% before recovering); a genuine attack envelope only eases off its own
early peak (Rapture never drops below ~98%). Two further guards keep an onset
from being attributed to the wrong boundary: it must fall within one bar of
the boundary it was searched from (QoK's 46.82s boundary, Fill → Pre-Drop,
independently rediscovered the same 48.555s pickup — 1.735s away, more than a
bar, and really belonging to the 48.72s Pre-Drop → Drop boundary 0.165s away
— so its own search is now rejected on distance alone), and a candidate is
never emitted as a new impact within the dedup floor of ANY existing impact,
not only ones near the boundary being processed (adjacent, bar-spaced
boundaries have overlapping search windows). Titanium's own onset (151.445s)
legitimately sits 0.985s — nearly 2 beats, about half a bar — past its
150.46s boundary, which is why the distance cap is a bar, not the pairing's
own one-beat tolerance; a literal one-beat cap would have silently dropped
it. Not closed by this item: `Cinderella - Ella Lee`'s 85.73s drop is a
drums-only entry (bass follows ~0.36s later, never crossing the stems'
shared on-threshold together) and `CruelSummer - Malvina` has no published
section boundaries at all (`sections.json` has zero rows — a pre-existing,
separate defect, not this item's to fix) — both are open follow-ups, not
regressions.

### Vocal cadence — `vocal_cadence.py`, 12/12 on Queen of Kings

v3.9 item 1, promoted from `experiments/vocal_cadence/`. Turns the operator's
own lyric alignment (`reference/human/lyrics.json` > `reference/moises/
lyrics.json`) plus the published `beats.json` into per-line bar-relative
timing, per-section `lead_in_bars`/rests/held notes/token density, and —
the load-bearing part — which earlier section a section's vocal cadence
repeats and at what bar offset. Timing only: the only text ever read from a
token is whether it is a `<SOL>`/`<EOL>` marker or fully parenthesised (a
call, e.g. `(hey)`).

**12/12 on the operator's own Queen of Kings facts** (the only song scored so
far — it is the one the spec names): `lead_in_bars` 0 / −1 / −1 on drop1 /
drop2 / final chorus; drop2 repeats drop1 at `bar_offset` −1 (0.897 match
fraction); the final chorus repeats drop2 at offset 0 (best) and drop1 at −1;
all 4 calls (99.62/107.21/131.87/139.62 s) exact. `lead_in_bars` is anchored
on which downbeat a line *resolves on*, not raw line-start distance — this is
what lets a short Fill/Pre-Drop section directly in front of a boundary still
count its cadence line as that boundary's lead-in (drop 2: the line starts at
94.88 s, before the Fill section even begins). Not yet a corpus metric — only
Queen of Kings carries the fact set to score against; a song with no lyrics
tier gets an honest `source: null` file (D1.1), never an inferred one.

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
| `harmonic.py` | HPCP (key only) | anything that is not pitch — the key is the same on both sides of every boundary above |
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
[`archive/experiments.promoted.arrangement-state.md`](archive/experiments.promoted.arrangement-state.md).

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
