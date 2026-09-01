# Product Refinement — v2.2

Active worklist for the **v2.2** release of the analysis module. Items here are
scoped as they are agreed, then turned into `implementation-plan-v2.2.md`.

This doc is **open for refinement**: new scope arrives as `ADD` items below, new
defects as `BUG` entries under *Bugs — Open*. Items 1 and 2 close out pieces v2.1
explicitly deferred (a deprecation and a gold-set gap); items 3–7 are the release
proper — the drop-sequence rebuild.

## Version convention

Unchanged from v2.1 — the full table and its rationale live in
[product-refinement-v2.1.md](product-refinement-v2.1.md) under *Version
convention*. In short:

| Carrier | Rule |
| --- | --- |
| Module release | `vMAJOR.MINOR`, `MAJOR` tracks the repo (`2`). This doc produces `v2.2`. Tagged `v2.2` in git on completion. |
| Refinement doc | `product-refinement-v2.2.md` — this file. |
| Implementation plan | `implementation-plan-v2.2.md`, archived when the release closes. |
| Artifact `schema_version` | Per-artifact shape counter, independent of the module version. Bumped on every artifact whose **shape** changes this release. |
| `generated_from.engine` | Own version suffix, bumped when **behaviour** changes even if the schema does not. |

`v2.1` was drafted as `v1.1` and renumbered to align the module line with the
repo (`v2`) and the `UI v2` rebuild before its tag was cut. There is no `v1.x`
tag.

## Relationship to v2.1

v2.1 is code-complete; its `v2.1` tag is held on two host-dependent gates —
**D1** (gold-set timed labelling) and **D2** (full-corpus GPU validation run) —
recorded in [implementation-plan-v2.1.md](implementation-plan-v2.1.md). Those
gates close v2.1 and are **not** v2.2 items. v2.2 work may begin against the
committed v2.1 code before the tag lands; where a v2.2 item depends on a D1/D2
outcome, it says so.

## Release goal

Make the **drop sequence** the analyzer emits match how a lighting designer reads
one: a single gesture with a full, contiguous `approach → build → tension →
impact → release` envelope, each phase timed and energy-shaped well enough to be
pre-programmed as its own scene, with every drop in a multi-drop song detected
and its impact instant placed on the beat.

This is grounded in hand-authored drop-sequence hints for all four gold tracks
(`reference/human/human_hints.json`), which establish the target model:

| Track | Drops | Human impact instants (s) | v2.1 output |
| --- | --- | --- | --- |
| `_test_song` | 1 | ~28.4 | 2 composites; impacts 30.0 s (≈1.5 s late) and 37.0 s (false positive on a melody-restart dip); phases = `impact` + `release` only; `release` detached ~7 s after `impact` |
| `Hideaway - Kiesza` | 1 | 62.4 | none detected at the v2.1 0.3 baseline |
| `Armin - Revolution` | 2 | 57.8, 154.0 | none detected at the v2.1 0.3 baseline |
| `Titanium - David Guetta ft Sia` | 3 | 74.7, 151.3, 212.0 | one detected at the v2.1 0.3 baseline, matching no human impact |

(The three non-`_test_song` tracks have not had a full v2.1-engine re-run — that
is D2 — so their live output is still v1; the figures above are the plan's
recorded 0.3 baseline. `_test_song` has been re-run and shows the v2.1 fold
behaviour directly.)

The human model is a **fixed five-phase envelope, always in the same order,
phases contiguous** (each phase ends where the next begins; no gaps, no
overlap). Phase durations follow a consistent shape — `approach` 3–8 s, `build`
2.5–18.5 s (the most variable, and often far longer than any fixed fold
window), `tension` 0.75–3.2 s, `impact` 0.5–1.7 s, `release` ~0.4 s or a
zero-length instant. `recovery` and the `post_drop` event type do not appear in
any of the four references.

Items 3–7 below deliver this. Item 1 removes `beatdrop_visual_plan.json`, the one
consumer for which v2.1 had deferred the composite migration.

The consumer contract this release optimises against is unchanged:
[source references/analysis-input-guide.md](source%20references/analysis-input-guide.md).
Compatibility with the current artifact set and the MCP server's present
projections is **not** a constraint — where a schema, vocabulary, or file layout
blocks a more correct musical read, it changes, and the change is documented in
the contract-change note.

---

## 1. Deprecate and remove `beatdrop_visual_plan.json`

**Intent.** `beatdrop_visual_plan.json` (Story 7.5) schedules presets for a
BeatDrop / MilkDrop-style **screen visualizer** — full-frame generative graphics
on a projection or LED wall. Its output is a `preset_id` schedule with
visualizer-preset descriptors (`aggressive`, `hypnotic`, `dreamy`,
`hard_cut_friendly`). None of that maps onto moving-head control (pan/tilt,
colour, gobo, prism, zoom, beam-vs-wash, shutter), and the MCP consumer contract
[analysis-input-guide.md](source%20references/analysis-input-guide.md) — the
document the light show is actually authored from — does not reference the file
at all. It is a mandatory per-song deliverable that nothing downstream reads.

v2.1 deferred the composite-event migration specifically so this file could keep
reading the flat view. Removing the file removes that constraint and the
maintenance it carries.

The genuinely useful part of the beatdrop pipeline — per-section intent scoring
(aggression / motion / density / brightness / tension / release) and
transient-confirmed structural cut points — is fixture-agnostic and already
duplicated by `sections.json` and `song_event_timeline.json`. It is not lost by
removing the visualizer projection. If a screen-visualizer bridge is ever needed
it can be rebuilt as a thin downstream projection of the mainline structural
artifacts.

**Change.**

- Remove the `beatdrop_visual_plan.json` / `beatdrop_visual_plan.md` generation
  stage from the pipeline and from the per-song deliverable set in
  `Implementation_Guide.md` and the root `README.md` layout contract.
- Mark Story 7.5 superseded, with a one-line note pointing at the structural
  artifacts that carry its useful signal.
- Delete `src/analyzer/stages/beatdrop_visualizer.py` and its tests; drop the
  UI fixture and any UI code path that loads the file.
- Record the deliverable removal in `contract-change-v2.2.md`.

**Acceptance.** A full pipeline run produces no `beatdrop_visual_plan.*` file and
does not fail for its absence. No doc lists it as a required artifact. The
contract-change note states it is removed and why.

## 2. A `song_form` track joins the gold set

**Intent.** v2.1's gold set — `_test_song`, `Armin - Revolution`,
`Hideaway - Kiesza`, `Titanium` — is entirely `dance_form` or `hybrid`, chosen
because drop detection was the largest failure. v2.1 accepted, as a known risk,
that the pure `song_form` branch of `form_family` inference (R1a) and the
verse/chorus repetition grouping (R2) are exercised only through `Titanium`.
v2.1's evaluation-set note asks for a `song_form` track before v2.2.

**Change.** Add at least one pure `song_form` track to the gold set:

- A track with recurring vocal verse/chorus sections and matching harmonic
  material at regular intervals, and **no** drop — so `form_family` should infer
  `song_form`, not `hybrid`.
- Labelled to the same standard as the v2.1 gold set: section boundaries,
  per-section `form_role`, and a hand-authored `song_facts.json` with `genre`
  and `form_family` at `provenance: "human-confirmed"`. Since it has no drop,
  `has_drop` is `false`.
- The `--compare form` harness runs against it, and its `form_family` /
  `form_role` / repetition-grouping accuracy becomes a release gate alongside
  the existing four.

**Acceptance.** The scoring harness reports `form_family` = `song_form` for the
new track, its verses group together and its choruses group together in distinct
`repetition_group`s, and no section is assigned a dance-form `form_role`
(`build` / `drop` / `post_drop` / `breakdown`).

## 3. The drop is a canonical, contiguous five-phase envelope

**Intent.** v2.1's `_fold_composites` (`src/analyzer/stages/event_timeline.py`)
builds a composite's `phases[]` only from whatever independent events happen to
sit next to the drop anchor. `approach` is mapped to a preceding
`breakdown`/`pause_break`/`tension_hold` event — which is a low-energy trough,
not the rising pre-build the human means — so in practice it is never emitted.
`build` and `tension` appear only if a `build` event was detected within a fixed
8 s window. On `_test_song` the result is a composite carrying **only `impact`
and `release`**: the entire front of the gesture, which is exactly the part a
lighting rig has to pre-program, is absent.

The human references show the opposite model: a drop **always** has all five
phases, in the order `approach → build → tension → impact → release`, and they
**tile the gesture span contiguously** — each phase ends where the next begins.

The composite is a **pipeline-wide concept**, not an export-only projection.
`song_event_schema.json` is bumped to carry a composite grouping and `phases[]`
on `rule_candidates.json` and `events.machine.json`, and the fold runs before
those artifacts are written rather than in `export_event_timeline`. Flat member
events are still present inside the composite (`member_event_ids[]` plus the
members themselves), so ML training, benchmark, and review can keep reading flat
events while gaining the grouping. This supersedes v2.1's decision to keep the
internal schema flat at `"1.0"` (a decision that had only held because
`beatdrop_visual_plan.json` read flat members; item 1 removes that file). Making
the internal representation composite-aware is a deliberate choice for one
consistent shape end to end, so `song_event_timeline.json` is a straight
projection rather than the only place a drop is a single gesture.

**Change.** Rebuild composite construction around a fixed five-phase envelope
rather than opportunistic folding:

- The fold moves out of `export_event_timeline` into the event-machine stage (or
  a dedicated stage immediately after it), so composites exist in the strict
  internal artifacts and in the export alike.
- A detected drop instant (see item 4) is the `impact` anchor. From it, the
  envelope is filled **backwards and forwards** so that `approach`, `build`,
  `tension`, `impact`, `release` are always present and contiguous, covering
  `[approach.start, release.end]` with no gaps.
- Phase boundaries are derived from the stem-relative feature layer that v2.1
  item 1.1 already produces, not from the presence of sibling events:
  - `approach.start` — where energy first lifts off the preceding section's
    floor plateau while the kick is still absent or half-time;
  - `build.start` — where riser / onset-density / high-band energy begin their
    steep monotonic climb;
  - `tension.start` — the pre-impact suck-out: low-band energy and onset density
    drop sharply while high-band / noise peaks;
  - `impact` — the bass-stem re-entry and broadband transient on a downbeat
    (item 4);
  - `release.end` — the first bar after impact where the transient has passed
    and the groove reaches steady state.
- The fixed 8 s fold window is removed. `build` may be arbitrarily long
  (the references reach 18.5 s); the envelope is bounded by the feature
  evidence and the neighbouring section edges, not a constant.
- Any detected `build` / `breakdown` / `tension_hold` / `post_drop` events that
  fall inside the envelope are recorded as `member_event_ids[]` but no longer
  determine the phase boundaries.
- A build that never resolves (the `fake_drop` case) stays a composite with
  `approach → build → tension` only and no `impact` / `release`, as in v2.1.
- `composite_phase_vocabulary` in `event_vocabulary.json` drops `recovery` — it
  appears in no reference and its role overlaps `release`. The `post_drop` event
  type is demoted to a `member_event_ids[]` marker, not a phase.

**Acceptance.** For each of the seven gold-set drops, the emitted composite has
all five phases in order, contiguous (adjacent phase times equal within 0.05 s),
and every phase boundary is within the tolerance item 7 sets of the
human-labelled boundary. No composite is emitted with a missing interior phase.

## 4. Impact-instant precision and false-positive suppression

**Intent.** The drop anchor decides where every downstream phase and lighting
cue sits, and it is currently both late and noisy. On `_test_song` the detector
places impacts at 30.0 s and 37.0 s against a single human impact at ~28.4 s:
the first is ≈1.5 s late — more than a half-bar — because the accumulated
bass-re-entry / energy evidence peaks a beat or two *after* the transient rather
than *on* it, and the second is a false positive on the "Spacer" (a mid-song
volume dip that restarts the melody, not a drop). On `Titanium` the one detected
drop (105.7 s) matches none of the three real impacts.

**Change.**

- Once a beat window crosses the drop decision threshold, snap the `impact`
  instant to the **onset of the broadband transient / bass re-entry** within
  that window (the leading edge), not to the evidence-score peak beat.
- Require the impact to sit on or within one beat of a bar downbeat on the
  EPIC 1.2 grid.
- Add a negative gate for the melody-restart / drop-out class: a short energy
  dip that recovers to no more than its prior level, with no sustained
  stem-relative bass jump above the pre-dip floor, is not a drop. This is the
  same asymmetry v2.1 item 4 applied to `fake_drop`, applied to the drop-out
  case.

**Acceptance.** Each gold-set impact is detected within ±0.35 s (about one beat)
of its human label. The `_test_song` "Spacer" at ~36.5 s produces no drop.
`Titanium` reports three drops whose impacts match 74.7 / 151.3 / 212.0 s.

## 5. Every drop in a multi-drop song is detected

**Intent.** `Armin - Revolution` has two drop sequences and `Titanium` has
three; the v2.1 baseline detected zero and one respectively. A light show for an
EDM set is built around hitting *every* drop, so recall across the whole
timeline matters as much as precision on the first one.

**Change.**

- Confirm the non-maximum-suppression spacing (`min_spacing_seconds`, currently
  6.0 s in `DROP_EVIDENCE_PROFILE`) does not merge or discard a genuine second
  drop; the closest gold-set pair is ~80 s apart, so spacing is not the blocker,
  but the NMS must be verified against the labelled sets rather than assumed.
- Evaluate drop evidence per candidate region across the entire song, not only
  in the highest-energy section, so a second-half drop is not suppressed by a
  louder first-half one.
- The scoring harness (item 7) reports per-song drop **count** recall and
  precision, and the full-corpus gate records the drop-count distribution
  against the pre-v2.2 figures.

**Acceptance.** `Armin - Revolution` reports two drop sequences, `Titanium`
three, each with a full five-phase envelope; no gold-set drop is missed.

## 6. Measured per-phase intensity envelope

**Intent.** Each phase maps to a distinct lighting scene, and the scene's
energy is driven by the phase's `intensity`. v2.1 fills phase `intensity` with
the parent event's value or a `+0.1` fudge (`impact` 1.0, `release` 0.35 as
literal placeholders), so the field carries no real shape.

**Change.** Give each phase an `intensity` measured from the stem-relative
feature curve over that phase's own span, on the same absolute cross-song scale
v2.1 item 6 defined for events: `approach` low and rising, `build` rising more
steeply, `tension` a high held plateau, `impact` at or near the song's ceiling,
`release` a sharp fall-off. Record the start and end intensity of each phase, not
a single value, so the consumer can author a ramp.

**Acceptance.** Across the gold set, phase intensities are monotonic through
`approach → build → impact`, `impact` is the maximum of its composite, and
`release` is below `impact` by a visible margin. No phase intensity is a constant
across songs.

## 7. Ground truth, scoring, and training for drop sequences

**Intent.** The curated `human_hints.json` files introduce a new ground-truth
shape — a run of five hints titled `drop approach` / `drop build` / `drop
tension` / `drop impact` / `drop release` with contiguous times — that three
existing consumers misread:

- `--compare drops` (`src/analyzer/stages/validation/form_drops.py`)
  `labelled_drop_times()` treats **every** hint whose title contains "drop" as a
  separate drop, so `Titanium` scores as 15 labelled drops instead of 3.
- The ML training label builder (`src/analyzer/event_ml_train.py`
  `hint_to_labels()`) appends the `drop` label for any hint text containing
  "drop", so `drop build` / `drop tension` / `drop approach` — up to ~20 s of
  riser — are all trained as `drop` frames.
- Nothing documents the convention, links the five hints into one gesture, or
  checks their ordering and contiguity.

**Change.**

- Document the drop-sequence hint shape in `data_folder_reference.md` and the
  relevant story: five hints, fixed phase order (`approach → build → tension →
  impact → release`), contiguous times. The five are grouped into one drop **by
  adjacency** — a contiguous run of the canonical phase titles in order — with no
  new hint field, so the existing four `human_hints.json` files work as authored.
  The hint editor is unchanged.
- `--compare drops` collapses each five-hint run into one drop keyed on the
  `drop impact` hint and scores: drop **count** precision/recall per song;
  **impact-time error** per matched drop (±0.35 s tolerance); **per-phase
  boundary error** (each predicted phase edge vs. the human edge, ±0.5 s for
  `approach`/`build` starts, ±0.25 s for `tension`/`impact`/`release`); and
  **phase completeness** (all five emitted).
- The ML / benchmark label mapping routes phase hints to phase-appropriate
  types: `drop approach` → **no positive label** (`approach` is a derived phase
  label only, not an event type — see item 3), `drop build` → `build`, `drop
  tension` → `tension_hold`, `drop impact` → `drop`, `drop release` → `post_drop`.
  Only the `impact` hint yields a `drop` frame.
- `human_hints.json` load paths validate that a partial or out-of-order
  drop sequence fails loudly rather than being silently scored.

**Acceptance.** `--compare drops` on the four gold tracks reports 1 / 1 / 2 / 3
labelled drops respectively and scores each detected sequence against its
five-phase label. An ML training run over the gold set produces `drop` frames
only across the `impact` spans, not the build-ups.

---

## Evaluation set

Inherits the v2.1 gold set plus the `song_form` track from item 2. The v2.1
D1 labelling pass (timed drop boundaries, section boundaries, `form_role` for the
three unlabelled dance tracks) is a v2.1 close-out gate; item 2 adds one track to
what that pass covers.

All four v2.1 gold tracks now carry hand-authored **drop-sequence hints** in
`reference/human/human_hints.json` — a five-phase `approach → build → tension →
impact → release` run per drop (`_test_song` 1, `Hideaway` 1, `Armin` 2,
`Titanium` 3; 7 sequences, 35 phase hints). These are the ground truth items 3–7
are scored against. `Armin` and `_test_song` also carry a few non-drop section
hints (`Breath`, `Spacer`, outro phrasing) that must not be read as drop labels.

## Release process

Carries the v2.1 conventions unchanged:

- **Story specs are updated inside the item that changes them.**
- **Projected-shape changes update the in-repo MCP server in the same commit.**
  The song-understanding MCP server now lives in this repo (`mcp/`, see
  [mcp-server/product-definition.md](mcp-server/product-definition.md)); an item
  that reshapes an artifact it projects also updates the affected serializer and
  its golden snapshots, and the tests fail if it drifts. A **contract-change
  note** (`contract-change-v2.2.md`) is still maintained for any *external*
  consumer (the light-show host).
- **Per-item runs use one song; full-corpus runs are the release gate.**

## Bugs — Open

Regressions found against committed v2.1 work that need a design decision or
sequencing land here (annotated with the plan item that will address them);
one-off fixes go to `docs/issues.md` (backend) or `docs/web-ui/ui-issues.md`
(frontend) instead.

**B1. Composite `phases[]` omits the whole front of the gesture.**
`_fold_composites` in `src/analyzer/stages/event_timeline.py` emits `approach`
only from a preceding low-energy trough event and `build` / `tension` only from a
`build` event inside a fixed 8 s window. On `_test_song` the v2.1 composite
carries only `impact` and `release`. Addressed by item 3.

**B2. `release` phase is attached from a distant unrelated event.**
`_fold_composites` accepts any `post_drop` / `energy_reset` starting within 8 s
after the anchor as the `release` phase. On `_test_song` this placed `release` at
36.5 s, roughly 7 s after the `impact` at 30.0 s; the human `release` is ~0.4 s
and immediate. Addressed by item 3 (contiguity) and item 4 (anchor precision).

**B3. Drop-phase hints are miscounted as separate drops and mistrained.**
`labelled_drop_times()` in `src/analyzer/stages/validation/form_drops.py` counts
every "drop"-titled hint as one drop (Titanium: 15, not 3), and
`hint_to_labels()` in `src/analyzer/event_ml_train.py` labels every "drop"-titled
span as a `drop` frame including the multi-second build-ups. Exposed by the new
curated `human_hints.json` shape. Addressed by item 7.

## Decisions taken by recommendation

No open questions remain. These were settled before planning and are listed here
so they can be reviewed in one pass; each is stated in full where it belongs.

| Decision | Lives in |
| --- | --- |
| `beatdrop_visual_plan.json` is deprecated and removed — it targets a screen visualizer, not moving heads, and no downstream consumer reads it. | Item 1 |
| The composite is pipeline-wide: `song_event_schema.json` is bumped to carry the grouping and `phases[]`, with flat member events retained inside each composite. The fold moves out of the export into the event-machine stage. | Item 3 |
| Drop-phase hints are grouped into one sequence **by adjacency** — a contiguous run of the canonical phase titles in order. No new hint field, no editor change. | Item 7 |
| `approach` is a **derived phase label only**, not an event type. It has no rule detector and no ML label; its span is filled geometrically from `build.start` back to where energy lifts off the section floor. | Items 3, 7 |

## Out of scope for v2.2

- Fixture mapping and `lighting_score.md` generation — downstream of this work
  and not reshaped here unless an item explicitly pulls them in.
- Retraining or re-architecting the event ML classifier. Item 7 fixes the label
  mapping that feeds training; an actual retraining pass is a separate release.
- The `form_role` / `form_family` / repetition work from v2.1 — only extended,
  via the new gold-set track in item 2, not changed.
- MCP-server changes. Item 1 removes a deliverable and items 3 and 6 reshape
  projected shapes; v2.2 produces `contract-change-v2.2.md` for the MCP side to
  absorb, as in v2.1.
