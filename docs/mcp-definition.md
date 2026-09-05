# MCP definition — the `mcp/` song-comprehension server

The **third module** of this repository, beside `src/analyzer/` and `ui/`. A
read-only MCP server that helps a reasoning model understand a song's mood,
sections and dynamics — **drop sequences especially** — while spending as few
tokens as possible.

> **Status: specified, not built.** No `mcp/` directory exists yet. The plan is
> [`implementation-plan-v3.1.md`](implementation-plan-v3.1.md), whose **first
> item is the scaffold** — the module, its Compose service and a proven stdio
> round-trip — so the plumbing is validated before any data work.

- How to prove it still works: [`reference/mcp-regression.md`](reference/mcp-regression.md)
- What the analyzer produces for it: [`analysis-definition.md`](analysis-definition.md)
- Field detail for every file it reads: [`reference/artifacts.md`](reference/artifacts.md)
- The *other* server, in another repo: [`reference/downstream-contract.md`](reference/downstream-contract.md)

## What it is for

A model authoring a light show cannot listen to the song, and pays per token for
everything it learns. This server is the narrow interface that lets it ask
precise questions and get small, honest answers.

It exists to answer three things:

1. **What is the shape of this song?** Its parts, their names, how confident we
   are in those names, and how they relate.
2. **Where are the drops, and what is their internal shape?** The
   `approach → build → tension → impact → release` envelope, with times and
   intensities, so a moving head knows it has eight bars to travel.
3. **What exactly is happening at this instant?** Dense loudness and drum
   detail for a short window, at a resolution the caller picks.

## The hard boundary

**Cue authoring is permanently forbidden to this server.** Proposing, writing or
validating `.cue.json`; reading a rig config, a fixture list or POIs; emitting
any fixture-aware output; DMX of any kind.

This is not "v1 of" something that later grows a `cue.` surface. That work
belongs to `ai-dmx-light-render`. If a request would add fixture or cue
capability here, the answer is that it goes in the other repo — see
[`product-definition.md`](product-definition.md) for why the split exists.

The server describes the *music*. A downstream host owns the lighting
translation.

## The exposure rule

> **This server reads `data/analysis/<Song - Artist>/*.json` and nothing else.**

| Tier | Who may read it |
| --- | --- |
| `data/analysis/<Song - Artist>/*.json` — top level | `mcp/`, `src/analyzer/`, `ui/` |
| `…/artifacts/**`, `…/reference/**` | **`src/analyzer/` and `ui/` only** |

Inner folders are the raw material phase 4 uses to build the top-level files.
They are never a delivery surface. `mcp/` must contain no path that reaches into
`artifacts/` or `reference/` — a signal only reaches this server by being
published at top level, and that is phase 4's job, not this module's.

**This binds `mcp/` only.** The debugger reads anything under `data/` at any
depth, by design ([`ui-definition.md`](ui-definition.md)); it is a diagnostic
tool, not a delivery surface.

A corollary worth stating: **no top-level file may embed an absolute host path.**
Several do today (`info.json`'s `song_path` / `generated_from` / `artifacts` /
`outputs`, `rms_loudness.json`'s `sources[].path`). Those are internal
filesystem details and must not cross to a delivery surface.

## Runtime

| | |
| --- | --- |
| Language | Python |
| SDK | the official `mcp` package |
| Transport | stdio |
| State | none — reads `data/analysis/` on each call |
| Writes | **none, ever.** Read-only against the whole tree |
| Container | its own Compose service; never the analyzer image |

Song discovery is by directory name under `data/analysis/`, the same key the
debugger uses.

### How a client invokes it

A stdio server is **spawned by its client**, so there is no `docker compose up`
for this service. The client's MCP config names the command:

```json
{ "command": "docker",
  "args": ["compose", "run", "--rm", "-T", "mcp"] }
```

`-T` is mandatory — without it Compose allocates a TTY and corrupts the stdio
framing. The container lives for the session and exits with it.

## The tool surface

Two substantive capabilities — overview and detail — plus the trivial discovery
call they both need. Everything else is out of scope for v1.

### `list_songs()`

Every analysable song directory under `data/analysis/`, with `song_name`, `bpm`
and `duration`. Deliberately trivial, and not optional: a client cannot guess
directory names, and without this the caller must be told the exact
`"<Song - Artist>"` string out of band. It is also what makes the scaffold
end-to-end testable without stubbing a response.

### `get_song_overview(song)`

One call, whole song, small. This is what a concept pass reads before anything
else, and it must stay compact enough to sit in context for the whole session.

Returns:

- **Identity** — `song_name`, `bpm`, `duration`, whole-song `key`, genre with
  its confidence and its `guidance` prose.
- **Grid** — tempo, `beats_per_bar`, `bar_count`, and an **honest downbeat
  note**: how many downbeats carry a `null` confidence, so the caller knows
  whether bar numbers can be trusted on this song. Never the full beat list.
- **Sections** — one compact row each: `section_id`, `start`, `end`, `function`,
  `function_confidence`, `function_status`, `same_label_as`, `description`,
  `confidence`. An `"unknown"` `function_status` is surfaced as such, never
  smoothed into a confident label.
- **Gestures** — one row per composite gesture, not per phase: its span, its
  peak intensity, its `section_id`, and which phases are present. A song with 31
  impact rows must not return 31 unrelated events.
- **Transitions** — the `"<from> → <to>"` rows, with times.
- **Human hints** — the operator's own marks, verbatim, with their
  `lighting_hint` where one exists. These are ground truth and outrank every
  inferred field in the response.

### `get_detail(song, scope, interval_ms=None, sources=None)`

On-demand detail for one span. `scope` selects it, exactly one of:

| Scope | Span |
| --- | --- |
| `section_id` | that section |
| `gesture_id` | that gesture's full `approach → release` envelope |
| `start_ms` + `end_ms` | an arbitrary window |

**The dense-series cap is 5 seconds — a maximum, not a default.** When the
resolved span exceeds 5 s the call returns the structural view (phases,
transitions, hints, aggregate intensity) and **withholds the dense frames**,
saying so explicitly and naming the cap. It never silently truncates, and it
never silently downsamples to fit.

**`interval_ms` is the caller's choice.** The server decimates the published
series per request; it is not a resolution baked in at publish time. The
published floor is **20 ms** — the finest a caller may request. A concept pass
wanting a coarse envelope and a section pass chasing a transient are the same
file read at two resolutions.

`sources` optionally narrows the stem set (mix, drums, bass, harmonic, vocals);
the default is all five.

## Honesty obligations

The server inherits the analyzer's honesty rules and must not launder them:

- **Never invent a value to fill a field.** An absent gesture phase means no
  supporting primitive was found. A `null` downbeat confidence means the bar
  phase is unresolved. Both are passed through as-is.
- **Confidence stays a separate numeric field**, never folded into a display
  string and never inflated.
- **`function_status: "unknown"` is surfaced**, not hidden behind the label.
- **`same_label_as` is label repetition, not acoustic identity.** Any response
  grouping sections must carry that caveat rather than implying verified
  identity.
- **A drop is never named directly** — it appears as gesture phases anchored on
  a detected impact, or as a section-pair transition.
- **`source` is passed through, never dropped to save tokens.** Published values
  are fused from several producers and the winner varies per song and per row, so
  a value without its source is a value the caller cannot weigh. Where a file
  declares its producers in a header, the server may summarise them once per
  response rather than repeating them per row — but it may not discard them.
- **A confidence is reported against the thing it measures.** `beats.json`'s
  confidence qualifies the downbeat phase, not the beat time; a response that
  implies otherwise is wrong even if every number in it is copied correctly.

## Keeping it in sync

Because this consumer is in-tree, an analyzer change that reshapes a top-level
file **updates this module's serializer and its golden snapshots in the same
commit**, and the tests fail if the projection drifts. That is the advantage of
having it here rather than downstream: contract drift becomes a failing test
instead of a handoff note.

The external cue-authoring server is still remote, so a reshape affecting *its*
read surface additionally needs a handoff note — see
[`reference/downstream-contract.md`](reference/downstream-contract.md).
