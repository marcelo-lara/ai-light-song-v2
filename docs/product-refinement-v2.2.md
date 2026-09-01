# Product Refinement — v2.2

Active worklist for the **v2.2** release of the analysis module. Items here are
scoped as they are agreed, then turned into `implementation-plan-v2.2.md`.

This doc is **open for refinement**: new scope arrives as `ADD` items below, new
defects as `BUG` entries under *Bugs — Open*. The two carry-over items already
listed are the ones v2.1 explicitly deferred to this release; they are not the
whole release.

## Version convention

Unchanged from v2.1 — the full table and its rationale live in
[product-refinement-v2.1.md](product-refinement-v2.1.md) under *Version
convention*. In short:

| Carrier | Rule |
|---------|------|
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

_To be set once the worklist is agreed._ The two carry-over items point at a
provisional theme: finish the composite-event migration that v2.1 started but
deliberately stopped short of (so every consumer reads one representation of a
drop), and widen the evaluation set so the `song_form` half of v2.1's form work
is actually measured rather than assumed.

The consumer contract this release optimises against is unchanged:
[source references/analysis-input-guide.md](source%20references/analysis-input-guide.md).
Compatibility with the current artifact set and the MCP server's present
projections is **not** a constraint — where a schema, vocabulary, or file layout
blocks a more correct musical read, it changes, and the change is documented in
the contract-change note.

---

## 1. `beatdrop_visual_plan.json` consumes composite phases

**Intent.** v2.1 introduced composite events with typed `phases[]` in
`song_event_timeline.json` (R5), but left `beatdrop_visual_plan.json` reading the
**flattened** event view and kept the strict internal `song_event_schema.json`
at `schema_version` `"1.0"` with flat member events specifically because
`beatdrop_visual_plan.json` still depended on them. v2.1's contract-change note
records this as the one deferred piece ("Moving it to composites is v2.2").

**Change.** Migrate `beatdrop_visual_plan.json` generation to consume composite
events and their phases directly:

- The visual plan reads the composite `phases[]` (`approach`, `build`,
  `tension`, `impact`, `release`, `recovery`) so a drop's build, tension span,
  and release each drive their own segment of the plan rather than being
  reconstructed from flat `build` / `drop` / `post_drop` rows.
- Once nothing else reads the flat member events, the strict internal
  `song_event_schema.json` can drop the flat-member representation (or bump its
  `schema_version` and carry phases). Decide during planning which of the two;
  the deciding factor is whether any other internal consumer still needs the
  flat view.
- `beatdrop_visual_plan.json`'s own `schema_version` / engine version bumps to
  reflect the new input.

**Acceptance.** A song with a detected drop produces a `beatdrop_visual_plan.json`
whose segments align to the composite's phase boundaries. No pipeline stage
reads flat `layer`-style or flat `build`/`drop`/`post_drop` member events for the
visual plan. The contract-change note for v2.2 records the new
`beatdrop_visual_plan.json` shape.

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

---

## Evaluation set

Inherits the v2.1 gold set plus the `song_form` track from item 2. The v2.1
D1 labelling pass (timed drop boundaries, section boundaries, `form_role` for the
three unlabelled dance tracks) is a v2.1 close-out gate; item 2 adds one track to
what that pass covers.

## Release process

Carries the v2.1 conventions unchanged:

- **Story specs are updated inside the item that changes them.**
- **The MCP server is not modified by this module.** Items that change a
  projected shape produce a **contract-change note** (`contract-change-v2.2.md`),
  maintained as items land, handed to the MCP side to absorb.
- **Per-item runs use one song; full-corpus runs are the release gate.**

## Bugs — Open

_None recorded yet. Regressions found against committed v2.1 work that need a
design decision or sequencing land here (annotated with the plan item that will
address them); one-off fixes go to `docs/issues.md` (backend) or
`docs/web-ui/ui-issues.md` (frontend) instead._

## Decisions taken by recommendation

_None yet._

## Out of scope for v2.2

_To be filled in as the worklist firms up. Fixture mapping and
`lighting_score.md` generation remain downstream of this work and are not
reshaped here unless an item explicitly pulls them in._
