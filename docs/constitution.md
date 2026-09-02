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

---

## 4. Documentation

- **`docs/` holds current material only.** Everything in it describes how the
  system is meant to behave now, and is kept in sync with the code. There is no
  archive folder: **git history is the archive.** A document that has stopped
  being true is deleted in a commit, not parked in a subfolder — the commit
  keeps it recoverable while keeping it out of the working tree, where a reader
  (human or model) would otherwise mistake it for a specification.
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

## 5. Determinism and reproducibility

- **Same input, same engine version ⇒ byte-identical artifacts.**
- **No hidden state.** All parameters explicit. No opportunistic mid-run
  downloads, no reliance on unversioned external APIs. Model weights resolve
  from the repo-local cache.
- **Seeded randomness.** Any non-deterministic step uses a logged seed.
- **Schemas are versioned.**
- Determinism binds the *pipeline*. Experiments may be exploratory, but a result
  that cannot be reproduced cannot be promoted.

---

## 6. Time

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

## 7. Environment isolation

- **Docker is authoritative.** All analysis, validation and tests run inside the
  project's Compose services. Proposing host-installed Python or audio tooling
  is a constitutional violation.
- **GPU-targeted.** CPU paths are for debugging, not canonical artifacts.
- **Batch runs isolate each song in a subprocess** to prevent GPU and memory
  state contamination between tracks.
- Experiment sandboxes are separate images and must leave the analyzer image
  untouched.

---

## 8. Data governance

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

## 9. Change control

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
