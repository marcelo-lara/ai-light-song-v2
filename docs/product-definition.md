# Product definition — what this system is for

The **why**. What the three-part system is, what this repository owns inside it,
and what "good" means for the thing we emit. Rules are in
[`../CLAUDE.md`](../CLAUDE.md) "Rules that are load-bearing"; the pipeline itself is in
[`analysis-definition.md`](analysis-definition.md).

## The three parts

```
  data/songs/*.mp3
        │
        ▼
  ┌──────────────────────┐   data/analysis/{song}/
  │ 1. ANALYSIS  (here)  │ ─────────────────────────────────►┐
  │  src/ + ui/          │   8 top-level files + artifacts/  │
  └──────────────────────┘                                   │
                                                             ▼
                                          ┌──────────────────────────────┐
                                          │ 2. MCP SERVER  (here, mcp/)  │
                                          │  token-budgeted projections  │
                                          └──────────────────────────────┘
                                                             │
                                                             ▼
                                          ┌────────────────────────────────┐
                                          │ 3. CUE AUTHORING  (other repo)  │
                                          │  a model + ai-dmx-light-render  │
                                          │  → moving-head light show       │
                                          └────────────────────────────────┘
```

**This repo owns parts 1 and 2** — the analysis and the read-only
song-comprehension MCP server over it. It turns a song into structured musical
analysis and projects token-budgeted views of it. It never sees a fixture, a
rig, a cue or a DMX universe; that is part 3, in `ai-dmx-light-render`.

**Part 2 is the only path from analysis to cue authoring.** As of v3.3 the
downstream server no longer reads `data/analysis/` at all — it deleted its own
`get_analysis*` tools, `song://` resources and the windowed `artifacts/` door.
There is no second route to a musical fact: a signal phase 4 does not publish at
top level, and this server therefore cannot project, reaches the light show
nowhere. The reciprocal boundary is stated in
[`mcp-definition.md`](mcp-definition.md).

The lighting target is **moving-head fixtures**, which is why gestures with
internal phases matter more than isolated events: a moving head needs to know it
has eight bars to travel, not just that something loud happened.

## What we owe the authoring model

The reader is a reasoning model that **cannot listen to the song** and is billed
per token. Everything follows from that.

### 1. Named structural parts and their transitions

`intro → verse`, part A → part B. **Knowing something is *different* at a given
instant is what defines a cue.** A boundary two seconds late is a cue that fires
on the wrong bar.

### 2. Composite gestures with internal phases

A drop has an approach, a build, a tension span, an impact and a release. Each
maps to a different scene. A flat list of independent events loses exactly the
thing that matters. A phase we cannot support with evidence is **absent**, never
guessed.

### 3. Character, not only arrangement

A verse/chorus label is not the only thing worth emitting, and often not the
most valuable. What earns a cue is frequently a block's *character*: vocal-led
and low intensity, drums out, sparse and atmospheric, dense and driving.

The operator hand-marks these. `Armin - Revolution` `hint-006` is titled
**"Breath"** — 81.4–96.3 s, *"Vocal - no intense section"* — with the lighting
hint *"soft motion of moving heads, parcans slow violet waves."* That is a
texture fact, not a verse/chorus fact, and **no shipped artifact carries it
today** (see [`analysis-definition.md`](analysis-definition.md) "Known gaps").

### 4. How the parts relate

Which section is the same one returning, which is the biggest, which is the
quietest. This is also **not shipped honestly yet** — `same_label_as` reports
label repetition, not acoustic identity.

### 5. Honest uncertainty

An `unknown` costs the reader nothing. A confident wrong answer costs them the
show. See the honesty rules in [`../CLAUDE.md`](../CLAUDE.md).

## The acceptance test

> **A signal that cannot be stated compactly, with a time and a confidence, is
> not yet a deliverable.**

And its companion, the **reach test** (the reach test — docs/mcp-definition.md): a feature is only
real if it lands in a file the MCP server actually projects. The list is in
[`mcp-definition.md`](mcp-definition.md). Improving an artifact nothing projects
changes nothing about the show.

## Out of scope

| Not ours | Whose |
| --- | --- |
| Which fixture does what, when, in what colour | part 3 |
| Cue lists, lighting-design documents, DMX | part 3 |
| Rig configs, fixture lists, POIs, `.cue.json` | part 3 |
| Screen visualizers | nobody — deleted 2026-09-02 |

Part 2 — the `mcp/` server's token-budgeted projection shape — **is** ours, and
is covered by [`mcp-definition.md`](mcp-definition.md). Its hard boundary is the
same as part 1's: it describes the music and never authors a cue.

`lighting_score.md`, `lighting_events.json`, `beatdrop_visual_plan.json` and
their three stages were removed on 2026-09-02. None had a consumer;
`data/fixtures/` never existed. **Do not reintroduce them**, and do not justify
work by appealing to fixture orchestration.

## The standing priority

**Musical correctness outranks compatibility.** Improving the quality of the
musical read beats preserving the artifact schema, field names, file set, or the
MCP server's exact projection shape. When the existing shape gets in the way of
a more correct interpretation, propose changing the shape — do not build a
workaround. Judge a proposal by whether it makes the structural read more
correct and more honestly-confident, not by whether it adds signals.
