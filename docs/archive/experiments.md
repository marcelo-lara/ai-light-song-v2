# Archive — concluded experiments

The standing record of which experiments were run and what they scored
(constitution §3.4). This is a deliberate, named exception to §4's "no archive
folder" rule. An entry lands here only after the operator has picked
**archive** or **promote** for a concluded experiment in
[`experiments_pending.md`](../experiments_pending.md); each entry below keeps
its measured results and conclusion exactly as reported there — measured
evidence does not go stale (constitution §4).

---

## All-In-One (`allin1`) — named song form

<https://github.com/mir-aidj/all-in-one>

### Disposition

**Promoted**, in `docs/implementation-plan-v3.0.md` item 7. Replaced
`src/analyzer/stages/sections/` (the 1,403-line deterministic-DSP segmenter
plus its 13-value invented `section_character` vocabulary) with
`src/analyzer/stages/segmentation.py`. Changed the projected `sections.json`
and `artifacts/section_segmentation/sections.json`. Full experiment writeup,
kept current as measured evidence: [`../../experiments/allin1/README.md`](../../experiments/allin1/README.md).

### Why? What for?

Named song form. The shipped segmentation labelled sections with invented mood
adjectives ("Momentum Lift", "Vocal Spotlight"), so nothing in the artifact
said *which part of the song* a section is, or that a returning chorus is the
same part as the first one — and its boundaries were measured at chance.
`allin1` is the one model in the 2026-09 survey that outputs *named*
functional structure (Harmonix vocabulary: `intro verse chorus bridge inst
solo break outro`) in a single multi-task model trained on pop/EDM, the
repertoire this project targets.

### Experiment Plan

Built as `experiments/allin1/`: `model.py` runs the model in a sandbox image,
seeded with the pipeline's own demucs stems for reproducibility; `features.py`
derives merged sections (with `same_label_as`), transitions between them, the
raw 8-bar phrase grid, tempo, a beat-grid comparison against essentia, and a
degeneracy check; `export.py` writes a proposal per song to
`reference/proposals/allin1.json`; `score.py` measures against the incumbent
and an evenly-spaced-grid baseline. Two debugger lanes: **allin1 Transitions**
and **allin1 Sections** (both later removed on promotion — item 14 — since
their content now lives in the production **Sections** lane and
`song_event_timeline.json`'s transition rows).

### Results evidence

Gold set: 4 songs, 7 hand-placed drop-impact marks, plus 38 interior boundaries
in `reference/moises/segments.json` once that reference landed.

| method | ±0.5 s | ±1.0 s | ±2.0 s | boundaries/min |
| --- | --- | --- | --- | --- |
| **allin1 section transitions** | **3/7** | **4/7** | 4/7 | **1.6** |
| allin1 phrase edges (unmerged) | 3/7 | 4/7 | 6/7 | 3.3 |
| shipped `sections.json` (incumbent) | 0/7 | 0/7 | 1/7 | 3.6 |
| evenly spaced grid, same budget | 0/7 | 2/7 | 3/7 | 3.6 |

Re-scored against the 38 Moises boundaries once available: allin1 merged
sections **0.53 recall / 0.91 precision / 0.67 F1** at ±1.0 s, phrase edges
**0.84 / 0.76 / 0.80**, against the incumbent's **0.32 / 0.27 / 0.29**.

Seeded with the pipeline's own stems, allin1 is reproducible (3/3 identical
runs on every gold song); unseeded it disagrees with itself on 14 of 21 songs
— the earlier survey's "degenerates on instrumental trance" finding was an
artifact of unseeded demucs, not a property of the model. Its own beat grid is
not usable (4 of 21 corpus songs a clean half-beat off essentia's, 1 halves the
tempo) — structure only, keep essentia's grid (a decision item 8 later made
explicit and separately measured).

### Conclusion

`allin1` supplied the named structure the pipeline had no equivalent of, at
less than half the incumbent's boundary budget, against an incumbent that lost
to evenly spaced guesses. Promoted in v3.0 item 7. Section *identity*
(`same_label_as` is label repetition, not acoustic identity) remained
unresolved at promotion time and is tracked separately — see the CLAP entry
below and the open identity entry in `experiments_pending.md`.

---

## Transition-FX and gesture phases — riser, downlifter, snare roll, pre-drop gap, impact

<https://www.ujam.com/tutorials/how-to-create-huge-edm-transitions/>

### Disposition

**Promoted**, in `docs/implementation-plan-v3.0.md` item 9. Replaced the whole
Epic-5 `event_*` stack (`event_rules/`, `event_machine/`, `event_features/`,
`event_timeline.py`, `event_review.py`, `event_identifiers.py`,
`review_queue.py`, `event_contracts.py`, ~3,800 lines) with
`src/analyzer/stages/gestures.py`. Changed the projected
`song_event_timeline.json`. Full experiment writeup, kept current as measured
evidence: [`../../experiments/gestures/README.md`](../../experiments/gestures/README.md).

### Why? What for?

Constitution §1.2: a drop "has an approach, a build, a tension span, an impact
and a release, and each phase becomes a different look." The `event_*` stack
claimed to do this and measured at chance, because it inferred gestures from
raw features with no named structure to hang them on. This experiment builds
one detector per named, conspicuous sound-design device (riser, downlifter,
reverse cymbal, snare roll, pre-drop gap, impact) with a signature detectable
in artifacts the pipeline already trusts, and assembles them into composite
gestures with named internal phases.

### Experiment Plan

Built as `experiments/gestures/`, numpy only. One detector per primitive
(riser/downlifter via sliding-window linear regression on high-band energy,
reverse cymbal via a rising mix-RMS ramp into a transient spike, snare roll via
onset-density doubling, impact via a simultaneous sub-band + transient spike,
pre-drop gap via a `dropout_strength` spike). Assembly anchors each gesture on
a detected impact and fills approach/build/tension/release from primitives in
the preceding window; a phase with no supporting primitive is absent, never
guessed. Explicitly does not name the section — a drop is derived from a named
section pair, never detected directly (constitution §5.2).

### Results evidence

Gold set, 7 drop impacts:

| method | ±0.25 s | ±0.5 s | ±1.0 s | events/min |
| --- | --- | --- | --- | --- |
| gesture impact phase | 2/7 | 4/7 | 4/7 | 14.1 |
| incumbent `song_event_timeline` build/drop/impact | 0/7 | 1/7 | 2/7 | 1.5 |
| **RMS-derivative peak-picker (baseline)** | **3/7** | **6/7** | **7/7** | 40.8 |

Clearly beat the incumbent — direct confirmation of the "measured at chance"
finding, on the metric the incumbent's own stack was supposed to own. Did
**not** beat the cheapest possible baseline on raw impact-instant recall,
though that baseline fires ~3× as often and emits no phases, no evidence and no
claim that can be wrong. What the gesture pipeline delivers that no recall
number captures: 12 gestures assembled from 35 primitives on `_test_song`
alone, each phase with its own span, confidence and per-primitive evidence
string. Coverage of non-drop hints (Armin's "Breath", `_test_song`'s vocal
outro phrases) was weak — every miss was vocal- or texture-driven with no
riser/roll/transient signature, complementary to (not overlapping with) the
still-open vocal-phrases work.

The plan's own called-for measurement — per-primitive precision, hand-audited
by ear over 20-30 spans — was **not run** before promotion. This is a known
gap carried forward, not a claim that every emitted primitive is correct.

### Conclusion

Positive against the stack it replaced, negative against the cheapest
baseline on raw recall, and the one thing it uniquely offered — named,
evidenced, phase-structured gestures — is not captured by a recall-only
metric at all. Promoted in v3.0 item 9 on the strength of the structural
requirement (constitution §1.2) rather than the recall number alone. The
per-primitive precision audit remains open work for anyone extending the
gesture detectors.

---

## CLAP — section character and section identity

<https://github.com/LAION-AI/CLAP>

### Disposition

**Split.** The **section-identity** result below is archived here as a
concluded, negative finding — CLAP was measured and lost to a 20-coefficient
MFCC baseline, so nothing from it was promoted into `src/` for identity. The
**character-layer** idea (a texture/intensity axis beyond verse/chorus
arrangement — see the pinned operator guidance on non-arrangement character
blocks) is a **separate, still-open question** and was **not** decided in
v3.0. It stays in [`experiments_pending.md`](../experiments_pending.md) as its
own entry rather than being archived with the identity result.

### Why? What for?

Two questions were run under one experiment. First: does CLAP supply what is
missing beyond the song arrangement — texture blocks like `Armin - Revolution`
`hint-006`, "Breath", *"Vocal - no intense section"*, invisible to any
verse/chorus label. Second (the part concluded here): can a CLAP embedding
supply section *identity* — which other sections are acoustically the same
part returning — where `sections/form.py`'s `repetition_group` shipped `null`
on every section of all 21 songs.

### Experiment Plan

Built as `experiments/clap/`. Three sources on a shared 10 Hz grid: stems
(`essentia/rms_loudness.json`, exact and free), CLAP contrastive probe pairs
(calm↔intense, sparse↔dense), and allin1's frame-level posterior
(`include_activations=True`). For the identity question specifically: mean
pairwise AUC of CLAP embeddings at matching two occurrences of the same
section, against a 20-coefficient MFCC baseline and a chroma baseline.

### Results evidence

**Section identity — the concluded, archived half:** mean pair AUC — MFCC 20
**0.73**, CLAP raw 0.68, chroma 0.62, CLAP centred 0.61, duration control 0.59,
time control 0.46. Twenty MFCC coefficients beat the 512-d CLAP embedding.
CLAP scores 0.83 at telling a section from *itself* and 0.68 at matching two
occurrences of the same part, so identity needs a representation trained for
invariance between occurrences, not a bigger general-purpose embedding.
**MFCC 0.73 is the number any next identity attempt must beat.**

**Character layer — the still-open half, not decided in v3.0:** the ablation
that justifies CLAP's one useful axis: stems + CLAP calm found 28 "breath"
blocks covering 41% of the corpus (vs. 81 blocks / 73% for stems alone), and
found the hand-marked Armin `Breath` block in both cases — only the
CLAP-gated version is specific. CLAP's `calm` axis tracks the operator's own
intensity judgement; its `drums`/`bass` axes are confidently wrong about what
is playing. allin1's frame-level posterior (shadow labels) finds a breakdown
inside an `inst` stretch the 8-bar argmax segmentation cannot express. Full
tables: [`../../experiments/clap/README.md`](../../experiments/clap/README.md).

### Conclusion

**Identity: negative and archived.** CLAP cannot recognise a returning part
better than 20 MFCC coefficients; the lane built for it was removed. Any
future identity attempt needs an invariance-trained embedding (or a
cover-song-style objective), not a bigger general-purpose one, and must clear
MFCC's 0.73.

**Character: positive but not promoted in v3.0**, and not archived with the
identity result — it is a genuinely different, still-open question (a new
projected file would be needed; no file in
`docs/reference/analysis-input-guide.md` carries texture today) and remains
queued in `experiments_pending.md`.
