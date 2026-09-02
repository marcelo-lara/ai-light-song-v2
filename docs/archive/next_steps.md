> **ARCHIVED — historical record, not a specification.**
> This document describes how something was *planned or built at the time*. It
> is **not** a description of current behaviour and may contradict the code.
> Do not treat it as a contract and do not implement from it: verify against
> `src/` first. For what the system does today, read `CLAUDE.md` at the repo
> root.

# Next Steps

Working checkpoint — where the docs stand and what to pick up next.

**Last updated:** 2026-09-01 · **Branch:** `claude-improvements`

## Where things are

| Track | State |
| --- | --- |
| **v2.1** (analyzer) | Code complete, all items committed. `v2.1` tag **held** on two gates: **D1** gold-set timed labelling, **D2** full-corpus GPU run. See [implementation-plan-v2.1.md](implementation-plan-v2.1.md). |
| **v2.2** (analyzer) | **Planning, in progress.** Refinement doc has release goal + 7 items + 3 bugs + resolved decisions. Not yet turned into an implementation plan. See [product-refinement-v2.2.md](../product-refinement-v2.2.md). |
| **MCP server** (`mcp/`) | **Newly specced.** Product definition + implementation plan written. No code yet. See [mcp-server/](../reference/mcp-server-product-definition.md). |

## v2.2 refinement — current contents

Release goal: make the emitted **drop sequence** match the human model — a full
contiguous `approach → build → tension → impact → release` envelope per drop,
every drop in a multi-drop song detected, impact on the beat. Grounded in the
hand-authored drop-sequence hints now in all four gold tracks'
`reference/human/human_hints.json` (7 sequences, 35 phase hints).

- **Item 1** — deprecate & remove `beatdrop_visual_plan.json` (targets a screen
  visualizer, not moving heads; no consumer reads it).
- **Item 2** — add a pure `song_form` track to the gold set.
- **Items 3–7** — the drop-sequence rebuild: canonical 5-phase envelope,
  impact-instant precision + false-positive suppression, multi-drop recall,
  measured per-phase intensity, and ground-truth/scoring/training fixes for the
  new phase-hint shape.
- **Bugs B1–B3** — concrete defects in `_fold_composites`, the `--compare drops`
  validator, and the ML label mapping, each annotated with its addressing item.

Resolved decisions (do not re-open): composite is pipeline-wide
(`song_event_schema.json` bumped, fold moves into the event-machine stage);
drop-phase hints grouped by adjacency, no new hint field; `approach` is a derived
phase label only, not an event type.

## MCP server — what was decided

- New **`mcp/`** component **in this repo**, Python + official `mcp` SDK, stdio,
  read-only, reads `data/analysis/` directly. The canonical in-repo consumer.
- **Song comprehension only** — mood, sections, dynamics (drops). **Cue
  authoring is permanently out of scope** — that is the separate
  `ai-dmx-light-render` server (`backend/src/app/mcp/`,
  `ai-dmx-light-render/docs/mcp-server-definition.md`). No `cue.` surface is ever
  added here.
- Four tools: `song.list`, `song.dynamics` (whole-song overview, no prose),
  `song.drop_sequence` (one drop's full phase envelope), `song.segment_detail`
  (window / section / drop drill-down). Token-budget rules are contract.
- Open upstream ask: a first-class per-section **mood descriptor** in the
  analyzer (the MCP just projects it) — raise as a v2.2 (or later) refinement
  item if wanted.

## Pick up here

1. **v2.2 direction** — decide: keep adding refinement items (e.g. the mood
   descriptor, a `song_form` track choice), or draft
   `implementation-plan-v2.2.md` now from the 7 items as they stand.
2. **MCP server build** — [mcp-server/implementation-plan.md](mcp-server-implementation-plan.md)
   is ready to execute **outside `/spec-doc`** (or via `/implement`). Phase 0
   first (skeleton + `list_songs` + fixtures).
3. **v2.1 close-out** — D1 and D2 are still open; the `v2.1` tag waits on them.
