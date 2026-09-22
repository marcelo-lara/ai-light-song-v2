# MCP definition — the `mcp/` song-comprehension server

The **third module** of this repository, beside `src/analyzer/` and `ui/`. A
read-only MCP server that helps a reasoning model understand a song's mood,
sections and dynamics — **drop sequences especially** — while spending as few
tokens as possible.

> **Status: built and green — all three tools return real payloads.**
> The stdio/Compose plumbing, song discovery, the exposure guard, the
> fixture-based regression harness (`smoke-test` / `full-regression`, no
> deferrals), the whole-song overview and the on-demand `get_detail` dense read
> are all in place. Shipped in v3.1. The downstream cue-authoring consumer kept
> consuming the published delivery surface rather than migrating to read
> analyzer internals directly — see
> [`reference/downstream-contract.md`](reference/downstream-contract.md) for the
> current contract.

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

Reciprocal boundary statement

- Downstream services (the cue-authoring server and its siblings) must not read
  the `data/analysis/` top-level files directly. They operate on the compact
 , reviewed tool-surface this project publishes. In short: the boundary is
  enforced both ways — this server does not author cues, and downstream cue
  authoring does not reach back into analyzer internals.

Consequence: any top-level signal not published into the delivery surface will
not reach cue authoring. If a signal is kept only in inner artifact folders or
never published at top level, it cannot be consumed by downstream cue authors.
To make a signal available for lighting translation, the analyzer must publish
it as a top-level file (phase 4).
## The exposure rule

> **This server reads `data/analysis/{song}/*.json` and nothing else.**

| Tier | Who may read it |
| --- | --- |
| `data/analysis/{song}/*.json` — top level | `mcp/`, `src/analyzer/`, `ui/` |
| `…/artifacts/**`, `…/reference/**` | **`src/analyzer/` and `ui/` only** |

Inner folders are the raw material phase 4 uses to build the top-level files.
They are never a delivery surface. `mcp/` must contain no path that reaches into
`artifacts/` or `reference/` — a signal only reaches this server by being
published at top level, and that is phase 4's job, not this module's.

**This binds `mcp/` only.** The debugger reads anything under `data/` at any
depth, by design ([`ui-definition.md`](ui-definition.md)); it is a diagnostic
tool, not a delivery surface.

A corollary worth stating: **no top-level file may embed an absolute host path.**
The v3.1 work removed them from `info.json` (`song_path` / `generated_from` /
`artifacts` / `outputs`, item 8) and the published `loudness.json`
(`sources[].path`, item 7). Two top-level files still carry host paths in a
`generated_from` provenance block — `hints.json` and `song_event_timeline.json`
— a pre-existing leak the serializers do not propagate into responses (the
`full-regression` F4.21 check confirms this) but which the publish stage should
strip at source; tracked in [`issues.md`](issues.md). The `artifacts/`
originals keep these internal filesystem details and must never be exposed.

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
{
  "command": "docker",
  "args": ["compose", "run", "--rm", "-T", "mcp"]
}
```

The canonical invocation topology (D3.1) for remote clients is *remote Docker
over SSH*: the caller SSHes to the host running the Compose stack and invokes
Compose there, passing an absolute path to the repository's `docker-compose.yml`.
Example canonical command:

```sh
ssh s2.local -T -- docker compose -f <absolute-repo-path>/docker-compose.yml run --rm -T mcp
```

When the caller and the Compose host are the same machine the equivalent local
invocation is acceptable:

```sh
docker compose -f <absolute-repo-path>/docker-compose.yml run --rm -T mcp
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
`"{song}"` string out of band. It is also what makes the scaffold
end-to-end testable without stubbing a response.

### `get_song_overview(song)`

One call, whole song, small. This is what a concept pass reads before anything
else, and it must stay compact enough to sit in context for the whole session.

Returns:

- **Identity** — `song_name`, `bpm`, `duration`, whole-song `key`, genre with
  its confidence. **v3.6 item 8 dropped `genre.json`'s `guidance` field** (one
  identical text across the whole corpus) — the equivalent guidance is stated
  once in the `get_song_overview` tool's own description instead (see
  `mcp/server.py`), not repeated per song in the response.
- **Grid** — tempo, `beats_per_bar`, `bar_count`, and an **honest downbeat
  note**: how many downbeats carry a `null` confidence, so the caller knows
  whether bar numbers can be trusted on this song. Never the full beat list.
- **Sections** — one compact row each: `section_id`, `start`, `end`, `function`,
  `function_confidence`, `function_status`, `same_label_as`,
  `confidence`. An `"unknown"` `function_status` is surfaced as such, never
  smoothed into a confident label. **v3.6 item 8 dropped `description`**
  (display prose, moved to a debugger-only artifact never read from `mcp/`).
  **v3.6 item 10** adds `energy`, `energy_confidence`, `tension`,
  `tension_confidence` and `rhythm` (per-source subdivision + confidence) —
  present only where a row has one, never a guessed default. See
  `docs/reference/downstream-contract.md`'s "Energy / tension / rhythm clue
  fields" for the precedence rule and per-row `source` overrides.
- **`review_warning`** (present only when needed) — set on the response,
  never per section row, when at least one section in this call's `sections`
  block carries a `seed_unreviewed` source on `energy`, `tension` or any
  `rhythm.<source>`: `{"text": "...", "section_ids": [...]}` naming every
  affected row. Text: *"energy/tension/rhythm sourced `seed_unreviewed` are
  inferred, not yet reviewed by the operator; verify on the final show."*
  Omitted entirely (not `null`) when nothing on the song is seed-sourced.
- **Gestures** — one row per composite gesture, not per phase: its span, its
  peak intensity, its `section_id`, and which phases are present. A song with 31
  impact rows must not return 31 unrelated events.
- **Arrangement** — one row per `arrangement_state` block: who is `playing`,
  who `entered`, who `left`, and the block `confidence` (a leading block carries
  `null`). `arrangement_state.json` is one of the 9 required top-level files
  (v3.6 item 9 dropped the old pre-v3.2 degraded/omitted path) — the block is
  always present. Also carries `vocals_phrase` — a
  second, independent read on the vocals stem from the promoted `whisperx_vad`
  detector (v3.5 item 7, run as its own pipeline service since v3.6 item 2 —
  the `whisperx` Compose service, before `./analyze`): spans where a phrase was
  detected, each with `confidence: 1.0` by operator directive (a detected
  phrase is asserted certain, never graded). `vocals_phrase` is never `null`
  once `arrangement_state.json` exists — publishing fails loudly if the
  `whisperx` service has not been run for that song. Each span additionally
  carries `sibilance` — the
  promoted item-4 stem-bleed discriminator (v3.5 item 4), to be read against
  the sibling `vocals_sibilance_song_mean` rather than absolutely, since the
  cue has a per-song noise floor. A phrase well below the song mean is the
  vocal detector firing on instrument bleed rather than a voice. No gate is
  applied at publish time — the value is reported and the call is the
  consumer's.
- **Transitions** — the `"<from> → <to>"` rows, with times.
- **Human hints** — the operator's own marks, verbatim, with their
  `lighting_hint` where one exists. These are ground truth and outrank every
  inferred field in the response.

### `get_detail(song, section_id=None, gesture_id=None, start_ms=None, end_ms=None, bars=None, interval_ms=None, sources=None)`

On-demand detail for one span. Exactly one scope selector is required — zero or
two is an error, with no precedence rule:

| Scope selector | Span |
| --- | --- |
| `section_id` | that section |
| `gesture_id` | that gesture's full `approach → release` envelope |
| `start_ms` + `end_ms` | an arbitrary window |
| `bars` (v3.7 item 3/5) | `[start_bar, end_bar]`, inclusive, 1-indexed — resolved to `[start_bar beat 1, (end_bar+1) beat 1)` off the published beat grid, tempo-extrapolated where a bar falls outside it |

**The dense-series cap is 5 seconds — a maximum, not a default.** When the
resolved span exceeds 5 s the call returns the structural view (sections,
phases, transitions, hints, drum events, aggregate intensity, the overlapping
`arrangement_state` blocks, `beats`, `stem_summary`, `drum_density` and
`dropouts` — all structural block data, listed with no decimation and present
even when the dense frames are withheld) and **withholds the dense frames**,
saying so explicitly and naming the cap. It never silently truncates, and it
never silently downsamples to fit.

**`stem_summary` (v3.7 item 7).** Per requested stem, `{ peak, mean,
peak_position }` over the resolved span, from `loudness.json`'s
normalized-loudness series. Answers "how loud is X here" without the caller
fetching and hand-averaging multiple capped dense windows — served on every
call, including spans past the 5 s cap, since the cap guards the per-frame
payload, not this fact.

**`beats` (v3.6 item 9)** is the one deliberate exception to "no full beat
list": every beat inside the resolved span — `time`, `bar`, `beat`,
`downbeat_confidence` — scoped, not the whole song's grid, and **not** subject
to either the 5 s dense cap or the `interval_ms` decimation the dense loudness
frames go through. A caller resolving a 6 s window still gets every beat in
that window; it only loses the dense loudness/stem frames.

**`interval_ms` is the caller's choice.** The server decimates the published
series per request; it is not a resolution baked in at publish time. The
published floor is **20 ms** — the finest a caller may request; a finer
`interval_ms` is an error naming the floor, never a silent upsample. Decimation
is chunk-averaging, not frame-dropping, so a transient in the window is not lost.
A concept pass wanting a coarse envelope and a section pass chasing a transient
are the same file read at two resolutions.

`sources` optionally narrows the stem set (mix, drums, bass, harmonic, vocals);
the default is all five.

**`position` (v3.7 item 3/5).** Every time field `get_detail` serializes — the
span itself, section/phase/transition/hint edges, `impact_alignment.
impact_position`, arrangement blocks and vocals phrases (including item 7's
`peak_position`), drum-event rows, `drum_density` bar rows, `dropouts` span
edges, and every dense loudness frame — carries a sibling `position`:
`{"bar", "beat", "section_id", "resolved"}`, derived on read from the
published beat grid; nothing in `src/` stores bars. `resolved: false` marks a
bar derived by tempo arithmetic across a downbeat with `null`
`downbeat_confidence`, rather than read from an actual detected downbeat —
never present a guessed bar as detected. `get_song_overview` deliberately does
**not** carry `position` (its byte budget is load-bearing — see
`docs/issues.md`'s prose-budget issue); a caller wanting bar/beat context for
a specific row fetches it through `get_detail`.

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
