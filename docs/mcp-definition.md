# MCP definition — the `mcp/` song-comprehension server

The **third module** of this repository, beside `src/analyzer/` and `ui/`. An
MCP server that helps a reasoning model understand a song's mood,
sections and dynamics — **drop sequences especially** — while spending as few
tokens as possible.

> **Status: built and green — twelve tools.** Three reads, one proposal
> write (v3.7), two analysis-run tools (v3.8), `get_watcher_status`
> (v3.10) and the structure-hint pair `get_structure_hint_brief` /
> `write_structure_hint` (v3.10 item 7, plus the `structure_hint` prompt) —
> and (v3.11 item 23) the second-pass trio `get_verdict_brief` /
> `write_verdict_pass` / `write_verdict_check` (plus the `verdict_pass` prompt) —
> see "The tool surface". `request_analysis` takes `force` (v3.10).
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

**Second code-scoped write (v3.10 item 7).** `write_structure_hint` writes
one file, `reference/pre-analysis/structure.json`, in a song's inner folder
(created on demand, so it works before a first run). It lives in
`mcp/structure_hint.py` with the path components split as separate string
literals, and the tool descriptions avoid inner-folder paths, so
`test_exposure.py` and smoke S4.10 stay unchanged and green. S4.11 now asserts
the `/data` mount is writable for these bounded writers; the boundary itself is
held by code, not the mount.

**Third and fourth code-scoped writes (v3.11 item 23).** `write_verdict_pass`
writes only the `second_pass` block of `reference/pre-analysis/verdict.json`;
`write_verdict_check` appends only to the proposals queue. Both live in
`mcp/verdict.py` (queue helpers in `mcp/proposals.py`) with path components as
separate string literals, so `test_exposure.py` and smoke S4.10 stay unchanged
and green. Neither edits the hint, the first-pass `version_check` / `verdicts`
blocks or any analysis file; `get_verdict_brief` only reads the verdict file and
the queue. `test_verdict.py` asserts that a pass plus a check change nothing but
`verdict.json` and `pending.json`.

**D3.1 exception (v3.8 item 3).** `request_analysis`/`get_analysis_progress`
write/read `_run_request.json`/`_run_progress.json`, one level under a song's
directory — a bounded, documented exception to the top-level-only exposure
rule, same shape as `propose_hint`'s queue file
(v3.7 item 10). Both files are operational run state (who is running
`./analyze` and how far it got), never analysis, and are never promoted to a
top-level file. Kept in its own module, `mcp/runs.py`, path components split
as separate string literals exactly as `proposals.py` does, so
`test_exposure.py`'s literal-substring grep stays unchanged and green.

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

The ten required top-level files (`mcp/loaders.py` `REQUIRED_TOP_LEVEL_FILES`; a
missing one errors naming it, no degraded mode): `info.json`, `beats.json`,
`hints.json`, `sections.json`, `song_event_timeline.json`, `drum_events.json`,
`loudness.json`, `arrangement_state.json`, `vocal_cadence.json`, and — v3.12
item 33 — `bar_features.json` (per-bar texture; projected through the tools by
item 34, not yet a tool field).

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
| Writes | **read-only, with bounded exceptions:** `propose_hint` (v3.7) appends to a song's own inner-folder proposals queue file — never a top-level file, never the operator's own hand-authored file (see "Correction proposals"); `request_analysis` (v3.8) writes only `artifacts/_run_request.json` (see `request_analysis` / `get_analysis_progress`); `get_watcher_status` (v3.10) reads `data/analysis-watcher.heartbeat`; `write_structure_hint` (v3.10 item 7) writes only `reference/pre-analysis/structure.json` (see "Pre-analysis structure hint"); `write_verdict_pass` (v3.11 item 23) writes only the `second_pass` block of `reference/pre-analysis/verdict.json`; `write_verdict_check` appends a `verdict_check` row to the proposals queue (see "Second pass over the verdicts") |
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

Two substantive read capabilities — overview and detail — plus the trivial
discovery call they both need, (v3.7 item 10) one write tool that only ever
queues a correction for human review, and (v3.8 item 3) two tools that let the
caller request and poll a run for a song it cannot see yet, and (v3.10 item 7)
two tools for the pre-analysis structure hint, and (v3.10 item 11)
`get_watcher_status`, and (v3.11 item 23) the second-pass trio. Twelve tools, plus the `structure_hint` and `verdict_pass` prompts. Everything else is out of scope for v1.

**Not on this surface:** the v3.10 experiments `filter_sweep`, `phrases`,
`downbeat_anchors` and `section_names` (measured on the whole corpus, none
shipped; see [`analysis-definition.md`](analysis-definition.md)). Their
`reference/proposals/*.json` outputs are never read by any tool here and
`get_song_overview` / `get_detail` carry no field derived from them. A promotion
would first publish the signal into a top-level file (the reach test) and then
list it in the tool sections below.

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

- **Identity** — `song_name`, `bpm`, `duration`. **v3.10 item 8 removed** the
  whole-song `key` and the genre block (`genre.json` is no longer published).
- **Grid** — tempo, `beats_per_bar`, `bar_count`, and an **honest downbeat
  note**: how many downbeats carry a `null` confidence, so the caller knows
  whether bar numbers can be trusted on this song. Never the full beat list.
- **Sections** — one compact row each: `section_id`, `start`, `end`, `function`,
  `function_confidence`, `function_status`, `same_label_as`,
  `confidence`. An `"unknown"` `function_status` is surfaced as such, never
  smoothed into a confident label. **v3.6 item 8 dropped `description`**
  (display prose, moved to a debugger-only artifact never read from `mcp/`).
  **v3.10 item 8 removed** `key`, `energy`, `tension`, `rhythm`,
  `impact_alignment` and their `*_confidence`/`*_source` fields from the rows,
  and the response-level `review_warning`.
- **Gestures** — one row per composite gesture, not per phase: its span, its
  peak intensity, its `section_id`, and which phases are present. A song with 31
  impact rows must not return 31 unrelated events.
- **Arrangement** — one row per `arrangement_state` block: who is `playing`,
  who `entered`, who `left`, and the block `confidence` (a leading block carries
  `null`). `arrangement_state.json` is one of the 10 required top-level files
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
- **Vocal cadence** (v3.9 item 1) — a whole-song `vocal_cadence` block
  (`source`, `reason`, total `call_count`), plus four compact fields folded
  onto each `sections` row: `lead_in_bars` (the downbeat a section's first
  line resolves on, in whole bars relative to the boundary — 0 = on the hit,
  -1 = a bar early), `rest_count`, `call_count` (calls inside that section's
  own span), and `cadence_repeat_best` (`{section_id, bar_offset}` of the
  highest-scoring earlier section this one's vocal cadence repeats, or
  `null`). Timing only — no lyric text anywhere. `source: null` (D1.1, no
  lyrics tier) still returns the block with `reason` set and every row's
  fields omitted — `vocal_cadence.json` is one of the 10 required top-level
  files, no degraded/absent path. The full per-section detail (`rests[]`,
  `held_notes[]`, `tokens_per_bar[]`, every `cadence_repeats[]` candidate) is
  `get_detail`'s job, not this one — see below.

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
`arrangement_state` blocks, `vocal_cadence` (v3.9 item 1 — the section
row(s)/lines/calls overlapping the span, at full detail: `rests[]`,
`held_notes[]`, `tokens_per_bar[]`, every `cadence_repeats[]` candidate), `beats`,
`stem_summary`, `drum_density` and `dropouts` — all structural block data,
listed with no decimation and present even when the dense frames are withheld)
and **withholds the dense frames**,
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
that window; it only loses the dense loudness/stem frames. It also carries
`off_grid_spans` (v3.9 item 3) — the published `beats.json` spans overlapping
the resolved window, `[]` when none do.

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
span itself, section/phase/transition/hint edges, arrangement blocks and vocals phrases (including item 7's
`peak_position`), drum-event rows, `drum_density` bar rows, `dropouts` span
edges, and every dense loudness frame — carries a sibling `position`:
`{"bar", "beat", "section_id", "resolved"}`, derived on read from the
published beat grid; nothing in `src/` stores bars. `resolved: false` marks a
bar derived by tempo arithmetic across a downbeat with `null`
`downbeat_confidence`, rather than read from an actual detected downbeat —
never present a guessed bar as detected. **v3.9 item 3**: `resolved` is also
`false` for a time falling inside one of `beats.json`'s `off_grid_spans` —
same honesty rule, the other way a bar number can be wrong (the tracker left
the constant-tempo grid there, not just the downbeat phase). `get_song_overview` deliberately does
**not** carry `position` (its byte budget is load-bearing — see
`docs/issues.md`'s prose-budget issue); a caller wanting bar/beat context for
a specific row fetches it through `get_detail`.

### Correction proposals — `propose_hint` (v3.7 item 10)

The one proposal write path this server has, and it never touches the surface above.

- `propose_hint(song, start, end, title, summary, evidence)` — a new hint,
  queued.

It **appends** to a queue file one level under the song directory — an inner
folder, so nothing written there is exposed by `list_songs`,
`get_song_overview` or `get_detail`. The tool never writes the operator's
own hand-authored file, and never mutates a top-level published file.
`evidence` is required: an empty or missing value is a rejected error,
and nothing is written — no silent no-op.

Turning a queued proposal into a real, published value is entirely the
debugger UI's job: an operator reviews it there, and approval writes the
change through the UI's existing write path for that file. The UI does not
trigger the analyzer stage that republishes it — it has no Docker access —
so it shows a reminder naming the `--stage` the operator runs by hand, same
as any other `reference/human/` edit. A rejection is kept, with its reason,
so the same proposal is not re-queued. This server never approves, rejects,
or reads back its own queue — it only appends to it.

**Why a queue and not a direct write.** A human-set field outranks every
inferred field *because a person set it*. A tool that wrote the operator's own
file directly would make that provenance mean "whoever called the tool last,"
which dissolves the one precedence rule the rest of the system trusts.

### Second pass over the verdicts — `get_verdict_brief` / `write_verdict_pass` / `write_verdict_check` (v3.11 item 23)

After the `hint-verdict` stage (`verdict.json`'s `verdicts.fields`), the client
re-reads the audio for every `refuted` / `unresolved` verdict. The audio
outranks the web: a source's answer settles a verdict only together with audio
evidence that does not contradict it. Needs a verdict file; without one every
tool errors (no hint, or the stages have not run).

- `get_verdict_brief(song)` returns `{brief, status, reason, verdicts}`. `brief`
  is the instructions verbatim (also the MCP prompt `verdict_pass`): per verdict
  read stem entries/exits, `drum_density`, `dropouts` and loudness through
  `get_detail`, run one targeted web search for that claim on the audio's
  version, then answer or queue. `verdicts` is one row per first-pass
  `refuted` / `unresolved` field:
  `{field, verdict, evidence, second_pass, check, operator}` where `evidence`
  is the first-pass evidence, `second_pass` is `null` or `{verdict, wrong,
  evidence}`, `check` is `null` or `{id, status, rejection_reason}` (the queued
  `verdict_check`), `operator` is `null` or the operator's answer (below).
  `status` / `reason` echo `verdicts.status` / `.reason` (a `skipped` block has
  no rows).
- `write_verdict_pass(song, results)`: `results` is `{field: {verdict, wrong,
  evidence}}`, `field` one of `drops`, `has_build_ups`, `chorus_is_drop`,
  `vocals`, `bpm`. `verdict` is `confirmed` (`wrong: null`) or `refuted` with
  `wrong: "hint" | "analysis"`. The verdict judges the analysis' agreement with
  the hint: when the hint's claim holds in the audio but the analysis lacks the
  labelling, record `refuted` + `wrong: "analysis"`, not `confirmed` (the brief
  says so). `evidence` is `{stems, drum_density, dropouts,
  loudness, web_search}`: the four audio kinds are required, each `{read,
  showed}` (non-empty strings; section ids, never times); `web_search` is
  `{read, showed}` or `null`, and never settles a verdict by itself because the
  audio kinds are mandatory. Refused, nothing written (all-or-nothing across
  `results`), on: an unknown field or key, any time-bearing key name, missing or
  empty evidence, a first-pass verdict that is not `refuted` / `unresolved`, a
  `verdict` that is not `confirmed` / `refuted`, `wrong` missing on `refuted` or
  set on `confirmed`, a claim the operator already answered.
- `write_verdict_check(song, field, claim, evidence, cannot_settle, question)`:
  queues a `verdict_check` for a verdict that stays unanswerable. `evidence`
  has the four audio kinds **and** `web_search`, each `{read, showed}`. Refused,
  nothing written, when `claim`, `cannot_settle`, `question`, any evidence kind
  or any `read` / `showed` is missing or empty, a key names a time, the field's
  first-pass verdict is not `unresolved`, the field is already settled by a
  second pass or answered by the operator, or a `verdict_check` for that field
  is already queued, approved or **rejected** (a rejection is never re-queued).

**Queue row** (`reference/proposals/pending.json`, new `type` beside `hint`):
`{id, type: "verdict_check", status: "pending", created_at, rejection_reason:
null, evidence: <cannot_settle text>, verdict_check: {field, claim, evidence,
cannot_settle, question}}`. The one claim key is the verdict `field`. `question`
is phrased so the operator can answer yes/no about the claim.

**Stored second pass** (`verdict.json`, sibling of `version_check` / `verdicts`,
untouched by those stages): `second_pass: {fields: {<field>: {verdict, wrong,
evidence, first_pass_verdict, operator}}}`. `verdict` / `wrong` / `evidence` /
`first_pass_verdict` are `null` until a pass is written; `operator` is `null`
until answered. `operator` (written by the debugger's approve flow, never by
this server) is `{answer: "confirmed" | "rejected", reason: string | null,
check_id}`: `confirmed` = the operator says the hint's claim holds, `rejected` =
it does not (`reason` required). An entry holding only `operator` is valid. The
queue row's `status` flips to `approved` / `rejected` by the same flow.

### `request_analysis` / `get_analysis_progress` (v3.8 item 3)

Let the caller start and poll a full `./analyze` run for a song it cannot see
yet, reusing the same request/progress files the debugger's **Run analysis**
button writes/reads (v3.8 item 1/2) — one mechanism, not two, regardless of
which surface started the run. The host-side `./analysis-watcher` (item 1) is
what actually runs the analyzer; this server only writes the request and
reads the progress.

- `request_analysis(song, force=False)` — fully analysed already
  (`resolve_song_dir` succeeds) → refused, pointing at
  `get_song_overview`/`get_detail` (or `force=True`) instead of starting a
  redundant run. `force=True` skips only that refusal, to re-run an analysed
  song deliberately (the debugger's **Run analysis** button does the same);
  every other rule below still applies, audio included. A `queued`/`running` progress already in flight →
  that progress is returned, no new request written. No real `<song>.mp3`
  under the songs root (missing, **or present but 0 bytes** — the real mount
  carries ~14 zero-byte `authoring-*.mp3` placeholders a run would be
  guaranteed to fail against) → refused, listing every stem that is both
  non-empty audio and not already fully analysed (excludes size-0
  placeholders and songs that already have a complete analysis directory —
  the only way the caller can discover a legal `song` argument for a song
  `list_songs` doesn't know about yet). Otherwise writes the request and
  returns immediately — `{"status": "requested", "song", "requested_at",
  "watcher": "up" | "down", "poll_with": "get_analysis_progress",
  "poll_every_s": 60, "note": "..."}` — never blocking on the run. `watcher`
  (also added to the in-flight progress it may return instead) is
  `get_watcher_status`'s `status`: `down` means nothing will pick the
  request up until `./analysis-watcher` runs on the host.
- `get_analysis_progress(song)` — once the watcher has written a progress
  file, its fields are returned verbatim (`status`: `queued`/`running`/
  `done`/`failed`, `stage`, timestamps, `error`). Before that: a fresh
  request reports `queued`; a request older than 120 s with still no
  progress file reports `not_started` (no-silent-fallbacks — nothing is
  watching this, not an indefinite wait). Neither file present → refused,
  pointing at `request_analysis`.

### `get_watcher_status` (v3.10 item 11)

`get_watcher_status()` → `{status: "up" | "down", last_heartbeat, age_s}`.
`./analysis-watcher` rewrites `data/analysis-watcher.heartbeat` (one ISO-8601
UTC timestamp) every poll interval, including while a job runs. `down` when
the file is missing or unparseable (`last_heartbeat` and `age_s` are then
`null`) or older than 3 poll intervals. The server reads it from the analysis
root's parent (`MCP_WATCHER_HEARTBEAT` overrides the path; `MCP_WATCHER_POLL_S`,
default 2, must match the watcher's `ANALYSIS_WATCHER_POLL_S`). It never
starts the watcher — that needs host process control, and the Docker-socket
grant was rejected (v3.7 D11.1); `analysis-watcher.service` keeps it up
(`docs/reference/docker.md`). The heartbeat is operational state like
`_run_progress.json`, never a top-level song file.

Mount (D3.2): the `mcp` service gets the songs directory read-only
(`MCP_SONGS_ROOT`, default `/data/songs`) so `request_analysis` can check for
audio before queuing a run guaranteed to fail — it never reads the audio
file's contents, only its size (`> 0`) and whether it exists.

### Pre-analysis structure hint — `get_structure_hint_brief` / `write_structure_hint` (v3.10 item 7)

A web-researched prior about a song's version, genre and expected shape,
generated by the client (Claude) when a song is added. The analysis reads it
as a prior only; it never outranks the audio, so it is written directly, not
queued.

- `get_structure_hint_brief(song)`: returns `{brief, existing}`, where
  `brief` is the instructions verbatim (also published as the MCP prompt
  `structure_hint`, one implementation, no paraphrase) and `existing` is the
  stored hint or `null`. The brief has the client research the song, fill
  the schema below and call `write_structure_hint`. It never writes times,
  sections or hints.
- `write_structure_hint(song, hint)`: validates `hint` against the schema
  and writes only `<song>/reference/pre-analysis/structure.json`, replacing
  any earlier one. An invalid payload is refused naming the first bad field,
  and nothing is written.
- Both accept any song `request_analysis` would accept (real audio under
  the songs root) as well as analysed songs: the hint is meant to exist
  before the first run.

**Schema** (`schema_version: "1.1"`; a stored `1.0` hint stays readable through `existing` but `write_structure_hint` refuses it until re-written as `1.1`). Unknown → `null`, never a bare guess; a derived value is allowed only labelled `inferred` with a quote. No
timestamps anywhere: web sources describe other versions, and an invented
time is worse than none.

| Field | Type | Values |
| --- | --- | --- |
| `schema_version` | string | `"1.1"` |
| `song_name` | string | the song folder name |
| `generated_at` | string | ISO date |
| `track.artist`, `track.title` | string | as researched |
| `track.version` | enum \| null | `radio_edit`, `extended`, `club_mix`, `remix`, `original` |
| `track.remixer` | string \| null | |
| `track.version_duration_s` | number \| null | the researched version's length. The pipeline compares it with `info.json`'s duration and ignores `track.version` and `shape` on a mismatch |
| `genre.family` | enum | `edm`, `pop_edm`, `pop`, `rock`, `other` |
| `genre.subgenre` | enum \| null | `big_room`, `house`, `techno`, `trance`, `dubstep`, `drum_and_bass`, `other` |
| `genre.bpm` | number \| null | researched, not measured |
| `shape.drops` | `{value, basis, source, quote}` | `value`: integer \| null, expected number of drops |
| `shape.chorus_is_drop` | `{value, basis, source, quote}` | `value`: bool \| null, a sung chorus takes the drop's place |
| `shape.has_build_ups` | `{value, basis, source, quote}` | `value`: bool \| null |
| `shape.vocals` | enum \| null | `none`, `chops`, `full` |
| `confidence` | number 0–1 | overall |
| `sources` | list of `{url, title}` | at least one; a chat-assistant answer is not a source |

Evidence fields (`shape.drops`, `chorus_is_drop`, `has_build_ups`):
`basis` is `stated` (a source says it) or `inferred` (derived from stated
facts); `source` is an integer index into `sources[]`; `quote` is a non-empty
supporting sentence. A non-null `value` without a valid `basis`, `source`
index and `quote` is refused naming the field. `value: null` requires
`basis`, `source` and `quote` all `null`. `quote` is a value, never a time
key: the no-time-key scan covers every key name. `shape.vocals` stays a plain
enum \| null.

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
