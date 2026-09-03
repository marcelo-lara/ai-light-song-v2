# Project Constitution — ai-light-song-v2

The standing law of this repository. Principles, not procedure: how to run it is
in [`../CLAUDE.md`](../CLAUDE.md) and [`README.md`](README.md).

*Last revised: 2026-09-02.*

---

## 1. Purpose

**This repository produces concrete, reliable, precisely-timed musical facts
that a reasoning model can author a production-quality light show from.**

That is the whole job. This analyzer is the *foundation* of a light show; it is
not the light show. A separate system, reading a compact projection of what we
emit, decides what the fixtures do. Our contribution is the quality and honesty
of the musical read underneath that decision.

### 1.1 Explicitly out of scope

The following are **not** this repository's goals, and work should not be
justified by them:

- **Fixture-aware orchestration.** Which fixture does what, when, in what
  colour, is authored downstream. We never model a rig.
- **Cue authoring, lighting design documents, and DMX.**
- **Screen visualizers.**

Epic 7 no longer exists in `src/`. `lighting_score.md`, `lighting_events.json`
and `beatdrop_visual_plan.json` — and the three stages that produced them — were
removed on 2026-09-02, having had no consumer: none of them appeared in
[`reference/analysis-input-guide.md`](reference/analysis-input-guide.md), and
`data/fixtures/` never existed. Do not reintroduce them here.

### 1.2 What "concrete and reliable, at precise times" means

Every output should answer, for a reader that cannot listen to the song:

- **Where does the song change, and into what?** Named structural parts and the
  transitions between them. Knowing something is *different* at a given instant
  is what defines a cue.
- **How do the parts relate?** Which sections are the same one returning, which
  is the biggest, which is the quietest.
- **What happens inside a part?** Composite gestures with internal phases — a
  drop has an approach, a build, a tension span, an impact and a release, and
  each phase becomes a different look. A flat list of independent events loses
  the thing that matters.
- **When, exactly?** To the instant, not to the neighbourhood. A boundary that
  is two seconds late is a cue that fires on the wrong bar.

A signal that cannot be stated compactly, with a time and a confidence, is not
yet a deliverable.

### 1.3 The reach test

A feature is only real if it reaches the authoring model. Only the files listed
in [`reference/analysis-input-guide.md`](reference/analysis-input-guide.md) are
ever projected; everything else under `artifacts/` is invisible downstream.
Improving an artifact nothing projects changes nothing about the show. Before
building, say which projected file the signal lands in.

---

## 2. Honesty

Confidence-bearing analysis is **inference, never premise**. The pipeline exists
to inform a decision it does not make, so an output that overstates itself is
worse than no output.

- **No silent fallbacks.** If a model or heuristic fails, fail the run or emit
  `unknown`. Never invent a plausible default — a generic C-major chord, a
  guessed section label — to keep a run green.
- **`unknown` is a valid, valuable answer.** A reader told "we don't know" spends
  no tokens corroborating a wrong claim. Prefer an honest gap to a manufactured
  one.
- **Confidence is a separate numeric field**, never folded into a display string,
  and never inflated. A low confidence is itself useful signal.
- **Provenance travels with the claim.** Every generated file carries a
  `generated_from` block; every section and event carries how it was arrived at
  (`machine-only`, `reviewed`, `human-confirmed`, …).
- **Reference data is validation-only.** Never copy
  `data/analysis/<Song - Artist>/reference/` into a generated artifact except
  through an explicit, confidence-gated, provenance-recorded promotion that
  preserves the inferred result alongside it and records the failing gate.
  Silent substitution is a constitutional violation.

---

## 3. Experimentation

Improving the musical read is a research activity, not only an engineering one.
Most attempts will fail. The constitution's job is to make failing cheap and
make the failure *legible*, so it is not repeated.

- **Experiments live in `experiments/<topic>/`**, outside `src/`. They may use
  their own container images, their own dependencies, and their own throwaway
  code. They must not modify the analyzer image or `src/`.
- **An experiment states a question and a measurement before it starts.** What
  would count as better, on which songs, against which incumbent. A survey with
  no baseline proves nothing.
- **Always measure against the thing you propose to replace**, and against a
  cheap classical baseline. "It looked plausible" is not a result.
- **A negative result is a deliverable.** Write it down: what was tried, what it
  scored, and what specifically was wrong with it. A documented dead end stops
  the approach from being reinvented; an undocumented one guarantees it.
- **Keep the record where the experiment lives.** A failed attempt is written
  up in its own `experiments/<topic>/README.md`, alongside the numbers. That
  README is current material — it states what is true about what was tried — so
  it stays in the tree. Losing the record costs the next person the same week.
- **Promotion into `src/` requires beating the incumbent on the stated metric**,
  and the number goes in the commit message. Nothing is adopted because it is
  newer, larger, or from a better-known lab.
- **Ground truth is precious and scarce.** When a measurement is at the noise
  floor of the labels, say so and fix the labels rather than tuning against
  them.

### 3.1 `experiments/` is a sandbox for anything

`experiments/` at the repository root exists so that a new idea can be tried
*without touching the production pipeline*. Inside it, try anything: other
models, other libraries, other container images, throwaway code, competing
approaches side by side. Nothing in `experiments/` is held to the pipeline's
determinism, schema or style rules, and nothing in `src/` may import from it.

The reason is historical and specific: unproven work merged straight into `src/`
is how the analyzer accumulated several thousand lines of event machinery built
on a segmentation that measures at chance. **An experiment stays an experiment
until it has earned promotion.**

### 3.2 Make it reviewable — add a UI lane

Musical output has to be *heard against the song*, not read as a table. When an
experiment produces anything time-bearing — boundaries, regions, events, curves
— it should be viewable in the debugger (`ui/`) as its own lane, played against
the waveform and against the human hints.

The established pattern, and the one to copy: `experiments/drop_detection`
writes `data/analysis/<Song - Artist>/reference/proposals/drop_impacts.json`,
and the UI renders it as the **Drop Proposals** lane directly beneath **Human
Hints**, so a proposal can be auditioned against hand-authored truth while the
song plays.

Rules for experiment output:

- It goes under `reference/proposals/`, never into `artifacts/` and never into
  the stable top-level contract. It is a proposal, not a deliverable.
- It never overwrites `reference/human/` — hand-authored ground truth stays
  purely hand-authored.
- The lane is added to the debugger's lane registry like any other, and removed
  when the experiment is abandoned or promoted.

An experiment whose output cannot be placed on a timeline is not exempt; it just
reports its numbers instead.

### 3.3 Promotion is asked for, never assumed

When an experiment beats the incumbent on the stated metric, **stop and ask
before moving anything into `src/`.** Promotion is a decision for the operator,
not a conclusion the evidence makes on its own — a better number on the gold set
is necessary, not sufficient, and the cost of carrying another production stage
is a judgement about the pipeline as a whole.

A promotion proposal states: what it replaces, the metric and both numbers, what
gets **deleted** from `src/` in the same change, and which projected file changes
as a result (§1.3). Promotion that only adds is usually a mistake; the point of
the sandbox is that the pipeline stays small.

### 3.4 The pending-experiments queue

Experiments that have not started yet are queued in
[`experiments_pending.md`](experiments_pending.md). The file as it currently
stands is the sample skeleton — copy one entry's shape for every new entry.

- **Immediately after the entry's title comes the URL** to the model or repo the
  experiment is about. That link may itself carry basic instructions, so it is
  the first thing a reader follows.
- **`### Why? What for?`** states the purpose of the *thing* the operator wants
  out of this experiment — what capability or answer it is meant to deliver, in
  the operator's terms.
- **`### Experiment Plan`** is the assistant's plan for how to implement the
  experiment under `experiments/<topic>/` — the concrete approach, not the
  motivation.
- **`### Results evidence`** holds the measured output — the golden-set
  comparison, the numbers against the incumbent and the baseline.
- **`### Conclusion`** is a short TLDR of what the results mean.

When an experiment is concluded, the assistant tells the operator it can be
**archived** or **promoted** (promotion still follows §3.3). Once the operator
picks one, the entry is removed from `experiments_pending.md` and moved, with its
filled-in results and conclusion, to
[`archive/experiments.md`](archive/experiments.md). This archive file is a
deliberate, named exception to §4's "no archive folder" rule: it is the standing
record of which experiments were run and what they scored.

### 3.5 The experiment corpus

Experiments run against the **four golden songs only**: `_test_song`,
`Titanium - David Guetta ft Sia`, `Hideaway - Kiesza`, and `Armin - Revolution`.
These are the songs with hand-labelled ground truth, so they are the only ones
where a measured comparison against the incumbent and a baseline means anything.

When an experiment is too heavy to run across all four — a slow model, an
expensive container — or when the goal is just a smoke test that the code path
works, use **`_test_song` alone**.

---

## 4. Documentation

- **`docs/` holds current material only.** Everything in it describes how the
  system is meant to behave now, and is kept in sync with the code. There is no
  archive folder: **git history is the archive.** A document that has stopped
  being true is deleted in a commit, not parked in a subfolder — the commit
  keeps it recoverable while keeping it out of the working tree, where a reader
  (human or model) would otherwise mistake it for a specification. The sole
  exception is [`archive/experiments.md`](archive/experiments.md), the concluded-
  experiments record defined in §3.4.
- **Delete on the same change that makes it stale.** A release ships, a plan is
  executed, an approach is abandoned: the document goes then, not later.
- **Intent and behaviour must agree.** If they disagree, that is a defect to
  resolve now — by fixing the code or the doc — not a precedence rule to invoke.
  (This replaces the former "documentation is assumed correct" rule, which is
  what turned 45 story specs into apparent specifications for behaviour that had
  since changed.)
- **No per-feature story spec.** Document a change where a future reader will
  look for it: the contract docs, `CLAUDE.md`, or the experiment's own README.
- **Do not make process state the entry point.** Release status, held tags and
  worklists belong in their own file, never at the top of a README.
- **Measured evidence is not stale.** `experiments/*/README.md` records what was
  tried and what it scored. That stays regardless of age; it is the only honest
  account of what works.
- A contract change that alters a projected file requires a handoff note to the
  downstream consumer.

### 4.1 Release documents — one refinement, one plan

The repository previously ran three parallel refinement tracks at once (core,
the UI rebuild, and UI v2.1). That is banned.

- **One `product-refinement-vX.Y.md` covers the whole release** — core analyzer,
  `ui/`, MCP, and experiments together. A component does not get its own
  refinement document. If work spans components, it spans sections of the one
  document.
- **Exactly one `product-refinement-*.md` may live in `docs/` at a time**, and
  at most one matching `implementation-plan-*.md` beside it. Opening a new
  release means the previous pair is **archived or deleted first**, in the same
  change — never left alongside.
- **Same rule for plans.** No per-component implementation plan, and no second
  plan open in `docs/`.
- The version number lives in the filename and nowhere else that can drift.

The point is that a reader — human or model — should never have to work out
which of several worklists is the live one. There is one, it is in `docs/`, and
superseded ones are gone from the tree.

### 4.2 The issue tracker holds open issues only

[`issues.md`](issues.md) is a queue, not a history.

- **Only `pending` issues live in `issues.md`.** The moment an issue is solved,
  the entry is removed — in the same change that closes it. Closing and removing
  are one action. The closed entry, with its evidence, stays recoverable in the
  commit that closed it.
- **Put the durable part somewhere durable.** If closing an issue established
  something a future reader needs — a contract, a constraint, a measured number
  — write it into the relevant doc or `CLAUDE.md` before deleting the entry. The
  issue text itself is scaffolding.
- **A closed issue is not a quality claim.** It says its own success condition
  was met. Where that condition was narrow — one song, one timestamp — say so on
  the way out, so a stage that passed a narrow gate is never mistaken for a
  stage that works.

The failure this prevents: a 200-line "cumulative work queue" in which every
entry is already closed, where the open work is invisible and the file reads as
a status report on a system that is fine.

---

## 5. Pipeline architecture — four phases

The pipeline runs in four phases. The split is not organisational tidiness: it
is what makes §2 enforceable, because it puts a line in the codebase past which
everything is a claim that can be wrong.

| Phase | Name | Reads | Produces |
| --- | --- | --- | --- |
| 1 | **measure** | audio | facts that cannot be musically wrong — beat grid, loudness, spectra, chroma, stems |
| 2 | **interpret** | phase 1 + audio | claims about the music — chords, key, sections and their names, note and drum events, genre |
| 3 | **relate** | phase 2 only, **never audio** | relations between what phase 2 named — identity, repetition, transitions, phrase structure, composite gestures |
| 4 | **publish** | phases 1-3 | the projected deliverables, and nothing else |

### 5.1 The line between phase 1 and phase 2

It is **not** "DSP versus machine learning". Stem separation, beat tracking and
transcription all use trained models, and excluding them would leave phase 1
empty. The test is:

> **Does this stage assert something that could be musically wrong?**

A loudness curve cannot be wrong; it is a measurement. A chord label can. A
section name can. Measurements go in phase 1, claims in phase 2.

A consequence to honour rather than work around: **chroma extraction and chord
decoding are two stages, not one.** Fusing them makes a chroma bug and a
decoding bug indistinguishable in the artifact, which is exactly the ambiguity
that made past chord issues hard to attribute.

Phase 1 carries no `confidence` field, because there is nothing to be uncertain
about. From phase 2 onward, confidence and provenance are mandatory (§2).

### 5.2 Phase 3 is defined by its input

Phase 3 is *not* "whatever is deterministic post-processing" — chord-pattern
mining is deterministic arithmetic and still belongs here. The rule is
structural: **phase 3 reads phase 2's output and never opens the audio.**

That makes it the layer where the show actually gets its shape: which sections
are the same one returning; that a transition is `chorus → inst`; that a **drop
is derived from a named section pair rather than detected**; that a gesture has
an approach, a build, a tension span, an impact and a release. Inferring a
composite gesture straight from raw features, without the named structure to
hang it on, is the mistake this phase exists to prevent.

### 5.3 Feedback is allowed; mutation is not

Phase 3 will sometimes improve on phase 2 — snapping a boundary to a phrase grid
it derived, for instance. That is permitted, but it **writes a new artifact with
provenance**; it never edits phase 2's output in place. Once a later phase can
silently overwrite an earlier one, it stops being possible to say which stage was
wrong, and the layering has bought nothing.

### 5.4 Phase 4 owns the reach test

Everything projected downstream is published here, and nothing else is published
at all. §1.3 is this phase's acceptance criterion: a signal that reaches no
projected file did not ship, whatever earlier phases computed.

### 5.5 What is not a phase

**Validation and the human/reference loop are orthogonal.** They observe every
phase rather than occupying a position in the sequence, and must not be
interleaved into it as ordinary stages — doing so is what previously scattered
`validate-beats` and `validate-chords` through the middle of extraction. Each
phase's output is scored independently, and human corrections may enter at any
phase, subject to the promotion rules in §2.

### 5.6 Adopting it

Re-filing existing stages is not the point and is not worth doing on its own.
The phases are the shape the rewrite takes: replacement structural inference
lands as phase 2, identity and transitions as phase 3, and code that belongs to
neither is deleted rather than relocated (§10).

## 6. Determinism and reproducibility

- **Same input, same engine version ⇒ byte-identical artifacts.**
- **No hidden state.** All parameters explicit. No opportunistic mid-run
  downloads, no reliance on unversioned external APIs. Model weights resolve
  from the repo-local cache.
- **Seeded randomness.** Any non-deterministic step uses a logged seed.
- **Schemas are versioned.**
- Determinism binds the *pipeline*. Experiments may be exploratory, but a result
  that cannot be reproduced cannot be promoted.

---

## 7. Time

- **Time values are in seconds** (float) in every artifact.
- **Bars are 1-indexed.** Beat- and bar-aligned outputs sit on the canonical
  timing grid.
- **Timeline totality.** Every state-based or frame-based layer covers the song
  from `0.0`. Leading silence is represented as silence, not omitted.
- **Prefer the physical onset.** For structural boundaries, the transient wins
  over the nearest grid position — a cue fired late is a cue missed. Where the
  grid itself is uncertain, say so rather than snapping and implying precision
  that isn't there.

---

## 8. Environment isolation

- **Docker is authoritative.** All analysis, validation and tests run inside the
  project's Compose services. Proposing host-installed Python or audio tooling
  is a constitutional violation.
- **GPU-targeted.** CPU paths are for debugging, not canonical artifacts.
- **Batch runs isolate each song in a subprocess** to prevent GPU and memory
  state contamination between tracks.
- Experiment sandboxes are separate images and must leave the analyzer image
  untouched.

---

## 9. Data governance

- `data/songs/` — source audio. Inputs only.
- `data/analysis/<Song - Artist>/` — the stable deliverable contract. Adding or
  removing a file here is a contract change.
- `data/analysis/<Song - Artist>/artifacts/` — intermediates, in
  producer-scoped subfolders. Read-only to the debugger.
- `data/analysis/<Song - Artist>/reference/` — human and external ground truth.
  The word `reference` is reserved for this. Validation only (see §2).
- **The debugger never writes to `data/analysis/`**, except the two explicit
  human-save paths under `reference/human/`.
- An artifact, once written, is the record of that run.

---

## 10. Change control

- **Musical correctness outranks compatibility.** When the schema, the
  controlled vocabularies, the artifact file set or the downstream projection
  shape stand in the way of a more correct read, propose changing them. Do not
  preserve field names or build compatibility shims unless asked.
- **Judge a proposal by whether it makes the structural read more correct and
  more honestly-confident** — not by whether it adds signals or preserves a
  contract.
- **Delete dead code rather than keeping it working.** A stage with no consumer
  is a liability: it costs maintenance, invites false confidence, and misleads
  every reader about what the system is for.
- **Keep the workspace clean.** Temporary scripts and scaffolding go in a
  scratch directory, never in the repo.
- Any assistant working in this repository is bound by this document, and should
  say so plainly when a request conflicts with it rather than quietly complying.
