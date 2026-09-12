# Product refinement — v3.5

**Status: open, nothing implemented.** A scoped worklist of concrete
refinements, collected item by item. Nothing here is done by writing it down.

**v3.5 is scoped to one question: does a voice actually sound here?** Reviewing
`ayuni` found the pipeline reporting a vocal for 40.8 % of a song whose vocal
stem is largely leaked flute, and found that the assumption behind that report
— energy in `vocals.wav` means a voice is singing — is hardcoded into three
stages and one experiment. Four competing detector lanes, one labelling surface,
one `src/` change and one ablation follow from that.

---

## The one change

**Voice presence stops being an energy reading on `vocals.wav` and becomes a
measured claim with its own confidence.**

Today nothing in the pipeline can tell a sung phrase from a flute that Demucs
put in the vocal stem. `arrangement_state.json` asserts `vocals` in its
`playing` list purely from stem RMS; `song_event_timeline.json` carries no
vocal event at all. This release adds a ground-truth surface, four competing
voiceness detectors measured against each other on one scorer, and — gated on a
winner — the `src/` change that makes the published claim honest.

### What the review established

All measured on `ayuni` this session, not asserted.

| | Finding |
| --- | --- |
| The published claim is wrong on this song | `arrangement_state.json` reports `vocals` present for **67.2 s of 164.8 s (40.8 %)** across 44 blocks. By ear the vocal occupies far less; the stem's energy is largely flute and indistinct bleed. |
| The stem is not quiet — self-normalisation makes leakage loud | The vocal stem spans **34.7 dB** from p50 to p98, and **39.0 %** of its 20 ms frames sit within 18 dB of p98 — which is exactly the `arrangement_state` presence rule. Whatever is in the stem gets stretched to full scale. |
| Three stages normalise the stem against itself | `fft_bands.py` `_robust_normalize` (5th–95th percentile **per source**); `loudness.json` (`normalization_scope: per-song-per-source-peak-rms`); `arrangement_state.py` (`PRESENT_DB_BELOW_P98 = 18.0`). None of them can be fixed by a cleaner level. |
| A flute is not noise | It is a competing musical source at comparable level in the same 400–2000 Hz band, with vibrato. No gate, denoiser or band filter separates it from a voice — a filtered stem loses vocal energy and keeps flute energy, then gets re-stretched to full scale by the three rules above. |
| The repo has already written down the wrong conclusion | `experiments/clap/README.md`: *"CLAP's vocal axis is weak (+0.36…+1.18) while the vocal stem is unambiguous (+1.5, +1.6, +1.2). Take voice presence from the stems."* Measured on four gold songs that separate cleanly. `ayuni` is the counterexample. |
| The nearest existing detector has the same weakness | `experiments/vocal_phrases/` scores 28/94 @ ±0.1 s against operator hint edges vs `sections.json`'s 5/94 — but does not clearly beat a mix-RMS threshold at a matched firing budget (44.9 vs 61.2 bounds/min), because its detector is a hysteresis gate on stem RMS. The same broken assumption. |
| Nothing is scorable yet | `data/analysis/ayuni/reference/human/` is empty and there is no Moises lyrics file for it. The four gold songs do not exhibit this failure — which is precisely why "take voice presence from the stems" measured as correct. |

### What this release does not do

- No cue authoring, no fixture reasoning — unchanged scope.
- **No cleaned `vocals.wav`.** The stem is never rewritten, filtered or gated on
  disk. It stays what Demucs produced, so provenance and determinism hold and
  `fft_bands.vocals` keeps meaning what its docstring says it means.
- **No change to `fft_bands`.** It is phase 1 and cannot be musically wrong: it
  honestly reports the spectrum of a Demucs output, and its separation-error
  caveat is already in its own docstring. The claim belongs in phase 2/3.
- **No promotion into `src/` before a winner.** Items 4–7 are lanes. Item 8 is
  the only `src/` change and is gated on one of them beating the incumbent on
  item 2's scorer; the promotion gate still applies, and a better number is
  necessary but not sufficient.
- **No consolidation of debugger lanes.** Each of items 4–7 gets its own visible
  lane, titled to match its experiment. They exist to be rendered on one
  timeline at once and contrasted by ear against the audio — merging them, or
  hiding them behind a selector, destroys the only comparison that settles this.
- **No MCP change until item 8.** The voiceness track itself stays a proposal
  artifact. Only item 8's two published fields reach the authoring model.

---

## 1. Vocal ground truth — `type: "vocal"` on human hints — `ui/`

**Current behaviour.** `human_hints.json` entries carry an optional `type`,
today `"review"` (seeded from an experiment/event block) or omitted (= a hint
authored from scratch), editable from a dropdown in the hint editor and tinted
distinctly on the Human Hints lane.

**Change.** Add `"vocal"` as a third value. A `type: "vocal"` hint means *a
voice sounds continuously across this span* — its start and end are the phrase
onset and offset, judged by ear against the audio.

This is one enum value, one dropdown entry and one tint. It deliberately does
**not** introduce a new lane, a new file or a new authoring surface: the hint
editor, the drag-to-adjust behaviour, the save path to `reference/human/` and
the timeline rendering all already exist and all already work.

**Why it is first.** Every item below is unfalsifiable without it. The four gold
songs do not exhibit the failure, so measuring on them alone would let a
candidate pass while `ayuni` stays broken.

**Corpus.** The operator marks `ayuni` and at least one further track where the
leakage is audible. These become the scoring set for items 3–7 alongside the
four gold songs.

| | |
| --- | --- |
| Writes | `reference/human/human_hints.json` — the existing file, existing schema, one new `type` value |
| Read by | item 2's scorer |
| Done when | `ayuni` carries `type: "vocal"` spans covering every sung phrase, and the lane renders them distinctly from `hint` and `review` |

---

## 2. Shared voiceness scorer and proposal schema — `experiments/` scaffold

**Change.** One scorer and one proposal schema that items 4–7 all plug into, so
the four candidates produce a single comparable table.

**Why it is second, before any detector.** `vocal_phrases` and `reactive_bands`
both landed the same unresolved result — a method that beat the incumbent but
could not be shown to beat a cheap baseline, because the two fired at different
rates. A detector that fires more often wins on recall for free. The scorer
therefore reports every candidate **at a matched firing budget**, and a result
that is not budget-matched is not a result.

**Metric.** Frame-level agreement and boundary F1 against `type: "vocal"` hint
spans from item 1:

| quantity | definition |
| --- | --- |
| frame voiceness accuracy | fraction of 50 ms frames whose voiced/unvoiced call matches the marked spans |
| false-vocal rate | fraction of frames called voiced **outside** every marked span — the quantity that is 40.8 % today and the headline number for this release |
| boundary F1 @ ±0.25 s / ±0.5 s / ±1.0 s | greedy one-to-one match of phrase onsets and offsets to marked span edges |
| bounds/min | firing rate, reported beside every F1 so budgets can be matched |

**Incumbents and baselines**, scored identically so every candidate has the same
column to beat: the `arrangement_state` `vocals` channel (the shipped claim),
the `vocal_phrases` RMS hysteresis detector, and a naive mix-RMS threshold.

**Proposal schema.** One shape for all four candidates, written to
`reference/proposals/<experiment>.json`: a per-frame `voiceness` series on the
50 ms grid with a `confidence`, plus derived `vocal_phrase` blocks. Identical
keys across candidates is what lets the four lanes be read against each other on
one timeline.

| | |
| --- | --- |
| Songs | `ayuni` + item 1's leaky tracks + the four gold songs |
| Reads | `reference/human/human_hints.json` (`type: "vocal"` only) |
| Consumed by | items 3, 4, 5, 6, 7 |

---

## 3. Demucs variant ablation — `experiments/`

**Current behaviour.** `stems.py` pins `htdemucs` (signature `955717e8`),
4-source, with the model file checksummed and fetched ahead of the run.

**Question.** How much of `ayuni`'s false vocal presence is separation error,
and how much is the self-normalisation described above?

**Change.** Re-run stems for the scoring corpus under `htdemucs`, `htdemucs_ft`
and `htdemucs_6s`, and report item 2's false-vocal rate for each. `htdemucs_6s`
adds `guitar` and `piano` sources, which pulls some melodic leakage out of
`vocals`; `_ft` is a fine-tuned variant of the same architecture.

**Why it is third, before the detectors.** It is the cheapest measurement that
could move the number — a model-pin change with no new dependency, no new image
and no new code path — and it settles which stems items 4–7 are built on. Doing
it after them would invalidate their caches.

**What it cannot do.** No variant has a flute source, so the leakage class that
caused this release survives all three. A variant that improves the number is a
smaller problem for items 4–7, not a substitute for them.

**Outcome.** A measured recommendation on the pin. Changing `DEMUCS_MODEL_NAME`
in `src/` is a follow-on decision this item informs, not one it takes: a
re-pin invalidates every cached stem in the corpus and every number measured
from one.

| | |
| --- | --- |
| Incumbent | `htdemucs` |
| Metric | item 2's false-vocal rate, per variant, per song |
| Kill condition | none — this item reports a number either way |

---

## 4. A — `vocal_voiceness` — `experiments/` + lane

**The recommended build.** A timbre discriminator over the existing vocal stem,
no model and no new image.

**Question.** Do pitch-contour and spectral cues separate a sung phrase from a
flute in the same stem, where a level gate cannot?

**Method.** Three cues, combined into a per-frame voiceness:

- **vibrato width and regularity** — singing carries wide, irregular ~5–7 Hz
  vibrato; a flute's is narrower and steadier;
- **portamento** — singing glides between notes, a flute steps between them;
- **sibilance** — consonant bursts in 4–10 kHz, which a flute has none of, and
  which are the single cue no pitched instrument can fake.

Built as a new experiment rather than by re-opening `vocal_phrases`: it reuses
that experiment's cached pYIN track, and leaves its measured result standing.
(The *"Do not re-open `vocal_phrases`"* line in `docs/experiments.md` is scoped
to the `structural_vs_micro` item it sits inside — it bars re-opening it as a
precision filter for that item, not as a voiceness term here.)

**Known gap inherited from `vocal_phrases`.** Its `sustained_notes` pass came
back empty on `_test_song` because a held note's own amplitude decay drops below
the hysteresis OFF threshold mid-note. Pitch continuity is what should bridge
that dip, and this item's f0 track is what makes bridging possible.

| | |
| --- | --- |
| Incumbents | `arrangement_state` `vocals`; `vocal_phrases`; mix-RMS threshold |
| Metric | item 2's scorer, at a matched firing budget |
| Songs | item 2's corpus |
| Lane title | **4. Vocal Voiceness** — matches `experiments/vocal_voiceness` |
| Lane output | `reference/proposals/vocal_voiceness.json`, under Human Hints |
| Kill condition | does not cut the false-vocal rate on `ayuni` below the `arrangement_state` incumbent at a matched budget |

---

## 5. B — `clap_voiceness` — `experiments/` + lane

**Question.** Does a contrastive CLAP pair distinguish a sung phrase from a
flute where CLAP's own absolute vocal axis could not?

**Method.** One contrastive pair — *"a person singing"* against *"a flute, a
synth lead"* — read as a differential after the two centrings the CLAP survey
established as mandatory. `experiments/clap/` already measured that a pair
cancels the per-sentence offset that made absolute readings useless; its
**weak** vocal axis (+0.36…+1.18) was an absolute reading, so it is not evidence
against this.

**What this candidate is for.** CLAP's 5 s window is too coarse to time a phrase
edge, so it is not a competitor on boundary F1 — it is an **independent second
opinion on the frame-level call**. If A and B disagree about whether `ayuni`'s
opening is a voice, A is the one to distrust.

| | |
| --- | --- |
| Image | the existing `ai-light-song-v2-research:dev` — no new pin |
| Metric | item 2's frame voiceness accuracy and false-vocal rate only; boundary F1 reported but not scored |
| Lane title | **5. CLAP Voiceness** — matches `experiments/clap_voiceness` |
| Lane output | `reference/proposals/clap_voiceness.json`, under Human Hints |
| Kill condition | does not agree with the marked spans better than chance on `ayuni` |

---

## 6. C — `svd_tagger` — `experiments/` + lane

**Question.** Does a pretrained tagger's *singing* class beat a hand-built
discriminator at the same job?

**Method.** The `Singing` / `Singing voice` head of a general audio tagger
(PANNs or BEATs), run on the vocal stem and on the mix, both reported. This is
the candidate with the strongest prior — the discrimination is one the model was
explicitly trained on — and the highest cost: a new sandbox image and a new
model pin, with the checkpoint fetched and checksummed ahead of the run so no
download happens mid-run.

**Why it is built even though A is the recommendation.** It is the only
candidate that could show a hand-built cue set is unnecessary. Keeping it as a
lane means that question gets answered by ear and by number rather than by
argument.

| | |
| --- | --- |
| Image | new — pattern of `Dockerfile.vocalparse` / `Dockerfile.acestep` |
| Metric | item 2's scorer, at a matched firing budget |
| Lane title | **6. SVD Tagger** — matches `experiments/svd_tagger` |
| Lane output | `reference/proposals/svd_tagger.json`, under Human Hints |
| Kill condition | does not beat item 4 on `ayuni`'s false-vocal rate, given its image and pin cost |

---

## 7. D — `whisperx_vad` — `experiments/` + lane

**Question.** Does the speech stack's VAD (and optionally its diarizer) find
vocal phrase edges on sung material?

**Method.** whisperX's VAD front-end over the vocal stem, emitting the same
proposal shape as items 4–6. Diarization is a second, optional pass: if it runs,
its speaker labels are reported as a lead/backing/other split and scored
separately, never folded into the voiceness call.

**Three recorded objections.** This item is built anyway so the comparison
happens by ear, but the plan should expect them to show up in the numbers:

- diarization answers *which speaker*, and on music it will assign a speaker to
  the flute — it segments whatever its VAD accepts, so it inherits exactly the
  false positives this release exists to remove;
- the VAD is speech-trained: sustained sung vowels with no consonants are its
  classic miss, and pitched instruments its classic false accept;
- lead-vs-backing is its weakest axis, because double-tracked leads and harmony
  stacks overlap constantly.

**Determinism.** pyannote's weights are a gated Hugging Face download. This item
is only valid if the checkpoint is fetched and checksummed ahead of the run,
like every other pinned model in this repo. A candidate that needs a live token
at analysis time cannot be promoted regardless of its score, and the item should
say so in its own README rather than discovering it at the promotion gate.

| | |
| --- | --- |
| Image | new — same pattern as item 6; `transformers` is absent from the `app` image and its `torchaudio` reports a CUDA mismatch with `torch` |
| Metric | item 2's scorer, at a matched firing budget; diarization split scored separately |
| Lane title | **7. WhisperX VAD** — matches `experiments/whisperx_vad` |
| Lane output | `reference/proposals/whisperx_vad.json`, under Human Hints |
| Kill condition | does not beat item 4 on `ayuni`'s false-vocal rate, or cannot run without a mid-run gated download |

---

## 8. `arrangement_state` gates `vocals` on voiceness — `src/`

**Current behaviour.** `detect_arrangement_state` calls `vocals` present when
the stem's RMS sits within 18 dB of its own p98 for 40 % of a 250 ms window,
held 1.5 s. On `ayuni` that is 40.8 % of the song.

**Change.** The `vocals` channel additionally requires agreement from the
winning detector's voiceness track. The other three stems are untouched — their
leakage is not the failure this release measured, and widening the change would
put four unmeasured claims into the same commit as one measured one.

**The reach test.** Two published fields, both already top level:

| file | what lands |
| --- | --- |
| `arrangement_state.json` | the `vocals` entry in `playing` becomes voiceness-gated, and carries its own named confidence — not the block's `margin_db`, which measures a different producer's decision |
| `song_event_timeline.json` | `vocal_phrase` onset/offset events from the winning detector |

**Confidence attribution.** A published row must not carry one confidence for
two producers' claims. The voiceness call gets a named confidence of its own,
sourced to the winning experiment, recorded in `field_sources` — because which
producer wins is a per-song question, and the consumer has to be told.

**Honest `unknown`.** Where the detector's confidence sits below its floor, the
`vocals` channel reports unknown rather than falling back to the RMS gate. A
silent fallback here would reproduce the exact defect this release is fixing.

**Gate.** This item does not start until one of items 4–7 beats the incumbent on
item 2's scorer at a matched budget, and the operator has reviewed the winning
lane by ear. If none wins, item 8 does not ship and the release closes with four
measured negatives and a corrected conclusion (item 9) — which is still a
result.

**Contract change.** A new field and a new event kind on two published files;
needs a handoff note to the downstream cue-authoring consumer.

---

## 9. Correct the recorded conclusion — docs

**Current behaviour.** `experiments/clap/README.md` instructs a reader to *"Take
voice presence from the stems"*, and `docs/analysis-definition.md` carries no
bound on vocal-stem trustworthiness.

**Change.** Both are corrected in the same release that measures the
counterexample:

- the CLAP README's recommendation is narrowed to what it actually measured —
  stem RMS beat CLAP's absolute vocal axis *on four gold songs that separate
  cleanly* — with `ayuni` named as the case where it fails;
- `docs/analysis-definition.md` gains the vocal-stem bound beside the drum
  vocabulary bound it already carries: what the vocal stem can and cannot be
  trusted to assert, with the 40.8 % / 39.0 % figures and their cause.

**Why it is an item and not a footnote.** The wrong conclusion is written down
in a README that reads as measured evidence, which is the repo's most trusted
kind of document. Left alone it will be followed again — the next session
building a voice-presence rule has every reason to believe it.

---

## 10. Hand-marked section segments — a new gold reference — `src/`

**Current behaviour.** `sections.json` boundaries, labels and function names
come from allin1 alone (see item table in `field_sources`). `reference/human/`
already holds `human_hints.json` (point/span annotations) and, for gold songs,
`reference/moises/segments.json` (Moises inference, validation-only). Neither
is a hand-marked segmentation an operator trusts more than allin1.

**Change.** A new optional file, `reference/human/segments.json` — a flat list
of `{start, end, label}` spans, hand-marked by the operator. Two now exist:
`"What a Feeling - Courtney Storm"` and `_test_song`. Same tier as
`human_hints.json` and `reference/moises/*`: optional, gold-song-only,
validation- and publish-fusion input, never read by an interpret/relate stage.

**Validate.** Scored the same way `reference/moises/segments.json` already is
in `segmentation.py`'s docstring — boundary recall/precision/F1 against it,
reported per song, alongside allin1's existing number.

**Fuse into `sections.json`.** Treated as producer `"human"`, fixed confidence
`0.8` — the operator's own estimate, not a ceiling, since hand-marked timing
and labels can be off. Confidence stays numeric and per-field, never folded
into a display string, so `0.8` is directly comparable to allin1's
`function_confidence`/`confidence` (often 0.15–0.26 in the corpus). Where a
song has a human `segments.json`, its spans **replace allin1's boundaries
outright** for that song — `start`/`end`/`label` all come from `"human"`, with
`field_sources` recording the per-song override; allin1 still supplies
`function_confidence`/`confidence`/`same_label_as` by matching its own
sections against the human boundaries it was replaced by. Where no human
`segments.json` exists, allin1 stays the sole producer, unchanged.

**Label vocabulary.** The function vocabulary stops being allin1's Harmonix
set (`intro outro break bridge inst solo verse chorus`). `docs/
segments-vocabulary.md` is the vocabulary for `function`/label going forward —
for human-marked rows and allin1-derived rows alike — replacing the Harmonix
set repo-wide rather than running two vocabularies side by side. allin1's
raw output is mapped onto the closest convention term at publish time.

**Docs.** `docs/reference/artifacts.md` gets an entry for
`reference/human/segments.json`, and `docs/analysis-definition.md`'s
segmentation section names it as a new validation/fusion input and records
the vocabulary switch.

| | |
| --- | --- |
| Reads | `reference/human/segments.json` (optional, per song) |
| Writes | validation report (new boundary F1 row); `sections.json` (fused `start`/`end`/`label`/`description`/`confidence`/`source`) |
| Kill condition | none — an honest `unknown`/allin1-only fallback stands when the file is absent |

---

## Open questions blocking implementation

**None.** The scoring corpus, the discriminator choice, the Demucs ablation
ordering and the `arrangement_state` gating were resolved with the operator on
2026-09-11; the segments.json fusion rule, vocabulary and docs scope were
resolved 2026-09-12. All ten items are unblocked.

One dependency is outstanding but blocks only item 8: the operator's `ayuni`
vocal marking (item 1), without which items 3–7 can run but cannot be scored.
