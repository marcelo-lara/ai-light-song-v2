# Product refinement — v3.4

**Status: open, nothing implemented.** A scoped worklist of concrete
refinements, collected item by item. Nothing here is done by writing it down.

**v3.4 is scoped to one question: can this repo measure how a passage *behaves*
— and be measured on it?** The operator's working thesis is that a light show is
driven by melody and harmony dynamics set against the drums. Reviewing it
against `Queen of Kings - Alessandra` found it partly right, found that the
instruments meant to test it are lying, and found there are no labels to score
anything against. Three experiment lanes and two `ui/` labelling surfaces follow from that.

Evidence base, with the numbers:
[`alessandra_findings.md`](alessandra_findings.md).

---

## The one change

**How a passage behaves becomes a measured, labelled, scoreable quantity.**

Today `layer_c_energy.json` asserts a `level` per section and per beat, nothing
publishes it, and nothing has ever checked it against a human. The pipeline
emits no periodicity signal at all. This release adds two `ui/` labelling
surfaces, three experiment lanes that compete against the incumbent, and fixes
the instruments that make the competition unfair.

### What the review established

All measured, not asserted.

| | Finding |
| --- | --- |
| The thesis is real but weak | corr(harmonic, drums) is negative on **18/23** songs — but median only **−0.15**, and it **inverts on 5/23**, including `_test_song`. `Queen of Kings` (−0.637) is the 2nd most extreme song in the corpus. |
| The contrast beats loudness | Across the first 64 s, mix loudness moves **1.4×**; tonal density moves **~18×**. |
| The instruments lie | The harmonic *stem* reads 0.009 RMS at the drop while the chroma chord decoder finds Am at **0.716 confidence**. Drum events carry **velocity 100, always** — 921 of 921. |
| Texture change finds every boundary | Spectral novelty scores recall **0.80–1.00** against operator hints on all four gold songs — at precision 0.05–0.50. |
| Repetition classifies the passage | Bar-shape autocorrelation separates through-composed / bar-loop / half-bar-loop cleanly, and recovers the operator-stated 8-bar bass phrase on `Chimera - Hana` from two stems independently. |

### What this release does not do

- No cue authoring, no fixture reasoning — unchanged scope.
- **No MCP change.** Nothing here reaches the authoring model yet, by design:
  `layer_a`–`layer_d` all sit in `artifacts/`, unpublished. Publishing is a
  phase-4 decision that should follow the experiment's result, not precede it.
  Stated here so the gap is deferred, not overlooked.
- No promotion into `src/`. Items 2, 3 and 4 are lanes; the promotion gate
  still applies, and a better number is necessary but not sufficient.
- **No consolidation of debugger lanes.** Every new artifact this release
  produces gets its own visible lane — four per-stem FFT lanes, three
  experiment lanes, block ratings, lyric validation. Nothing is merged, hidden behind a
  selector, or folded into a related lane for tidiness. The debugger is the
  only instrument for judging whether any of this is right, and a signal that
  cannot be seen cannot be checked.

---

## 1. A rating surface for block energy and tension — `ui/`

**Current behaviour.** `reference/human/human_hints.json` carries `title`,
`summary` and free-text `lighting_hint` per block. It carries no rating. There
is therefore **nothing to score an energy model against**, on any song. This is
the same shape as the open `arrangement_state` issue: the metric measures the
absence of labels, not the detector.

**Change.** The debugger gains controls to rate each human-hint block on two
1–5 axes, writing a new file the operator owns.

**Why two axes, not one.** The operator's own marking breaks the single-scalar
framing. `hint-007` "close to silence" and `hint-010` "micro break" are their
*lowest*-energy blocks and their highest-value lighting moments — a blackout
before a drop. Any energy scalar ranks them near the bottom. Tension is rated
separately so the two can disagree.

### Decisions taken (2026-09-10, with the operator)

| | | |
| --- | --- | --- |
| D1 | **resolved** | Ratings live in a **new file**, `reference/human/block_energy.json`, joined to hints by `hint_id` at read time. They do **not** become fields on `human_hints.json` — that file stays hand-authored and free of machine-facing structure. |
| D2 | **resolved** | Two axes, `energy` and `tension`, integers 1–5. A block may be unrated. |
| D3 | **resolved** | The debugger's writable-path list, documented as load-bearing, grows by one (to three, or four with item 9). `ui-definition.md`, `reference/artifacts.md` and `reference/ui-development.md` change in the same item. |

```json
{
  "schema_version": "1.0",
  "song_name": "Queen of Kings - Alessandra",
  "ratings": [
    { "hint_id": "hint-007", "energy": 1, "tension": 5 },
    { "hint_id": "hint-009", "energy": 5, "tension": 4 }
  ]
}
```

**Scope guard.** A labelling surface only. Nothing in `src/` or `mcp/` may read
`block_energy.json` — it is `reference/human/` material, like the hints
themselves.

**Done when** the four gold songs plus `Queen of Kings` are fully rated, and the
UI shows how many blocks remain unrated so a pass can be driven to completion.

---

## 2. Texture Novelty

`experiments/texture_novelty/`

**Current behaviour.** `sections.json` has **no boundary at 48.7 s** on
`Queen of Kings`, where the operator hears the drop.

**Question.** Does self-similarity novelty over the 7 FFT bands locate operator
hint boundaries better than `sections.json` and `arrangement_state.json`?

**Already measured** (cosine self-similarity, 1.0 s half-window, checkerboard):

| song | recall | precision | F1 | `sections.json` F1 |
| --- | --- | --- | --- | --- |
| `_test_song` | 0.80 | 0.50 | **0.62** | 0.00 |
| `Titanium` | 0.80 | 0.13 | 0.22 | 0.34 |
| `Hideaway` | 1.00 | 0.05 | 0.10 | 0.35 |
| `Armin - Revolution` | 0.83 | 0.12 | 0.21 | 0.22 |
| `Queen of Kings` | 0.88 | 0.20 | 0.33 | 0.33 |

**The finding, and the open problem.** Recall is **0.80–1.00 on every gold
song** — the texture genuinely does change at operator boundaries, everywhere.
Precision is 0.05–0.50: it fires 64–114 times per song. **Ranking peaks by
novelty magnitude makes it worse** (F1 0.00–0.66), so a magnitude threshold is
not the fix. The lane exists to find what is.

**Candidate feature sets to try**, in order:

1. the raw 7-band vector (the measured baseline above);
2. **chroma/HPCP against percussive band weight** — tonal density swings ~18×
   across the first 64 s of `Queen of Kings` where mix loudness moves only 1.4×.
   Use chroma on the **mix**, never the harmonic stem, which reads
   0.009 RMS at the drop while the chord decoder finds Am at 0.716;
3. per-stem band weight (item 5).

| | |
| --- | --- |
| Incumbent | `sections.json`; `arrangement_state` (0.59 on `_test_song`, 0.20 pooled) |
| Cheap baseline | mix-RMS delta, MFCC novelty |
| Metric | boundary F1 @ ±1.0 s vs `reference/human/human_hints.json` edges |
| Songs | the four gold songs |
| Lane title | **2. Texture Novelty** — matches this header and `experiments/texture_novelty` |
| Lane output | `reference/proposals/texture_novelty.json`, under Human Hints |
| Kill condition | no feature set lifts precision above 0.5 at recall ≥ 0.8 |

---

## 3. Phrase Periodicity

`experiments/phrase_periodicity/`

**Question.** What is the repetition period of a passage, and does its strength
classify what kind of passage it is?

**Method.** Collapse each bar to a 16-slot energy profile per stem,
**z-normalise it so it measures shape rather than level**, then autocorrelate
the sequence of bars at 1–16 bar lags. Period, not phase — so this is
independent of the downbeat-phase weakness.

The normalisation is load-bearing, not a detail: on `Chimera - Hana` it takes
the 8-bar peak from prominence **+0.056 to +0.325**, roughly 6× sharper.

**Already measured — block character.** Against the operator's own blocks on
`Queen of Kings`, three regimes separate cleanly and reproduce their own
distinctions:

| regime | `rep@bar` | period | operator blocks |
| --- | --- | --- | --- |
| through-composed | ≈ 0 (−0.04, 0.05) | — | Fairytale intro, Melodic Vocal bridge — the drumless, long-tonal-phrase passages |
| bar loop | ≈ 0.5 | exactly 1 bar | Post-Intro, Post-Intro + Harmony — the tribal percussion |
| half-bar loop, dense | `rep@beat` **and** `rep@bar` high | ½ bar | the three chorus/drop blocks |

The "Vocal tension build" sits between at 0.15, rising from the bridge's 0.05 —
repetition *emerging*, which is the build, measured.

**Already measured — phrase length.** Prominence over neighbouring lags doubles
as an honest confidence:

| song / stem | phrase | prominence |
| --- | --- | --- |
| `Chimera - Hana` / bass | **8 bars** | +0.325 |
| `Chimera - Hana` / harmonic | **8 bars** | +0.245 |
| `Hideaway` / bass | **8 bars** | +0.173 |
| `Chimera - Hana` / drums | 4–8 | +0.075 |
| `Queen of Kings` / bass | — | +0.069 |
| `Titanium` / bass | 4 | +0.045 |

Operator-supplied ground truth: the `Chimera - Hana` bass repeats every 8 bars,
"almost exact". Two stems find it independently, and the drums sit at 4 — a
4-bar drum loop nested inside an 8-bar bass phrase. Where prominence is near
zero the honest output is **"no phrase structure detected"**, not a forced
number; `Queen of Kings`'s bass genuinely does not loop, it changes character
per section.

| | |
| --- | --- |
| Incumbent | none — the pipeline emits no periodicity or phrase-length signal at all |
| Cheap baseline | raw-envelope autocorrelation without the z-normalisation |
| Metric | phrase length vs operator-stated truth; regime separation vs marked blocks |
| Lane title | **3. Phrase Periodicity** — matches this header and `experiments/phrase_periodicity` |
| Lane output | `reference/proposals/phrase_periodicity.json`, under Human Hints |
| Kill condition | prominence fails to separate known-8-bar songs from the rest |

**Known limit, and it is structural rather than incidental.** This needs at
least one bar, ideally two. Seven of the operator's sixteen `Queen of Kings`
blocks are shorter — including all four micro-events. Phrase Periodicity classifies block
*character*; it will never find a sub-second cue. That is item 4's job, below.

---

## 4. Structural vs Micro

`experiments/structural_vs_micro/`

**It gets its own lane.** This classification is derived by combining items 2
and 3, but it is **its own claim with its own error mode** — a boundary
mislabelled `structural` when it is a micro-cue is a wrong answer that neither
parent lane's metric would catch. Folded in as a field on their blocks it would
ride along invisibly inside lanes whose own numbers look fine. It is therefore a
lane, played against the waveform and judged on its own.

Neither parent lane alone answers the question the operator actually posed.
Together they do something neither was designed for.

Fitting a 4-bar phrase grid to the operator's `Queen of Kings` hints:

| edges | offset from the 4-bar grid |
| --- | --- |
| 1.11, 16.39, 23.94, 31.58, 39.21, 62.16 s | **−0.06 … −0.00 bars (≈ 0.1 s)** |
| 45.0, 46.5, 47.2, 48.7, 52.1, 52.5, 55.9, 56.3, 60.2 s | 0.15 – 3.3 bars |

**Six of sixteen edges lock to the phrase grid to within about 0.1 s.** The nine
that miss are exactly the sub-bar micro-events — the pre-drop, the near-silence,
the micro break, the 'hey'.

Averaged over all edges the phrase-grid prior beats chance by only 1.3–2.25×,
which is why this is *not* a precision filter for item 2 — the hypothesis this
review started with, and it failed. What it is instead is a **two-class split the
pipeline currently cannot express**: a structural boundary that lands on the
phrase grid, versus a cue that lives inside a phrase and never will. The
operator marks both kinds in one file and the distinction is invisible
downstream.

**Deliverable.** Every proposed block carries `kind: "structural" | "micro"`,
decided by phrase-grid fit, plus the fit error in bars so a reviewer can see
*how* marginal a call was. This is the release's most novel output and the one
most likely to change how cues get authored.

| | |
| --- | --- |
| Incumbent | none — the pipeline cannot express the distinction at all |
| Cheap baseline | block duration alone (< 1 bar ⇒ micro) |
| Metric | agreement with the operator's own hints, split by kind |
| Songs | the four gold songs |
| Lane title | **4. Structural vs Micro** — matches this header and `experiments/structural_vs_micro` |
| Lane output | `reference/proposals/structural_vs_micro.json`, under Human Hints |
| Kill condition | fails to beat the duration-only baseline |

**Explicitly not in scope:** vocal phrasing, bar-grid *phase* and local band
auto-gain already have lanes — `vocal_phrases`, `grid_consensus`,
`reactive_bands` — all measured, none promoted. Do not re-open them here.

**Metric assumption, settled:** the corpus is 4/4 at near-constant BPM,
tighter still where drum machines are involved. Bar-synchronous methods are
first-class here and need no escape hatch. This does not extend to grid
*phase*, which remains a real weakness — both lanes use period only.

---

## 5. Per-stem FFT bands — dependency for items 2 and 3

**Current behaviour.** `artifacts/essentia/fft_bands.json` is **mix-only**
(`harmonic_stem: null`): 7 bands, 50 ms frames, plus `brightness_ratio`,
`transient_strength`, `dropout_strength`.

**Change.** Run the same 7-band analysis per stem.

**Each stem gets its own visible lane.** Four new artifacts means **four new
lanes** — bass, drums, harmonic, vocals — beside the existing mix **FFT Bands**
lane, not folded into it and not merged into one multi-stem lane. Per-stem
separation error is exactly what a reviewer needs to catch by eye (the harmonic
stem reading near-zero through the drop is the standing example), and it is
invisible if the stems are averaged or hidden behind a selector. The debugger is
the only instrument for judging whether these are right.

**Why it is required, not nice-to-have.** Item 6 establishes that drum events
carry no dynamics at all. Spectral energy at the event timestamp is therefore
**the only available route to "how hard was this hit"** — the quantity the whole
energy thesis rests on. Sub-band (20–60 Hz) on the drums stem is a kick-weight
proxy; brilliance (6–16 kHz) separates hats from crashes.

**Known cost, stated up front.** Per-stem FFT is FFT of a Demucs output, so it
inherits every separation error before the transform. Mix FFT inherits none but
cannot attribute. That is the real trade — not resolution.

---

## 6. Drum events — a three-symbol vocabulary with no dynamics

**Current behaviour.** `drums.py` runs Omnizart on the drums stem and maps
General MIDI pitch to `kick` / `snare` / `hat`. Measured on `Queen of Kings`:

| | |
| --- | --- |
| Distinct pitches emitted, ever | **3** — 35 (kick), 38 (snare), 42 (closed hat) |
| `velocity` | **100 on all 921 events** |
| `duration` | 0.050 s, quantised |
| `confidence` | `null` on all 921 events |

`unresolved_count: 0` does not mean everything resolved cleanly — it means the
model can only emit three symbols and all three are in the map.

**Consequences, both real on this song.** Toms and congas have nowhere to go, so
the operator's "rhythmic tribal percussion" (16.4–31.6 s) is forced into kick or
snare. Crash and ride collapse into `hat`, so a crash on the drop and a hi-hat
in a verse are the same symbol — and a crash is a lighting cue where a hi-hat is
not.

**Change.** Split crash from hi-hat, and document the rest.

- Gate pitch 42 by **brilliance-band (6–16 kHz) transient magnitude** to
  separate a crash from a closed hi-hat. No new model, no checkpoint hunt — it
  uses band data that already exists.
- **Write the remaining bound into `CLAUDE.md`**: three symbols, velocity
  constant, `confidence: null`, toms and congas folded into kick or snare.

**Why only this much (D4, resolved 2026-09-10).** A crash is a lighting cue and
a hi-hat is not, so the crash/hat split is the whole lighting value of a wider
taxonomy at a fraction of the cost. Model-hunting for a tom-capable transcriber
has an unknown payoff and could eat the release. Toms stay mislabelled, honestly
documented — which means the operator's "rhythmic tribal percussion" block is a
**known** wrong label, not a silent one.

An honest documented bound is an acceptable outcome. A silent three-class
taxonomy presented as a drum transcription is not.

**Do not** publish the `velocity` field to fix this. It is a constant;
publishing it would add a confident-looking zero-information column.

---

## 7. Section function labels that contradict the energy — `src/`

**Current behaviour.** On `Queen of Kings`, allin1's labels are close to
anti-correlated with energy:

| passage | label | mix | drums |
| --- | --- | --- | --- |
| 3–15 s | **chorus** | 0.12 | **0.007** |
| 17–30 s | verse | 0.13 | 0.14 |
| 49–60 s | *(mid-chorus, no boundary)* | **0.17** | **0.20** |
| 64–78 s | verse | 0.17 | **0.23** |

"chorus" sits on the two quietest passages, "verse" on the two loudest. A cue
model reading `sections.json` lights the calmest moment in the song like a
climax.

**Change.** A phase-3 step cross-checks each allin1 `function` against
`arrangement_state` and `loudness`. Where a "chorus" is quieter and thinner than
the "verse" that follows, **keep allin1's label and flag it**:

```json
{
  "function": "chorus",
  "function_confidence": 0.544,
  "function_status": "contested",
  "contested_by": "energy"
}
```

**Why flag rather than flip (D5, resolved 2026-09-10).** Flipping asserts a
fresh claim from a heuristic with very little evidence behind it, and a
confident wrong answer costs the show. Dropping to `unknown` discards a label
that may well be right and leaves the authoring model with less than it has
today. Flagging asserts nothing new, preserves both signals, and matches the
honest-unknown pattern `function_status` already carries.

**Phase rule.** Phase 3 may refine phase 2 but writes a new artifact; it does not
mutate `sections.json` in place.

**Still to measure before building.** Whether the contradiction reproduces
across the corpus or is specific to this song's form — the same per-section
stem-RMS table across all 23 songs. This is a measurement, not a decision; a
rule tuned on one song is how the old segmenter reached F1 0.29. It does not
block the item's design, only its scope.

---

## 8. `layer_b_symbolic.json` is missing on every song with ground truth

**Current behaviour.** The note layer — 4,098 note events with pitch, velocity,
duration and source stem — exists for **17 of 23** songs. The six missing
include `Titanium`, `Hideaway`, `Armin - Revolution` and `_test_song`: **all
four gold songs.**

**Change.** Regenerate it on the four gold songs, or record why it cannot be.

**Why it blocks the release.** The richest evidence for the operator's thesis
currently cannot be validated against a single hand-marked song. Item 2 works
around this by using chroma instead — but any future note-level work is blocked
until this is fixed, and the gap is invisible today because nothing reads the
file.

---

## 9. Human validation of Moises lyric tokens — `ui/`

**Current behaviour.** The **Moises Lyrics** lane reads
`reference/moises/lyrics.json` — Moises' per-word inference, tinted green→amber→
red by Moises' own confidence. The operator verifies token timing against the
waveform and today records that by hand-editing the file (setting entries to
`"0.99"`, the existing operator-curated convention). There is no UI affordance
for it, and the hand-edit is indistinguishable from Moises' own high scores.

**Change.** In the lane-events panel, each word token's card
(`lane-events__card`) gains a **✔** button to the right of
`lane-events__label`. Clicking it marks that token **human-validated**; the lane
then shows it at confidence `1` — a value Moises itself never emits, so
validated tokens are unambiguous. Click again to un-validate. Markers
(`<SOL>` / `<EOL>`, confidence `null`) get no button.

### Decision D6 (2026-09-10, with the operator)

| | | |
| --- | --- | --- |
| D6 | **resolved** | Validation is an **overlay**, not an edit to the source. New file `reference/human/lyric_validations.json` — `{ schema_version, song_name, validated_ids: [int] }`. The lane reads `reference/moises/lyrics.json` and substitutes confidence `1` for any token whose `id` is listed. `reference/moises/` stays read-only and inference-only. Same pattern as D1. |

```json
{
  "schema_version": "1.0",
  "song_name": "Queen of Kings - Alessandra",
  "validated_ids": [2, 3, 4, 6, 7]
}
```

**Writable-path list — now four.** This is the second path v3.4 adds
(`block_energy.json` is the first, item 1 / D3). `ui-definition.md`,
`reference/artifacts.md` and `reference/ui-development.md` list all four:
`human_hints.json`, `song_facts.json`, `block_energy.json`,
`lyric_validations.json`. Whichever of item 1 or item 9 lands second updates the
count the first one wrote.

**Scope guard.** `lyric_validations.json` is `reference/human/` material.
Nothing in `src/` or `mcp/` reads it; it exists so the operator can see, in the
debugger, which tokens they have personally checked.

### For the planning phase to resolve

- `lane-events__card` is itself a `<button>` (it seeks on click). A nested
  `<button>` is invalid — the card structure has to change (wrapper `<div>` with
  two buttons, or the ✔ as a sibling that stops propagation). Implementation
  detail, but it changes the card's DOM.
- **Save cadence.** The other `reference/human/` writers save only on an
  explicit Save. A per-click validation toggle wants immediate persistence
  instead — recommend each click writes, and note the divergence from the
  human-hints pattern rather than forcing a Save button into a rapid workflow.
- A validated token needs a **distinct tint** in both the panel and the timeline
  lane — it must not just fall into the existing `≥ 0.7` "High" bucket alongside
  Moises' own 0.99s.

**Done when** a token can be validated and un-validated in the Moises Lyrics
panel, the state persists across a reload, and validated tokens are visually
distinct from Moises-scored ones.

---

## Open questions blocking implementation

**None.** `D4`, `D5` and `D6` were resolved with the operator on 2026-09-10;
all nine items are unblocked.

One measurement is outstanding but blocks nothing: the corpus-wide check on
item 7's label/energy contradiction, which sets that item's scope rather than
its design.
