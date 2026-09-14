# Product refinement — v3.6

**Status: planned:** [`implementation-plan-v3.6.md`](implementation-plan-v3.6.md).

**Goal:** the MCP server lets the authoring model understand a song without
guessing or re-reading large JSON. The question every experiment answers: **for
each section, how fast and in what rhythm does the music move, and how much
energy and tension does it carry?** Everyone knows a drop runs slow→fast, fades
on the pre-drop and strobes on the downbeat. What's missing is *how fast*.
Experiments feed that answer as clue layers (item 6) unless they fail too far
(item 3). Items are sized for a Sonnet implementer.

---

## 1. Promote WhisperX VAD out of the experiment sandbox — `src/`, `ui/`

**Current behaviour.** `whisperx_vad` was promoted in name only (v3.5 item 7,
`docs/archive/experiments_promoted.md`): `arrangement_state.json` carries
`vocals_phrase`, but the compute step is still out-of-band. `experiments/whisperx_vad/run.py`
writes to `reference/proposals/whisperx_vad.json`; `src/analyzer/stages/ui_data.py`'s
`_whisperx_vocal_phrase` only reads that cache if present, emitting `null`
otherwise. The debugger's "WhisperX VAD" lane (`ui/src/timeline/laneState.ts`)
still carries `experiment: "whisperx_vad"` and reads the same
`reference/proposals/` file via `ui/src/data/paths.ts` / `loaders.ts` — flask
badge included, even though the experiment itself closed months ago.

**Change.** WhisperX VAD becomes a real pipeline stage, run as its own Docker
service rather than merged into `app`. WhisperX pins `torch~=2.8.0`; `app` is
pinned to `torch==2.1.2` (`cu118`) because Demucs and
`natten==0.15.1+torch210cu121` break on any torch bump
(`docs/reference/docker.md`, "Why the versions are pinned where they are"), so
bumping `app` itself would touch every torch-backed stage for one detector.
Instead: the existing `experiments/whisperx_vad/Dockerfile` image becomes a new
`ondemand` service `whisperx` in `docker-compose.yml`, unchanged torch pin,
writing `data/analysis/{song}/artifacts/whisperx-vad/*`. It runs as its own
step **before** `./analyze` (`docker compose run --rm whisperx --song …` /
`--all-songs`). The `app` container has no Docker socket and gets none: an
analyzer with host-root access is not worth one command saved. The `app`
stage that reads it **fails explicitly when the artifact is absent**, never
`null`, never a fallback to `reference/proposals/`. `app`'s pins stay untouched. The debugger lane reads that artifact path
instead of `reference/proposals/`, and `experiment: "whisperx_vad"` is removed
from `laneState.ts` along with the flask badge.

**Why it matters.** Every other artifact in `data/analysis/{song}/artifacts/`
is written by `./analyze` itself and carries `generated_from` provenance; a
lane reading `reference/proposals/` while claiming to be non-experimental
breaks that invariant and misleads whoever next audits the flask convention
(`ui/src/timeline/laneState.ts`'s own docstring: the field "leaves the registry
together when the experiment is promoted... or abandoned" — it didn't, in
2026-09-13's partial promotion).

**Out of scope.** The `vocals_phrase.confidence` hardcode to `1.0` — that is a
separate, already-settled operator decision (`docs/archive/experiments_promoted.md`),
not reopened by this item.

| | |
| --- | --- |
| Writes | `data/analysis/{song}/artifacts/whisperx-vad/*` (new); removes the `reference/proposals/whisperx_vad.json` read path |
| Reads changed | `ui/src/timeline/laneState.ts`, `laneContent.ts`, `ui/src/data/paths.ts`, `loaders.ts`, `types.ts`; `src/analyzer/stages/ui_data.py::_whisperx_vocal_phrase` |
| Done when | the lane carries no `experiment` field or flask badge, its data comes from `artifacts/whisperx-vad/`, and `docs/archive/experiments_promoted.md`'s WhisperX VAD entry is updated to say the compute step moved in-pipeline via its own Docker service |

---

## 2. One curated-truth scorer for every experiment — `experiments/truth_common/`

**Change.** Generalise `experiments/voiceness_common/scorer.py` into one scorer
per signal family, all reading `reference/human/` only. Every experiment in
item 3 scores through it, so verdicts are comparable.

**Corpus — checked 2026-09-14; no more marking is requested before item 3 runs.**

| family | truth | songs |
| --- | --- | --- |
| structure (boundaries ±1.0 s, labels) | `human/segments.json`, `docs/segments-vocabulary.md` terms | `ayuni` 16, `Cinderella` 20, `_test_song` 8, `What a Feeling` 9 |
| drop stages | hint titles `drop approach/build/tension/impact/release` (parse rule of `src/analyzer/stages/validation/drops.py`) | `Titanium` 3 drops, `Armin` 2, `Hideaway` 1, `_test_song` 1 |
| vocal presence, three-class | `type: "vocal"` + negative + residual hints (`docs/experiments.md` "Ground truth is three classes") | negatives: `ayuni`, `Cinderella`; positives only: `Armin`, `In da name of love`, `What a Feeling` |
| texture / character | untyped, non-drop hints | `Queen of Kings` 16, `ayuni` 11, `Cinderella` 8, `_test_song` 8 |
| energy, tension (1–5, exact and ±1) | `human/segments.json` (operator); `human/segments.seed.json` (seeds, **provisional**) | 2 operator rows; seeds on the 4 segment songs (item 6), all 23 after item 7 |
| rhythm (per-source subdivision, exact match) | `human/segments.seed.json` (seeds, **provisional**) | seeds on the 4 segment songs (item 6), all 23 after item 7 |
| vocal rhythm (word onsets as the syllable proxy; text ignored) | trusted lyric timings only | `Queen of Kings` — `human/lyrics.json`, 257 words / 37 lines, 1.0–142.9 s (whole song; supersedes the Moises 0–127.2 s trust window); `_test_song` — `moises/lyrics.json`, 24 words / 5 lines, all `"0.99"` |

**Circularity rules** — breaking these produces a number that measures the truth, not the detector:

- On the 4 segment songs `ui_data` rebuilds `sections.json` *from* `human/segments.json`. Score producers (allin1 artifact, experiment output), never the published `sections.json`.
- `Cinderella`: 15 of 22 vocal positives were captured from the whisperX lane. Report only `false_vocal_rate` for whisperX-derived detectors there.
- Positives-only songs: false-positive columns are upper bounds; never average them into a corpus mean.
- Untitled hints (`Hint 13`, `Hint 18`) are excluded.

| | |
| --- | --- |
| Writes | `experiments/truth_common/`; each experiment's `out/score.txt` — one row per truth song, one corpus row, same columns per family |
| Done when | `voiceness_common` is folded into it (no second scorer left) and each family has a unit test on a hand-built fixture |

---

## 3. Verdict per open experiment

**Change.** Rescore each entry through item 2. **Default verdict: keep it as a
clue layer** feeding item 6, named by the file it lands in (reach test). Beating
the incumbent is not required. Two exits:

- **Fails too far → archive** (TLDR into `docs/archive/experiments_discarded.md`,
  lane retired): no better than its family's trivial baseline (always-on for
  presence, evenly spaced grid at the same boundary budget for structure, the
  song-wide constant for energy/tension/rhythm) on the truth songs, or
  contradicted by truth on most of them.
- **Noise → merge or drop**: a layer that repeats another layer's answer on the
  truth songs adds tokens, not clues. Keep the better-scoring one.

Promotion into `src/` is still asked per experiment. Per-song results are read
before any archive call: a corpus-row loss with a unique win on one song is
reported, not killed.

| experiment | family | incumbent | would land in |
| --- | --- | --- | --- |
| allin1 label posterior (never run) | structure | `segmentation.py` argmax | `sections.json` |
| SongFormer (never run) | structure | `segmentation.py` | `sections.json` |
| Phrase Periodicity | structure, texture | none — no periodicity signal exists | `sections.json` |
| Texture Novelty (CLOSED, kept for review) | structure, texture | `segmentation.py` | `sections.json` |
| Structural vs Micro (CLOSED, kept for review) | structure | `segmentation.py` | `sections.json` |
| CLAP character | texture | none | `sections.json` |
| Vocal phrase blocks | vocal presence (edges) | `vocals_phrase` (whisperX) | `arrangement_state.json` |
| Vocal voiceness — vibrato, portamento | vocal presence | whisperX | `arrangement_state.json` |
| SVD Tagger | vocal presence | whisperX | `arrangement_state.json` |
| Voice Multiplicity | vocal (solo/stacked) | none | `arrangement_state.json` |
| Drop Proposals (`drop_detection`, no queue entry) | drop stages | `gestures.py` | `song_event_timeline.json` |
| Demucs ablation (3 of 5 songs) | vocal presence, drop stages | `htdemucs` | every stem-derived file |
| ACE-Step Transcriber | vocal rhythm; vocal presence | `whisper_baseline.py` word onsets (rhythm), whisperX (presence) | `arrangement_state.json` (`vocals_phrase` edges + per-phrase onset timing) |

**Vocal phrases exist to give the model a song segment's rhythm, not its
words.** Lyrics are never a deliverable, and karaoke-grade text is worthless:
the scored quantity is *when* syllables land. A detector with wrong words and
right onsets passes; right words with late onsets fails. WER is not a verdict
metric. Text is only an alignment aid.

ACE-Step runs on three songs: `Queen of Kings` and `_test_song` (trusted word
timings: onset F1 at ±50 ms and ±100 ms, onsets per second per phrase, phrase
edges) and `Cinderella - Ella Lee` (no lyrics reference: phrase spans scored
three-class against its 22 vocal / 5 negative hints). The `Cinderella`
circularity rule does not apply: its positives came from the whisperX lane, and
ACE-Step's timing comes from `align.py`'s whisper baseline. ACE-Step emits no
seconds of its own, so its onset score **is** the aligner's score. If the
whisper baseline alone matches it, ACE-Step adds nothing to rhythm.

Texture Novelty and Structural vs Micro: this rescore **is** their "one operator
review pass". Drop Proposals: the rescore settles the orphan loose end — retire
the lane if `gestures.py` matches or beats it.

| | |
| --- | --- |
| Writes | each entry's `### Status` in `docs/experiments.md` (verdict + deciding number); archive TLDRs |
| Done when | every entry in `docs/experiments.md` has a verdict scored against your own references |

---

## 4. Delete what nothing reads

- `reference/proposals/` files with no reader: `clap_voiceness.json` (23 songs),
  `reactive_bands.json` (4), `grid.json` + `gestures.json` (4; read only by the
  archived `grid_consensus`), `proposals/arrangement_state.json` (4; promoted to
  top level — confirm no reader first).
- Lanes of every experiment archived in item 3, via Recipe B
  (`docs/reference/ui-development.md`).
- Doc drift: `docs/analysis-definition.md` lists 3 songs with
  `human/segments.json` — 4 (`Cinderella`); `docs/experiments.md` "Vocal ground
  truth inventory" and "Loose ends → no non-drop ground truth" rewritten to the
  item-2 corpus table.

| | |
| --- | --- |
| Done when | every `reference/proposals/*.json` has a reader, and every flask lane maps to an open entry |

---

## 5. Top-level files carry only what the authoring model uses — no backwards compatibility

**Change.** Each top-level file is cut to the fields `mcp/serializers.py` reads
and authoring needs. Anything else moves to (or stays in) `artifacts/`, where the
debugger reads it. Schema versions bump; no shim, no optional-file branch — the
corpus is re-run.

Field audit, 2026-09-14 (MCP reads vs. published, 23 songs):

| file | drop | why |
| --- | --- | --- |
| `sections.json` | `label`, `description`, `chord_progression` | `label` is a display string with confidence folded in (`"003 Build [unverified] (0.45)"`) — breaks the confidence rule; `description` restates `function` + ordinal (`"The 1st chorus…"`); `chord_progression` is unread (85 rows) |
| `beats.json` | `chord` | unread; chord labels are "informative, not settled". `time`/`type`/`bar`/`beat`/`downbeat_confidence` stay — they now reach the model via `get_detail` |
| `song_event_timeline.json` | `section_name`, `summary`, `evidence_summary`, `provenance`, `generated_from` | unread; `section_name` duplicates the `section_id` join |
| `hints.json` | `sections[]` wrapper, `id`, `category`, `summary`, `generated_from`, every `source: "inference"` row | wrapper duplicates `sections.json`; inference rows (1-2 per song) are cue-authoring prose ("Treat 30.00s as the main cue reset…") — out of scope — with dead `anchor_refs` to removed stages. Result: flat `hints[]`, human only, `source` stated once |
| `genre.json` | `top_predictions`, `guidance` | `top_predictions` unread; `guidance` is one identical text across all 23 songs — stated once in the tool description instead |
| `drum_events.json` | per-event `confidence` | `null` on all 32,213 events; one file-level `confidence: null` with its reason |
| `loudness.json` | `sources[]`, `metadata.sample_rate/duration/total_frames/normalization_scope` | unread; keep `interval_ms`, `source_order`, `frames[].time/values/normalized_values` |
| `info.json`, `arrangement_state.json` | — | fully read |

**Provenance at top level is `field_sources` only.** No top-level file carries
`generated_from`; it stays in `artifacts/`. The MCP client never reads it, and a
short, complete schema is the point. `field_sources` lists only surviving fields.

**Beats reach the model.** `get_detail`'s structural view gains a `beats` block:
every beat inside the resolved span — `time`, `bar`, `beat`,
`downbeat_confidence` — undecimated and present past the 5 s dense cap, like the
other structural rows. Today no beat time ever leaves the server.

**Backwards compatibility removed.** `mcp/loaders.py` `REQUIRED_TOP_LEVEL_FILES`
becomes all 9 files; `serializers._maybe_load`, the "song analysed before v3.2"
unavailable block and the `function_status` default are deleted.

| | |
| --- | --- |
| Writes | publish code for each file under `src/analyzer/stages/`; `mcp/serializers.py`, `mcp/loaders.py`, `mcp/tests/__snapshots__/`, `mcp/tests/fixtures/`; UI parsers that read dropped fields from top-level (`ui/src/data/parsers.ts`: `chord`, `chord_progression`, `section_name`, `evidence_summary`, `provenance`) move to the artifact source |
| Docs | `docs/reference/downstream-contract.md` file-by-file, `docs/mcp-definition.md` (`get_detail` beats block), `docs/reference/artifacts.md`; `CLAUDE.md` "Provenance" rule reworded (`generated_from` in `artifacts/`, `field_sources` at top level); `docs/issues.md` "host paths" entry deleted |
| Done when | every published field is read by `mcp/serializers.py`; `mcp/tests/run.py full-regression` green on the re-run corpus; `get_song_overview` on `Titanium` measured against the 6 KB target (`docs/issues.md`) |

---

## 6. Rhythm, energy and tension per section — `sections.json`

**Change.** Every `sections.json` row gains three clue fields. Each has its own
`confidence`, `null` when no producer clears its floor, and its winner recorded
in `field_sources` (fused per field, highest confidence wins):

| field | shape | candidate producers (each its own experiment + lane) |
| --- | --- | --- |
| `energy` | 1–5, the operator's segment rating scale | `loudness.json` level, `arrangement_state` stem count, CLAP calm↔intense |
| `tension` | 1–5 | gesture build phases, Texture Novelty, Phrase Periodicity regime |
| `rhythm` | per source (`drums`, `bass`, `vocals`, `harmonic`): dominant `subdivision` relative to the beat grid (`half`, `quarter`, `eighth`, `sixteenth`, `eighth_triplet`, `none`) + `onsets_per_beat` | **(a)** drum-event inter-onset intervals against `beats.json`; **(b)** sub-beat autocorrelation of per-stem 20 ms loudness (Phrase Periodicity taken below the bar); **(c)** vocal syllable onsets (item 3's ACE-Step / whisper) |

This publishes musical facts, not light instructions. "Drop: drums go
`quarter` → `sixteenth` across the build, `none` on the pre-drop, `quarter` kick
at energy 5" is in scope. "Strobe at 12 Hz" is the authoring model's call. MCP:
the three fields ride on the existing section rows in `get_song_overview`, with no
new tool.

**Seeds first; the operator reviews in the next refinement.** Nothing waits on
hand-marking. The implementer infers `energy`, `tension` and `rhythm` for every
row of the 4 segment songs (`ayuni`, `Cinderella`, `_test_song`,
`What a Feeling`; 53 segments) and writes them into
`reference/human/segments.seed.json`, with the same spans as that song's
`segments.json`. `segments.json` holds operator values only, so the 2 existing
ratings (`Cinderella` Intro, `_test_song` Refrain) stay untouched. The seed
method is fixed, not tuned:

| field | seed rule |
| --- | --- |
| `energy` | segment mean of `loudness.json` mix `normalized_values`, plus `arrangement_state` stems playing; song-relative quintiles → 1–5 |
| `tension` | `energy` slope across the segment (rising = tense), +1 when a gesture `build`/`tension` phase overlaps, clamped 1–5 |
| `rhythm.drums` | dominant `drum_events.json` inter-onset interval ÷ beat period → nearest of ½, ¼, ⅛, 1⁄16, ⅓ (`eighth_triplet`); `none` below 1 onset per bar |
| `rhythm.bass/harmonic/vocals` | strongest sub-beat autocorrelation peak of that stem's 20 ms loudness at the same fractions; `vocals` is `none` where no `vocals_phrase` overlaps |

The seeds share method with candidate producers (a) and (b), so until the
operator reviews them: **scores against seeds are reported as provisional, and
no `energy`/`tension`/`rhythm` producer may be archived**. Every producer
publishes as a clue layer meanwhile.

**Unreviewed seeds reach MCP with a warning.** Per field, per section, publish
takes the first that exists:

1. the operator's value in `segments.json`: source `human`;
2. the highest-confidence item-6 producer that clears its floor: that producer;
3. the seed in `segments.seed.json`: source `seed_unreviewed`, `confidence: null`.

A `seed_unreviewed` field is recorded as a per-row `field_sources` override.
`get_song_overview`'s sections block then carries one `review_warning`, naming
the affected `section_id`s: *"energy/tension/rhythm sourced `seed_unreviewed`
are inferred, not yet reviewed by the operator; verify on the final show."*
Seeds never supply boundaries or labels. Reviewing means saving in the segment
editor, which moves the value into `segments.json`, and the warning goes away
on the next publish.

`rhythm` is a new optional field on segment rows: per source (`drums`, `bass`,
`vocals`, `harmonic`), one `subdivision` from the vocabulary above. The segment
editor gets one dropdown per source, so the review is a click, and an unmarked
source is omitted, never defaulted. Per source is deliberate: a half-time vocal
over sixteenth hats is exactly the layering lights need.

| | |
| --- | --- |
| Writes | first the 4 songs' `reference/human/segments.seed.json`; `mcp/serializers.py` `review_warning`; `ui/`: seed values shown as unsaved drafts in the segment editor, per-source `rhythm` dropdowns in `ui/src/panel/SegmentEditorPanel.tsx`, saved by `ui/src/data/saveHumanSections.ts`; then `sections.json` (schema bump, alongside item 5); one experiment per candidate producer, each with a lane |
| Done when | the three fields are published on the corpus with confidence and `field_sources`, and each producer has an item-3 verdict |

---

## 7. Seed the whole corpus — last item of the plan

**Change.** After every other item is closed, item 6's seed rule runs on **all
23 songs**. The operator reviews the results after the implementation closes,
not during it.

- **The 4 segment songs**: already seeded in item 6. Re-run only if an item
  changed an input (`loudness.json`, `drum_events.json`, `vocals_phrase`).
- **The other 19**: write `reference/human/segments.seed.json` over the current
  `sections.json` spans. **No `segments.json` is created**: `ui_data` rebuilds
  `sections.json` boundaries from `segments.json` at confidence 0.8, and allin1's
  unreviewed boundaries must not be dressed as human truth. The segment editor
  loads the seed when no `segments.json` exists, and **Save writes
  `segments.json`**. Saving is the review.

Then the corpus is re-published. Seeds reach MCP through item 6's precedence,
flagged `seed_unreviewed`, with the `review_warning`. Item 2 scores against
seeds only as provisional.

| | |
| --- | --- |
| Writes | 19 × `reference/human/segments.seed.json`; segment editor load fallback (`ui/src/data/paths.ts`, `SegmentEditorPanel.tsx`); corpus re-publish |
| Done when | all 23 songs carry seeds; on the 19, `sections.json` boundaries are unchanged; every published `seed_unreviewed` field has a matching `review_warning` in `get_song_overview` |

---

## Bugs

### Open

- **`hints.json` is stale against the operator's ground truth.** Human hints
  published vs. authored, 2026-09-14: `Cinderella` 0 of 30, `In da name of
  love` 0 of 11, `ayuni` 12 of 18, `_test_song` 15 of 13. Every `hints.json` is
  from 09-12, before the 09-14 re-marks. `lighting_hint` is *not* dropped:
  `hints.py` carries every non-empty one, and only 9 authored hints have one
  (`Armin` 1, `_test_song` 8). Fix: re-publish the 9 hint songs (`--stage
  generate-section-hints` onward), then add a test that a hint saved in
  `human_hints.json` appears in `hints.json` after that stage. Addressed first in
  the plan, so every later item reads current truth.
