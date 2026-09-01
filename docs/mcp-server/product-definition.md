# MCP Server — Product Definition

**Component:** `mcp/` (new, this repo, alongside `src/analyzer/` and `ui/`).
**Status:** definition. Build is tracked in
[implementation-plan.md](implementation-plan.md).

## 1. Purpose

Let a reasoning model understand a song's **mood, sections, and dynamics** —
drop sequences above all — while spending as few tokens as possible on it.

`data/analysis/<Song - Artist>/` is large: ~15 JSON files, several with
multi-thousand-row dense arrays (`rms_loudness.json` is 10 ms frames — ~5 800
rows for a one-minute track). Handing that to a model raw is unaffordable and
mostly irrelevant to the question being asked. This server projects **compact,
purpose-shaped views** of the analysis and lets the model **drill down only
where it needs to**.

This is a **song-comprehension** server, and that is its whole remit. It is not
the light-show authoring server.

### Two different MCP servers — do not conflate

| Server | Repo | Job |
| --- | --- | --- |
| **This one** (`mcp/`) | `ai-light-song-v2` | Read-only. Projects song mood, sections, and dynamics token-efficiently so a model can *understand* the music. |
| **Cue-authoring server** | `ai-dmx-light-render` (`backend/src/app/mcp/`, already built) | Lets a model *author* `.cue.json` cue sheets against a rig — fixtures, POIs, the effects vocabulary, the whole-timeline validator. Defined in `ai-dmx-light-render/docs/mcp-server-definition.md`. |

The `get_song_brief` / `get_analysis` / `get_analysis_detail` reads described in
[../source references/analysis-input-guide.md](../source%20references/analysis-input-guide.md)
belong to the **cue-authoring server**, not this one. That server stays a
separate component this repo does not modify; this server is a new, additional,
narrower one that lives in-repo next to the artifacts it reads.

## 2. Non-goals

- **No cue authoring. Ever.** Proposing, writing, or validating `.cue.json`;
  reading a rig config, fixtures, or POIs; any fixture-aware output — all of it
  is **permanently out of scope** and is the sole responsibility of the
  `ai-dmx-light-render` cue-authoring server. This server is not "v1 of"
  something that later grows a `cue.` surface; a cue tool must never be added
  here.
- **No fixture or cue instructions in responses.** The server never says "point
  the moving head here" or "strobe on this beat". It describes the music.
  `lighting_hint` strings that already exist in the artifacts are passed through
  only after being reduced to a *musical* description (`musical_cue`), and only
  in detail reads — see §6; any that cannot be de-fixtured are dropped.
- **Not a database or a search engine.** It serves one analyzed song at a time,
  addressed by name.
- **Read-only. Always.** The server never writes into `data/analysis/**` or
  anywhere else, consistent with the constitution's reference-isolation rule and
  the debugger's "never writes" posture.

## 3. Where it lives and what it reads

| Aspect | Decision |
| --- | --- |
| Location | `mcp/` package at repo root. Own `pyproject`/entry point; unit tests colocated. |
| Language / SDK | Python (matches the analyzer), the official `mcp` package. |
| Transport | stdio (local host process). HTTP is a later option, not v1. |
| Analysis root | Config value / env var (`ALS_ANALYSIS_ROOT`), default `./data/analysis`. `data/` is gitignored, so the root is always supplied by the deployment. |
| Song identity | The directory name under the analysis root, verbatim (`"Armin - Revolution"`). `list_songs` enumerates them. |
| Container | Runs in the project's Docker environment like every other component. |

The server loads only the files a tool needs, parses them, and holds nothing
between calls beyond a small in-process cache keyed by `(song, file mtime)`.

## 4. The two capabilities

**(a) Whole-song dynamics** — one call returns a compact overview of the entire
song: meta, the section list, the dynamics timeline (drops, builds, breakdowns,
impacts…), a coarse energy arc, and a drop index. Prose is kept out; every field
is billed to the caller's context.

**(b) Segment detail** — given a time window, a `section_id`, or a `drop_id`,
return the fine-grained picture for just that span: events expanded with their
musical prose, the full five-phase envelope for a drop, a downsampled dense
signal window, the hints and beat grid for that span.

The model uses (a) to decide *where* to look, then (b) to look there.

## 5. Tool surface (v1)

### `list_songs()`

Returns `[{ song, duration_s, bpm, has_analysis }]` for every directory under
the analysis root. Cheap; lets the caller resolve a title before asking for
anything heavier.

### `get_song_dynamics(song)`

Capability (a). One compact object:

- **`meta`** — `title`, `duration_s`, `bpm`, `key` (+ `mode`), `time_signature`.
- **`character`** — `genre[]`, `genre_confidence`, `genre_guidance[]` (the
  source's own prose, verbatim), `form_family` (+ `confidence`). This is the
  "mood" surface as it stands today; see §7.
- **`sections[]`** — one row per section, time-ordered:
  `section_id`, `start_s`, `end_s`, `form_role`, `form_role_confidence`,
  `energy_character`, `repetition_group`, `variant_of`, `description`
  (the one-sentence top-level `description`, passed through), `confidence`.
- **`dynamics[]`** — the lean event table of contents: `id`, `type`,
  `start_s`, `end_s`, `intensity` (absolute 0–1), `section_id`,
  `confidence`, `provenance`. Composite drops appear as **one row** with
  `type: "drop"`, `composite: true`, `phase_count`, and `impact_s`. **No
  `summary` / `evidence` / `lighting_hint` here** — those are detail-read only.
- **`energy_arc[]`** — a coarse curve: one point per section (or per bar-group
  for long sections), `{ time_s, intensity }`, derived from `rms_loudness`
  mix + stems, downsampled hard. Lets the model see the song's shape without the
  dense stream.
- **`drops[]`** — the drop index: `{ drop_id, impact_s, start_s, end_s,
  confidence, phase_count }`, one per detected drop sequence. This is the direct
  answer to "how many drops, and where".

### `get_drop_sequence(song, drop_id)`

Capability (b), specialised for the emphasis of this system. Returns the full
gesture:

- `drop_id`, `section_id`, overall `start_s` / `end_s` / `confidence` /
  `intensity`.
- **`phases[]`** — the ordered envelope `approach → build → tension → impact →
  release`, each `{ phase, start_s, end_s, intensity_start, intensity_end }`.
- `member_event_ids[]` and the expanded member events (with prose `summary`).
- `evidence` — the drop-decision breakdown (`drop_evidence` metadata) so the
  model can see *why* this was called a drop and how confident to be.
- Optional `signal` — a downsampled dense window over the gesture span
  (per-stem loudness at a coarse interval, drum onsets), included only when
  `include_signal: true` and the span is ≤ the dense-window cap.

### `get_segment_detail(song, { start_ms, end_ms | section_id })`

Capability (b), general. For the requested span:

- **`events[]`** — every event overlapping the span, fully expanded: `type`,
  times, `intensity`, `confidence`, `provenance`, `summary`, `evidence_summary`,
  and `lighting_hint` **relabelled as `musical_cue`** (the server strips any
  fixture phrasing to a musical description, or drops it).
- **`hints[]`** — inference hints plus merged human hints
  (`reference/human/human_hints.json`) that fall in the span, each
  `{ source, category, text, start_s, end_s }`.
- **`beats[]`** — the beat/bar grid slice: `{ time_s, type, bar, beat }`,
  downbeats flagged. Bounded row count.
- **`signal`** — same optional downsampled dense window as above.
- `sections_touched[]` — the `section_id`s the span overlaps, for context.

## 6. Projection and token-budget principles

These are contract, not style:

1. **Overview reads carry no prose.** `get_song_dynamics` returns identifiers,
   numbers, and controlled-vocabulary tokens only. Every free-text field is
   deferred to a detail read.
2. **Detail reads are windowed.** `get_segment_detail` and the `signal` block
   reject a span wider than a stated cap (default: detail 45 s, dense signal
   15 s). A caller that wants more makes more calls — that keeps the cost
   visible.
3. **Dense signals are always downsampled.** `rms_loudness` 10 ms frames are
   never returned raw. The server aggregates to a target interval (default
   250 ms) and a capped frame count, and says what interval it used.
4. **Every response states its own size.** A `budget` block on each response:
   `{ approx_tokens, rows, truncated }`. `truncated: true` names what was
   dropped and how to fetch it.
5. **Controlled vocabularies pass through unchanged** — `form_role`,
   `energy_character`, event `type`, hint `category`. The caller is expected to
   hold the vocabularies; the server does not re-explain them per call.
6. **Times are seconds (float) in every response.** Inputs accept `_ms` for
   precision; outputs are `_s`.

## 7. The "mood" question

There is no dedicated mood artifact in the pipeline today. In v1 the server
projects mood from what exists: `genre_guidance[]` prose, `key` mode
(major/minor), `energy_character` per section, `form_role`, and the per-section
`intensity` trajectory. `get_song_dynamics.character` and the section rows carry
these; a caller infers mood from them.

If a first-class mood signal is wanted (a short controlled descriptor per
section — `driving`, `euphoric`, `brooding`, `spacious`, `tense`, `wistful`,
…), that is **analysis-pipeline work**, not MCP work: the server would just
project it. It is recorded here as an upstream ask, to be raised as a refinement
item against the analyzer, following the same pattern
[analysis-input-guide.md](../source%20references/analysis-input-guide.md) uses
for dense signals ("propose it rather than hoping a layer file gets read").

## 8. Confidence and provenance posture

The operator's standing rule — confidence-bearing analysis is inference, never
premise — applies to every consumer of the artifacts, this server included. It
is stated for the cue-authoring consumer in
[analysis-input-guide.md](../source%20references/analysis-input-guide.md) §3;
the same posture holds here:

- Confidence is always its own numeric field, never folded into a display
  string. Where a source file only has it in a `label` string, the server
  surfaces the numeric value from the segmentation row.
- Source `guidance` / prose is passed through verbatim, not paraphrased.
- A low confidence is a signal — the server never inflates or floors it.
- Every section and every event carries `confidence` **and** `provenance`.

## 9. Selection, identity, errors

- **Song** — exact directory name. Unknown song → a typed `song_not_found`
  error listing near matches.
- **`section_id`** — as emitted by `artifacts/section_segmentation/sections.json`
  (`"section-001"`). The server joins the top-level and segmentation section
  lists **on `section_id`** (per B5 / v2.1 item 3.2), not by array index.
- **`drop_id`** — assigned by the server, stable within a song for a given
  analysis version: `"drop-1"`, `"drop-2"`… in impact-time order. Echoed in
  `get_song_dynamics.drops[]`.
- **Missing artifact** — a tool that needs a file the song does not have returns
  a typed `artifact_missing` error naming the file and the pipeline stage that
  produces it, never a partial silent response.
- **Stale analysis** — if the analysis `schema_version` is older than the server
  supports, the response carries a `stale_analysis` warning rather than
  guessing at the old shape.

## 10. Extensibility

Within the song-comprehension remit only — cue authoring is never one of the
directions this server grows (§2).

- The projection layer is a set of pure serializers
  (`artifact dict → compact dict`) with no tool logic, so a new
  song-understanding tool (e.g. a harmonic-progression view, a lyrics/vocal
  view) is composition, not a rewrite.
- All tools carry a `song.` name prefix, marking this as the song-comprehension
  server so a host that also mounts the `ai-dmx-light-render` cue server keeps
  the two legible.
- Transport is abstracted behind the `mcp` SDK; an HTTP deployment is a config
  change, not a code change.

## 11. Dependencies on the analysis pipeline

- **Composite drop sequences with `phases[]`.** `get_drop_sequence` needs the
  five-phase envelope. The `song_event_timeline.json` export already carries
  composites (v2.1 R5); the envelope becomes complete and pipeline-wide with
  v2.2 items 3–7. Until then `get_drop_sequence` returns whatever phases the
  export has and marks the response `partial_envelope: true`.
- **`section_id` on every section, event, and hint** (v2.1 item 3.2) — required
  for the joins in §9.
- **The dense artifacts** `artifacts/essentia/rms_loudness.json` and
  `artifacts/symbolic_transcription/drum_events.json` — the only two dense
  signals the server will downsample. Their stem set and interval must stay
  regular.
- **`beatdrop_visual_plan.json` is not read** — it is deprecated (v2.2 item 1).
