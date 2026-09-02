> **ARCHIVED — historical record, not a specification.**
> This document describes how something was *planned or built at the time*. It
> is **not** a description of current behaviour and may contradict the code.
> Do not treat it as a contract and do not implement from it: verify against
> `src/` first. For what the system does today, read `CLAUDE.md` at the repo
> root.

# Product Refinement — v2.1

Active worklist for the **v2.1** release of the analysis module. Items here are
scoped and ready to be turned into `implementation-plan-v2.1.md`.

## Version convention

`v2.1` is the version of **this module** (the analyzer in `ai-light-song-v2`) —
not of the lighting system as a whole, and not of any single artifact.

The module release line is numbered `v2.x` to match the repository (`v2`) and
the from-scratch UI rebuild (`UI v2`), so a reader sees one major version across
the three. This release was drafted as `v1.1` and renumbered to `v2.1` before
its tag was cut; the git tag is `v2.1`, and there is no `v1.x` tag. The next
release is `v2.2`.

The artifact `schema_version` carrier is **independent** of the module version
and is not renumbered by this alignment: an artifact whose shape changed this
release carries `schema_version` `"1.1"` (its second shape), regardless of the
module being `v2.1`. `schema_version` counts an artifact's own shape revisions;
the module version is the umbrella release.

| Carrier | Rule |
|---------|------|
| Module release | `vMAJOR.MINOR`, `MAJOR` tracks the repo (`2`). The work in this doc produces `v2.1`. Tagged `v2.1` in git on completion. |
| Refinement doc | `product-refinement-vX.Y.md` — the active worklist for that release. |
| Implementation plan | `implementation-plan-vX.Y.md`, archived when the release closes. |
| Artifact `schema_version` | Per-artifact shape counter, independent of the module version. Bumped to `"1.1"` on every artifact whose **shape** changes this release. Artifacts whose shape is unchanged stay at `"1.0"`. |
| `generated_from.engine` | Carries its own version suffix, bumped when **behaviour** changes even if the schema does not — e.g. `deterministic.section_segmentation.v1` → `.v2`. |

A consumer therefore learns *what shape* to expect from `schema_version` and
*how the numbers were produced* from the engine string. The module version is
the umbrella both roll up to.

## Release goal

Make the structural read of a song correct and honestly-scored, so the MCP
server can answer "where is the bridge / where are the drops" from the analysis
alone rather than inferring it from dense data.

Compatibility with the current artifact set and with the MCP server's present
projections is **not** a constraint on this release. Where a schema, vocabulary,
or file layout blocks a more correct musical read, it changes.

The consumer contract this release optimises against is
[source references/analysis-input-guide.md](../reference/analysis-input-guide.md) —
in particular its priority order: section boundaries and identity first, then
the event timeline, then hints, then the beat grid.

---

## 1. Two-axis section labelling: musical form + energy character

**Intent.** The show's storytelling depends on knowing that a part *is* an
intro, a verse, a chorus, a bridge, a drop. The current controlled vocabulary is
entirely energy-shape language (`breath_space`, `flowing_plateau`,
`momentum_lift`), so the output cannot say where the chorus is.

**Change.** `artifacts/section_segmentation/sections.json` rows carry two
independent labels:

- `form_role` — musical function, from a new controlled vocabulary:
  `intro`, `verse`, `pre_chorus`, `chorus`, `hook`, `bridge`, `breakdown`,
  `build`, `drop`, `post_drop`, `instrumental`, `outro`, `unknown`.
  `unknown` is a first-class, expected value — see item 3.
- `energy_character` — the existing 13-value vocabulary, retained unchanged as
  secondary lighting metadata.

`form_role` is the primary label. The top-level `sections.json` `label` string
is rebuilt from it.

`form_role` is produced by deterministic rules, not a model. The constitution
requires byte-identical output for a given input and engine version, and rules
keep the evidence behind each label inspectable — which items 3 and 7 both
depend on. Revisit only if rules demonstrably plateau against the evaluation set.

### 1a. `form_family` gates the vocabulary

The `form_role` vocabulary above fuses two taxonomies: pop song-form (`verse`,
`pre_chorus`, `chorus`, `bridge`) and dance form (`build`, `drop`, `post_drop`,
`breakdown`). `pre_chorus` is meaningless in minimal techno and `drop` is
meaningless in a folk ballad, so which values are admissible has to be decided
per song.

Add a song-level `form_family` with its own confidence, written to the
segmentation artifact:

- `dance_form` — near-constant tempo, four-on-the-floor kick, and at least one
  bass-dropout → re-entry with a sharp transient on a bar boundary.
- `song_form` — recurring vocal sections with matching harmonic material at
  regular intervals.
- `hybrid` — both. A vocal verse/chorus track that also has a drop.
- `unknown` — neither, or the evidence conflicts.

`form_family` constrains which `form_role` values may be assigned.

**`form_family` is derived from audio evidence only. The inferred genre label is
not an input to it, and not a prior on `form_role`.** Genre confidence across the
current corpus spans 0.199–0.454 with 20 of 21 songs tagged `electronic` and/or
`dance`, so the label is close to constant and carries little information. Its
errors are also whole-song and correlated — a house track tagged `ambient` would
have drop detection suppressed across its entire timeline rather than in a few
places. Using it as a prior would additionally fold a low-confidence guess into
the section `confidence` that item 3 requires to be evidence-only, and would
double-count genre for the consumer, which already receives `genre.json`'s
`guidance[]` verbatim.

Keeping the two independent also preserves a free cross-check: disagreement
between `form_family` and the genre label is a useful review signal, which
coupling them would destroy by construction. That disagreement is reported per
item 7.

The bass-dropout signature is directly measurable and far more reliable here
than the genre classifier — on `Armin - Revolution` the bass stem varies about
30× across sections while mix RMS varies about 2.7× — and it is the same
evidence item 4 computes for drop detection, so `form_family` is close to free.

A *human-confirmed* genre is a different matter and may break ties; see item 7.

**Acceptance.** On a track with obvious verse/chorus alternation, `form_role`
alternates correspondingly. No section is assigned a `form_role` the evidence
does not support, or one outside its `form_family` — `unknown` is emitted
instead.

## 2. Section repetition identity (`A` / `A'` / `B`)

**Intent.** Nothing in the pipeline currently models section identity. The MCP
server's `similar_sections` grouping is built from `section_character` string
equality alone, so two sections that merely share an energy shape are proposed
as a reusable look pair, and three consecutive sections sharing a catch-all
label are proposed as mutually similar.

**Change.** Add repetition grouping derived from self-similarity over combined
harmonic and timbral features, not from the label:

- `repetition_group` — `"A"`, `"B"`, `"C"`… assigned by material similarity.
- `variant_of` — the `section_id` of the first occurrence when this section is a
  variant rather than a literal repeat; `null` for the first occurrence.
- `similarity` — the measured similarity to that first occurrence.

Sections sharing a `repetition_group` are the correct input to reusable-look
pairing; `energy_character` equality stops being used for that purpose.

**Acceptance.** A verse/chorus track groups its choruses together and its verses
together, with the groups distinct from each other.

## 3. Honest boundary confidence

**Intent.** `confidence` is load-bearing for the consumer, which is explicitly
built to distrust it and to read a low value as "don't spend tokens
corroborating this". It must therefore measure how certain the boundary and
label are — nothing else.

**Change.** Replace the current section confidence with a value composed of
boundary and label evidence only:

- sharpness of the novelty peak at the boundary,
- agreement between independent detectors (harmonic vs. timbral vs. energy),
- alignment to a measurable transient,
- alignment to the bar grid,
- for `form_role`, the margin between the best and second-best role.

Loudness, repetition count, and onset density are removed as direct confidence
terms — they may inform the *label*, never the *confidence in it*.

The value must be free to reach both ends of its range. A genuinely ambiguous
boundary reporting `0.25` is a correct and useful output; the previous
formulation could not emit one.

**Acceptance.** Across the corpus, confidence spans a wide range rather than
clustering; sections whose boundaries disagree between detectors score visibly
lower than sections where all detectors agree.

## 4. Drop detection rebuilt on stem-relative evidence

**Intent.** Drops are the single most important gesture for an EDM light show
and are currently almost never detected across the corpus, while `fake_drop`
fires far more often than `drop`.

**Change.** Three parts:

- **Signal.** Drive detection from stem-relative bass and spectral activation
  rather than full-mix RMS. Modern masters are limited, so mix RMS is nearly
  flat across a whole track while the bass stem varies over a far wider range;
  the discriminative signal is the one currently under-weighted.
- **Scoring.** Replace the conjunction of six thresholds with accumulated
  weighted evidence against a single decision threshold, so one weak feature no
  longer vetoes an otherwise unambiguous drop.
- **Symmetry.** `fake_drop` must require *positive* evidence of an withheld
  release (build present, expected release absent). It may no longer be reachable
  through a condition that is easier to satisfy than `drop` itself.

**Acceptance.** Tracks with an unambiguous drop report one. `fake_drop` no longer
outnumbers `drop` across the corpus.

## 5. Composite events with typed phases

**Intent.** A drop is not a point. It has a start, a build, a tension span, and
a release, and each sub-part maps to a different lighting scene. The event schema
is flat, so even when the parts are individually detected nothing records that
they are one gesture.

**Change.** Introduce composite events. A composite carries its own overall
`start_time`/`end_time`, `confidence`, and `intensity`, plus an ordered
`phases[]`, each phase with `phase` (`approach`, `build`, `tension`, `impact`,
`release`, `recovery`), `start_time`, `end_time`, and `intensity`.

Phase members are no longer emitted as independent top-level events. The
unscoped projection stays a compact table of contents: the composite appears as
one row, and its phases are delivered when a section pass asks for its own
section.

A build that never resolves is emitted as a composite whose `release` phase is
absent, not as a standalone phase event. That case is musically the `fake_drop`
situation, and keeping one representation means a consumer never has to handle
phases in two different shapes.

`beatdrop_visual_plan.json` keeps reading the flattened view for v2.1 and is not
updated to consume composites; that moves to v2.2.

**Acceptance.** A detected drop is one timeline entry whose phases cover its span
contiguously and can each be authored as a distinct scene.

## 6. A lean event timeline with a usable `intensity`

**Intent.** The guide asks for few high-value discrete events with tight time
ranges over a dense stream. The timeline is currently dominated by sub-second
`layer_add`/`layer_remove` blips, which is the exact anti-pattern, and they are
what the concept pass sees for the whole song.

**Change.**

- `layer_add` / `layer_remove` stop being timeline events. Texture change is
  summarised per section (which stems enter and leave, and where) instead of
  emitted per occurrence.
- `intensity` is rescaled so it uses its range. It currently saturates at the
  ceiling for a majority of events across the corpus, which makes it
  uninformative in precisely the projection where it is one of only five fields
  the model sees. The scale is **absolute, not per-song**: the consumer reads
  `intensity` as a cross-song magnitude when planning a set, and per-song
  normalisation would make a quiet track's loudest moment indistinguishable from
  a loud track's.
- Every surviving event keeps an honest `confidence` and a `summary` that
  describes the musical moment rather than restating the rule that fired.

**Acceptance.** Event counts per song fall substantially, with the remaining
events being ones a lighting designer would cue. `intensity` is distributed
across its range rather than piled at the maximum.

## 7. Human-curated song facts and a machine review queue

**Intent.** Where the machine is genuinely uncertain, a short human answer is
worth more than any amount of additional inference. One song out of the analysed
corpus currently carries any human curation at all, so the constraint is not the
schema — it is how cheap a question is to answer.

**Change.** Two files and a strict direction of flow between them.

**Human input — `reference/human/song_facts.json` (new).** Song-level, untimed
truths a person can state directly: `genre`, `form_family`, and later any other
whole-song fact. Each value carries `provenance: "human-confirmed"`.

This is a sibling of `human_hints.json`, not part of it. Every entry in
`human_hints.json` is a timed moment (`start_time`/`end_time`) consumed by event
benchmarking and ML training; song-level facts have a different shape, a
different lifecycle, and a different consumer, and mixing them would force every
reader of timed hints to filter.

**Machine output — `artifacts/validation/review_queue.json` (new).** The open
questions this run could not settle: the field in question, its competing
candidates with scores, the timestamps of the evidence that was ambiguous, and
why confidence was low. Ranked, so the highest-leverage question is first.

**Direction of flow.** The analyzer proposes into `validation/`; a human
disposes into `reference/`. The analyzer never writes into `reference/`.

This is deliberate. `reference/` is the validation truth set, and the analyzer
today only ever reads it. If the analyzer seeded its own low-confidence guesses
there, validation would begin scoring inference against a file inference wrote,
and the resulting numbers would degrade silently. A guess parked in the truth
folder awaiting confirmation is also an unresolvable state — used, it launders a
weak inference into truth; unused, it is clutter — and nothing in the file would
record which. Under this split, an unanswered question is unambiguously not in
use, and the constitution's existing rule holds: `reference/human/` is written
only by the UI on an explicit human save.

**Use.** A human-confirmed genre breaks ties in `form_family` when the measured
evidence is close. It does not override a confident measurement — a human naming
the genre does not establish whether this particular track drops where the audio
says it does. Where a human fact is used, the affected output records
`provenance: "human-confirmed"`.

The queue also carries the `form_family` / genre disagreement flag from item 1a.

**Acceptance.** A run on a song with ambiguous form emits a ranked queue whose
top entry is answerable in one choice. Answering it in `song_facts.json` changes
the next run's `form_family`, and the resulting sections carry
`provenance: "human-confirmed"`. `reference/` receives no analyzer writes.

---

## Evaluation set

Every acceptance criterion above needs something to measure against, and at the
start of this release there is almost nothing: of the 21 analysed songs, only
`_test_song` carries any ground truth (`moises/segments.json`, `chords.json`,
and 11 timed human hints, including an explicit "Drop in" at 28.8 s and a
"build up" at 22.2 s). The other 20 have none.

**Gold set — four tracks, all with unambiguous drops:**

| Track | Why it is in the set |
| --- | --- |
| `_test_song` (58 s) | Already labelled: 11 timed human hints including "Drop in" at 28.8 s and "build up" at 22.2 s. Fast regression fixture. |
| `Armin - Revolution` | Zero drops currently detected across a 194 s trance track. |
| `Hideaway - Kiesza` | Genre mis-tagged `ambient, instrumental` @ 0.22; drop present. |
| `Titanium - David Guetta ft Sia` | Vocal verse/chorus *and* a drop — the `hybrid` form family. |

Each is labelled with section boundaries, `form_role`, and drop times.

**Labelling needs no new tool.** The Story 8.8 human-hint editor already writes
timed hints into `reference/human/human_hints.json`, which is exactly the shape
drop and boundary labels take — `_test_song` is already labelled that way.
Song-level facts for four tracks are hand-authored JSON. Item 7's review queue is
therefore **not** a prerequisite for the gold set; it is built later in the
release, sized for the remaining 17 tracks where hand-labelling does not scale.

**Known gap in coverage.** All four tracks are `dance_form` or `hybrid`, chosen
because drop detection is the largest failure. Pure `song_form` is therefore
under-tested: item 1a's `song_form` branch and item 2's verse/chorus grouping are
exercised only through `Titanium`. Accepted for v2.1; a `song_form` track should
join the gold set before v2.2.

**Fixtures.** `data/analysis/test-song/` is an orphaned analysis directory with
no source mp3 in `data/songs/` and should be deleted. `ayuni` is a real 165 s
track, unlabelled, and stays outside the gold set for this release.

Until the gold set is labelled, an item's acceptance is provisional: it may be
implemented and pushed, but it is not considered validated.

## Release process

**Story specs are updated inside the item that changes them.** Items 1–7 change
the contracts in stories 3.1, 3.2, 4.5, 5.1, 5.2, 5.6 and 6.1, plus new UI work
for item 7. Each plan item's commit carries its code, its tests, *and* the Story
file edits for the contract it changed. The constitution requires a Story to
match the code before a task is done, and doing it per item avoids a
reconciliation backlog at the end of the release.

**The MCP server is not modified in v2.1.** It is a separate component. Items 1,
5 and 6 change the shape it projects — `form_role`/`form_family`, composite
`phases[]`, and the removal of `layer_add`/`layer_remove` — so this release
instead produces a **contract-change note** listing exactly what changed in the
top-level files, handed over for the MCP side to absorb. Compatibility is not a
constraint on the change; documenting it is.

**Corpus re-runs are per-item on one song, full-corpus once.** During an item,
re-run the changed stage on a single song for feedback. A full 22-song run is
the release-level validation gate, not a per-item one.

## Bugs — Open

**B1. Section confidence is a loudness proxy.**
`src/analyzer/stages/sections/segmenter.py:228` computes confidence as a fixed
affine function of section energy, repetition, and onset density. It contains no
term for boundary certainty, so a misplaced boundary in a loud section scores
high. Addressed by item 3.

**B2. Drop rule is a six-way conjunction with self-defeating thresholds.**
`src/analyzer/stages/event_rules/generator.py:175-190` requires six thresholds to
pass simultaneously plus membership in the top intensity cluster. Three of those
thresholds are derived from the song's own mean and standard deviation, so a
track that is mostly drops raises its own bar until they no longer qualify.
Addressed by item 4.

**B3. `fake_drop` is easier to satisfy than `drop`.**
`src/analyzer/stages/event_rules/generator.py:286` accepts a `fake_drop` on a
disjunction whose second branch fires on *low* harmonic tension, while `drop`
requires a six-way conjunction. The pipeline is therefore structurally biased
toward calling drops fake. Addressed by item 4.

**B4. `intensity` saturates.**
A majority of events across the analysed corpus carry `intensity` exactly at the
ceiling, collapsing one of the five unscoped projected fields into a constant.
Addressed by item 6.

**B5. Top-level and segmentation section lists are coupled by array index.**
The consumer guide records that the two lists are matched positionally, so a
count or order mismatch silently misaligns every section's character and
confidence. With the section schema changing this release, the two should be
joined on `section_id` instead of position.

**B6. Benchmark threshold profiles are selected by the inferred genre label.**
`src/analyzer/stages/event_benchmark.py:39` picks a profile from
`genre_result["genres"][0]`. Across the corpus that label is near-constant
(`electronic`/`dance` for 20 of 21 songs) at 0.199–0.454 confidence, so profiles
are bucketing on noise. This is post-hoc scoring rather than inference today, but
if tuned thresholds ever feed back into detection it becomes an inference path
through the back door — which item 1a rules out. Profile selection should key on
`form_family`, or on a human-confirmed genre, once item 7 exists.

## Decisions taken by recommendation

No open questions remain. These were settled by adopting the recommendation
rather than by separate decision, and are listed here so they can be reviewed in
one pass before handoff. Each is stated in full where it belongs.

| Decision | Lives in |
| --- | --- |
| `form_role` comes from deterministic rules, not a model | Item 1 |
| Genre is not a prior on `form_role`; `form_family` is evidence-derived | Item 1a |
| An unresolved build is a composite with no `release` phase | Item 5 |
| `beatdrop_visual_plan.json` keeps the flattened view until v2.2 | Item 5 |
| `intensity` is on an absolute scale, not per-song | Item 6 |
| Gold set is `_test_song`, `Armin - Revolution`, `Hideaway - Kiesza`, `Titanium` | Evaluation set |
| Labelling uses the existing 8.8 editor; item 7 is not a gold-set prerequisite | Evaluation set |
| Pure `song_form` is under-tested in v2.1; accepted risk | Evaluation set |
| `data/analysis/test-song/` is orphaned and should be deleted | Evaluation set |
| Story specs are updated inside the item that changes them | Release process |
| The MCP server is not modified in v2.1; a contract note is handed over | Release process |
| Per-item runs use one song; full-corpus runs are the release gate | Release process |

## Out of scope for v2.1

- Fixture mapping and `lighting_score.md` generation — downstream of this work
  and unaffected while the published contracts are re-cut.
- The internal debugger UI, **except** the item 7 round-trip: the UI must render
  `review_queue.json` as answerable questions and save the answers into
  `reference/human/song_facts.json`. Without that the queue has no consumer and
  human facts have no editor. Lane changes to render composites and the new
  section fields are out of scope and follow once the artifact shapes settle.
- Retraining the genre model. Item 1a removes the pipeline's dependence on it,
  and item 7 gives the human-confirmed path that matters more.
- The intermediate layer files, `event_inference/` internals, pattern mining, and
  `validation/` reports, except where they feed the items above — none are on the
  MCP surface.
