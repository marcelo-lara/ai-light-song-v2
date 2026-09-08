# Product refinement — v3.3

**Status: complete (implemented and container-validated, 2026-09-08).** A scoped worklist of concrete refinements,
collected item by item. This is the first versioned refinement doc in this
repository — v3.0–v3.2 ran from implementation plans directly — and it adopts
the convention the downstream repo uses: numbered items, each landing in
[`mcp-definition.md`](mcp-definition.md) once implemented and verified. Nothing
here is done by writing it down.

**v3.3 is scoped to the `mcp/` module.** No analyzer stage, no debugger UI, no
new signal. Every item below projects material the pipeline already produces;
where an item needs a field that does not exist yet, that is called out as a
dependency rather than smuggled in.

---

## The one change

**This server becomes the only song-comprehension surface for cue authoring.**

The downstream cue-authoring server is removing its song-analysis block whole —
`get_analysis`, `get_analysis_detail`, `get_song_brief`, the `song://`
resources, the windowed `artifacts/` door, and its `data/analysis` mount. See
[`ai-dmx-light-render/docs/product-refinement-v1.5.md`](../../ai-dmx-light-render/docs/product-refinement-v1.5.md).
Claude Desktop connects to both servers; song facts come from this one, the rig
and the cues from that one.

That is the outcome [`product-definition.md`](product-definition.md)'s three-part
diagram always described and the exposure rule always implied. v3.3 is what
makes it true in practice.

### What it costs us

The consumer's `artifacts/` reader was, in effect, an escape hatch. When a
projection here was thin, an authoring session could reach past it into
`rms_loudness.json` and `drum_events.json` directly. That hatch is closing.

**From v3.3 on, a projection gap here is an authoring gap with no fallback.**
That raises the bar on this module in one specific way, and every item below is
a consequence: the things a cue author cannot get wrong are *what* is lit and
*when* it lands, and both of those are questions only this server can now
answer.

### A measured baseline first

Item 0, before anything else is built. The downstream repo's v1.4 release was
shaped by measuring its own calls, and the same discipline applies here: the
consumer is about to route every song read through `get_song_overview`, and
nobody has measured what that costs on a real four-minute song with thirteen
sections and a full hint set.

Take the figures inside the `mcp` container, character count over four, on the
longest song in `data/analysis/` and on `_test_song`:

| Call | chars | ≈ tokens |
| --- | --- | --- |
| `get_song_overview(song)` | | |
| `get_detail(song, section_id=…)` — structural only | | |
| `get_detail(song, gesture_id=…)` — dense, 5 s | | |

`get_song_overview` is the one that matters: it is described as needing to
"stay compact enough to sit in context for the whole session", and it is now
also the concept pass's single read (§3). If it comes in materially above the
~1,000 tokens the downstream `get_song_brief` was budgeted at, §3 is a split
rather than a rename, and the numbers decide that — not this document.

---

## 1. `get_detail` serves drum onsets

**Current behaviour.** [`mcp-definition.md`](mcp-definition.md) "What it is for"
promises the server answers *"What exactly is happening at this instant?"* with
**"dense loudness and drum detail for a short window."** It does not serve drum
detail. `mcp/loaders.py` says so directly, in a comment: drum events are "not
required here yet — that is later v3.1 plan work." The loaders read eight
top-level files; `drum_events.json`, published at top level in v3.1, is not one
of them.

The gap has been invisible because the downstream consumer served drum events
itself, out of `artifacts/symbolic_transcription/drum_events.json`.

**Change.** `get_detail` returns drum-event rows — `time`, `event_type`,
`confidence` — whose `time` falls inside the resolved span, from the top-level
`drum_events.json`, alongside the loudness frames. Include the summary counts
for the window, so a caller can tell "no kicks here" from "no data here".

**This is the single most load-bearing item in the release.** A cue that lands
at the wrong moment is one of the two failures an audience actually notices, and
a kick onset is the thing an accent hangs off. Without this item, an author
anchors to the beat grid — which the one authored show in the downstream tree
records itself doing, naming re-pinning to real kick timestamps as the obvious
upgrade it could not perform.

---

## 2. The 5-second cap is a dense-frame rule, not a span rule

**Current behaviour.** The dense-series cap is 5 seconds. When the resolved span
exceeds it, `get_detail` returns the structural view and withholds the dense
frames, saying so explicitly and naming the cap. It never silently truncates and
never silently downsamples.

That rule is right for what it was written about — per-frame loudness at a 20 ms
floor, where a wide span is genuinely hundreds of KB. It is the wrong rule for
sparse event data. Five seconds is about 2.7 bars at 130 BPM: enough to chase one
transient, not enough to shape a phrase. A section pass wanting the onsets across
its own fifteen-second section has to make three calls and stitch them.

**Change.** Cap dense frames and sparse events separately.

- **Dense frames** (loudness) keep the 5 s span cap exactly as written,
  including the withhold-and-say-so behaviour and the 20 ms floor.
- **Sparse events** (§1's drum onsets, and the gesture phases already in the
  structural view) are capped by **row count**, not span, and are returned for
  the whole resolved span — a `section_id` scope included.

A section's worth of onsets is tens of rows, not thousands of frames; the two
were never the same cost and should not share a ceiling. The refusal shape stays
the same when a row cap is genuinely hit: explicit, naming the cap, never a
silent truncation.

---

## 3. `get_song_overview` absorbs the concept pass's read

**Current behaviour.** `get_song_overview` is one call, whole song, compact:
identity, grid with its honest downbeat note, sections, gestures, arrangement,
transitions and the operator's hints verbatim. The downstream server separately
built `get_song_brief` — duration, bpm, bar count, genre, sections with their
inferred character, and candidate `similar_sections` pairings — as "the *shape*
of the song in under 1,000 tokens, in place of `get_analysis()`'s per-section
hint prose." That tool is being deleted.

**Change.** `get_song_overview` carries the concept pass's read. Whether that
needs a scope parameter depends on item 0's measurement:

- If the overview already sits near the concept pass's budget, nothing changes
  but the documentation, which should say plainly that this call is the concept
  pass's single read.
- If it does not — most likely because the verbatim hints and the per-section
  `description` prose dominate — add a `scope="brief"` that drops the prose and
  keeps the numbers and the structure. Not a second tool: one projection, two
  densities, the same argument `interval_ms` already makes for the dense series.

**`same_label_as` supersedes `similar_sections`, and the caveat travels with
it.** The downstream tool grouped sections by inferred `section_character` and
published the groupings as candidates rather than conclusions. This server
already publishes the same relationship as `same_label_as` and already states
what it is: label repetition, not acoustic identity. That caveat is the honest
part and it must stay attached in any response that groups sections — a consumer
inheriting the grouping without it is exactly the laundering
["Honesty obligations"](mcp-definition.md) forbids.

---

## 4. A whole-song anchor view

**Current behaviour.** There are two resolutions and nothing between them: the
whole-song overview, whose gesture rows carry a span and a peak intensity, and
`get_detail`, which needs a scope selector and returns at most a 5 s dense
window. An author who wants to know *where the hits are in this song* has no
call that answers it. At the current caps, sweeping a four-minute song for its
accents is roughly forty-eight `get_detail` calls.

That is why an author reaches for the beat grid instead. The grid is one cheap
call and it is always wrong by a little.

**Change.** Gesture rows in `get_song_overview` carry the **impact time** they
are anchored on, not only the composite span. The gesture vocabulary is already
`approach → build → tension → impact → release`; the impact phase's own
timestamp is the anchor an author needs, and it is already in
`song_event_timeline.json` under the `gesture_id` grouping v3.1 added.

That makes the overview a whole-song anchor view at no new cost: one call gives
every significant moment in the song with the time it lands on and how hard, and
`get_detail` becomes what it was meant to be — the zoom, for a moment the author
has already located.

**It also sizes the travel budget**, which is the other half of landing on time.
The reason the server exists to answer *"where are the drops, and what is their
internal shape"* is stated in [`mcp-definition.md`](mcp-definition.md) itself —
*"so a moving head knows it has eight bars to travel"*. The `approach` phase's
start against the `impact` time is that budget, and with the impact time
published it is arithmetic the consumer can do without a second call.

**Honesty obligation, unchanged.** A drop is still never named directly. This
item publishes the time of a detected impact phase, which is what the existing
vocabulary already carries — it does not add a `drop` field or a confidence this
module did not measure. A gesture with no detected impact phase publishes no
anchor, exactly as an absent phase already means no supporting primitive was
found.

---

## 5. `arrangement_state` is load-bearing, and its absence must be named

**Current behaviour.** The overview's arrangement block comes from the optional
top-level `arrangement_state.json`, and "the whole block is omitted for a song
analysed before v3.2."

Silent omission was defensible when the block was a v3.2 nicety. It is not
defensible now. **This is the input that prevents the wrong thing being lit** —
a piano solo with the light on the mic is not an imprecision, it is a visible
mistake, and `playing` / `entered` / `left` per block is the only signal in the
system that answers it. The downstream server has never read this file and is
about to stop reading analysis entirely, so this projection is the sole path.

**Change.** The block's absence is reported explicitly — a named gap with its
reason (song analysed before v3.2; re-run the pipeline to populate it), not a
missing key. An author flying blind on who is playing must know they are.

This is the same argument the server already makes for
`analysis_root_present`-style distinctions and for `function_status: "unknown"`:
a gap surfaced is a gap the caller can weigh; a gap smoothed away is a wrong
answer. It is an honesty obligation, and it belongs in that list.

**Known limitation to state in the projection, not hide.** `issues.md` records
that `detect-arrangement-state` scores F1 0.59 on `_test_song` but 0.20 pooled
corpus-wide, below the incumbent, because the gold hints are almost all drop
stages that `gestures.py` owns. The block's per-block `confidence` already
carries this and must not be inflated — but the honest framing is that
arrangement state is a strong signal for *who is playing* and a weak one for
*drop staging*, and a consumer should be told which question it is good for.

---

## 6. Restate the boundary — both directions

**Current behaviour.** ["The hard boundary"](mcp-definition.md) states one
direction firmly: cue authoring is permanently forbidden here — no cue
proposing, writing or validating, no rig, fixtures or POIs, no DMX. That stays
exactly as written; nothing in v3.3 softens it.

**Change.** The reciprocal is now true and should be stated beside it: **the
downstream server no longer reads `data/analysis/` at all.** It has no
projection of its own, no windowed door into `artifacts/`, and no mount. There
is no second path to a musical fact.

That converts a stylistic preference into a contract. Previously, a thin
projection here was an inconvenience the consumer could route around; now it is
a capability the system does not have. The exposure rule is unchanged — this
server reads `data/analysis/{song}/*.json` and nothing else, `artifacts/` and
`reference/` stay closed to it — but its consequence is heavier: **a signal that
phase 4 does not publish at top level cannot reach a light show at all.**

Worth saying plainly in ["Keeping it in sync"](mcp-definition.md) too. That
section's advantage — an in-tree consumer turns contract drift into a failing
test — now covers strictly more of the delivery surface than it did, because the
out-of-tree consumer's independent readers are gone.

---

## 7. Close `contract-change-v3.1.md`

**Current behaviour.** [`contract-change-v3.1.md`](contract-change-v3.1.md) is
headed *"Handoff note for `ai-dmx-light-render` — delivery pending; remove once
the downstream consumer has migrated."* It has never been consumed: the
consumer still reads `artifacts/section_segmentation/sections.json` after §3 of
that note said to stop, and still reads `artifacts/` copies of `genre.json`,
`loudness.json` and `drum_events.json` that v3.1 published at top level.

**Change.** The note is **superseded, not delivered**, and closing it should say
so. The consumer is not migrating to the top-level files; it is deleting every
reader the note addressed. Nothing in v3.1's delivery surface reaches it any
more except through this server's projections.

Archive it with that outcome recorded. The bare-array trap in §2 —
`beats.json` and `sections.json` becoming objects, which breaks an iterating
consumer silently — stays worth keeping as a lesson even though its audience is
gone, because this module reads the same files.

**After v3.3 there is no external consumer of the delivery surface**, only of
this server's tool responses. Future contract changes are handoffs about *tool
shapes*, not file shapes — a narrower and more stable thing to promise, and the
next such note should be written that way.

---

## Outcome summary (implemented)

All v3.3 items landed and were validated in-container (`smoke-test`,
targeted pytest, and `full-regression` all green on committed fixtures).

- Item 0 — `0. Measure baseline token cost` (`47363c0`)
- Item 1 — `1. get_detail serves drum onsets` (`94a55c7`)
- Item 2 — `2. Separate dense-cap and sparse-cap rules` (`e073f6b`)
- Item 4 — `4. Add whole-song impact anchors` (`28b5cb2`)
- Item 5 — `5. Make arrangement_state absence explicit` (`92502b3`)
- Item 3 — `3. Make get_song_overview the concept-pass read`
  (`2c09cf3`, `5cfc7e1`, `3375817`)
- Item 6 — `6. Restate boundary in definition docs` (`f2d712a`)
- Item 7 — `7. Close contract-change-v3.1 as superseded`
  (`5a1398b`, `d41832d`)
- Item S3.1 — `S3.1 Align cross-repo client invocation docs` (`cd8e7ee`)

`S3.1` is resolved: this repo and
`ai-dmx-light-render/docs/mcp-server-definition.md` now both document the
canonical remote Docker-over-SSH invocation, absolute `-f` compose path, and
required `-T` flags.
