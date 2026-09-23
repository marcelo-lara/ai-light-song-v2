# CLAUDE.md — orientation for `ai-light-song-v2`

## What this is

The **analysis module** of a three-part stage-lighting system. It turns a song
into structured musical analysis under `data/analysis/{song}/`. The in-repo
`mcp/` server projects small, token-budgeted views of that analysis to a model
that authors the light show, targeting **moving-head fixtures**; a separate
cue-authoring server (`ai-dmx-light-render`, another repo) turns those cues into
DMX.

This repo produces *concrete, reliable, precisely-timed musical facts a
reasoning model can author a production-quality light show from.* That is the
whole job. **Fixture-aware orchestration, cue authoring, lighting-design
documents and DMX are out of scope.**

The work is not "extract many features". It is to establish **where the song
changes, what each part is, and how the parts relate** — precisely enough that a
model reading only a compact projection can author cues.

## The four definition documents

Read the one that answers your question. Do not re-derive this from `src/`.

| Doc | Answers |
| --- | --- |
| [`docs/product-definition.md`](docs/product-definition.md) | what the system is for, and what it is explicitly not for |
| [`docs/analysis-definition.md`](docs/analysis-definition.md) | every stage, which phase it is in, **and how good it measures**. Read before trusting any output |
| [`docs/ui-definition.md`](docs/ui-definition.md) | the debugger: reviewing findings, authoring human hints, and the two files it may write |
| [`docs/mcp-definition.md`](docs/mcp-definition.md) | the in-repo `mcp/` song-comprehension server — purpose, hard boundary, tool surface. **Built and green** |

Lookups, not reading: [`docs/reference/`](docs/reference/) —
[`artifacts.md`](docs/reference/artifacts.md) (every `data/` file),
[`downstream-contract.md`](docs/reference/downstream-contract.md) (what the external cue-authoring server consumes),
[`source-map.md`](docs/reference/source-map.md) (every `src/` file),
[`cli.md`](docs/reference/cli.md) (`./analyze` flags),
[`docker.md`](docs/reference/docker.md) (runtime and version pins),
[`ui-regression.md`](docs/reference/ui-regression.md) (visual QA runbook),
[`ui-development.md`](docs/reference/ui-development.md) (adding/removing a UI lane and other repetitive `ui/` changes),
[`mcp-regression.md`](docs/reference/mcp-regression.md) (`smoke-test` and `full-regression` for the MCP server).

No open release. The `mcp/` module and its delivery surface shipped in v3.1
(see git history); the current contract with the downstream cue-authoring
consumer is [`docs/reference/downstream-contract.md`](docs/reference/downstream-contract.md).

Queues: [`docs/issues.md`](docs/issues.md) (open issues only),
[`docs/experiments.md`](docs/experiments.md) (one entry per experiment),
[`docs/archive/experiments_archive.md`](docs/archive/experiments_archive.md)
(index of one file per promoted or discarded experiment — what shipped, and
what did not; TLDRs, the only archive material that exists).

Measured evidence lives with the experiment: `experiments/*/README.md`. That is
the best account of what actually works, and it does not go stale with age.

## The four phases

| Phase | Reads | Produces |
| --- | --- | --- |
| 1 **measure** | audio | facts that cannot be musically wrong — beat grid, loudness, spectra, chroma, stems |
| 2 **interpret** | phase 1 + audio | claims — key, sections and their names, drum events, genre |
| 3 **relate** | phases 1-2, **never audio** | identity, repetition, transitions, composite gestures |
| 4 **publish** | phases 1-3 | the projected deliverables, and nothing else |

The 1/2 line is **not** DSP vs. ML — it is *does this stage assert something
that could be musically wrong?* Phase 1 carries no confidence field; phase 2
onward always does. Phase 3 may refine phase 2 but writes a new artifact — never
mutates.

## Current state, in one table

Full numbers, per-song breakdowns and root causes:
[`docs/analysis-definition.md`](docs/analysis-definition.md).

| Area | State |
| --- | --- |
| Stems, beat *times*, FFT, loudness, HPCP, drums, energy | **trusted.** 7/7 human impacts within 0.25 s of an essentia beat |
| Drum vocabulary (`drums.py`) | **bounded and written down.** Omnizart emits GM pitches 35/38/42 only; `velocity` is a constant 100 (not published); `confidence` is `null`; toms/congas fold into kick/snare — a *known* wrong label. v3.4 adds a `crash`/`hat` split on pitch 42 (drums-stem 6–16 kHz brilliance gate), nothing else in the taxonomy widened |
| Chord inference | **removed.** It failed on every song and never served its purpose (finding where a song repeats). Only the essentia whole-song `key` survives, published on `sections.json` |
| Structure (`segmentation.py`) | **improved, not solved.** F1 0.67 vs the old segmenter's 0.29. `function_status: "unknown"` is set honestly, and `same_label_as` is label repetition, not identity. `sections.json` rows also carry `energy`/`tension`/`rhythm` (v3.6 item 10, `section_clues.py`) — fused per field from the operator's `segments.json` (`human`), else the best-clearing candidate producer, else `segments.seed.json` (`seed_unreviewed`, `confidence: null`); and `impact_alignment` (v3.7 item 2, always present, `null` outside ±2 bars of a nearest gesture impact — never fused from human/seed). **Provisional corpus-wide**: only 4 songs (`Cinderella - Ella Lee`, `_test_song`, `ayuni`, `What a Feeling - Courtney Storm`) have operator-reviewed segments; the rest is seed or candidate-producer output, not yet reviewed — `get_song_overview`'s `review_warning` names every affected section |
| Downbeats / bar numbers | **short of target — 0.226 F1** against a 0.50 goal. **Do not assume bar numbers are correct.** A `null` confidence is an honest "we don't know", not a guess. `mcp/`'s `get_detail` derives a `position` (`bar`/`beat`/`section_id`/`resolved`) on read for every time field it serializes (v3.7 item 3) — `resolved: false` on a bar guessed across a null-confidence downbeat, same honesty rule |
| Gestures (`gestures.py`) | **better than what it replaced**: 4/7 @±1.0 s vs 2/7. Per-primitive *precision* has never been audited — the debugger now has the instrument to do it (v3.7 item 1: a three-state verdict control on every claim-bearing lane's blocks, scored by `experiments/truth_common`'s `block_reviews` scorer) but the actual four-gold-song audit has not been run — see `docs/issues.md` |
| Section identity | **not shipped.** MFCC 0.73 is the number any attempt must beat |
| Character blocks (texture, not arrangement) | **measured in `experiments/clap/`, not shipped** |
| Arrangement state (`detect-arrangement-state`, phase 3) | informative on `_test_song` (F1 0.59 vs `sections.json` 0.00), unmeasured elsewhere; honest `null` confidence off the margin |
| `vocals` channel (`playing[]` vs `vocals_phrase[]`) | **decided: `playing`'s `vocals` stays RMS-only** (false_vocal 0.0891 on `ayuni`) — gating it on whisperX lowered false_vocal but cost >0.01 frame_acc on `Cinderella`. Trust `vocals_phrase[]` (whisperX) for voice presence. whisperX's own compute now runs in-pipeline as the `whisperx` Compose service (`whisperx_vad/`, v3.6 item 2) rather than out-of-band in `experiments/` — run it before `./analyze`; `vocals_phrase` is never `null` once it has. That service also writes `artifacts/whisperx-vad/vocal_onsets.json` (v3.6 item 10, `faster_whisper` large-v3 word onsets) — `section_clues.py`'s only candidate producer for `rhythm.vocals` |
| `mcp/` server + delivery surface | **built and green.** Five tools: `list_songs`, `get_song_overview`, `get_detail` (read-only), plus `propose_hint`/`propose_section_field` (v3.7 item 10 — the one write path, code-scoped to appending `reference/proposals/pending.json`; the `mcp` service's `/data` mount is read-write for this, enforced by code not the mount). All nine top-level files per song are **hard-required** — no degraded mode, a missing one errors naming it — each carrying a `field_sources` attribution header. `get_detail`'s structural view carries `beats` (`time`/`bar`/`beat`/`downbeat_confidence`, undecimated past the 5 s cap), and — v3.7 items 3/5/7/8/9 — a `position` on every time field, a `bars` scope selector, `stem_summary`, `drum_density` and `dropouts`. `get_song_overview` carries `review_warning` when any section has a `seed_unreviewed` field; deliberately omits `position` (byte-budget, `docs/issues.md`). A proposal reaches a published file only via the debugger UI's approve flow (v3.7 item 11), which writes `reference/human/` and shows a reminder to run the republishing `--stage` by hand — the UI has no Docker access to trigger it itself (a docker-socket approach was tried and reverted as too broad a host-access grant) |

## Rules that are load-bearing

These are the rules that get broken by default — an agent's instinct is to add a
fallback, keep the old doc, preserve the schema. Each one is here because
breaking it has already cost this repo something.

- **Docker only.** All analysis, validation and tests run inside the Compose
  services. Never propose host-installed Python or audio tooling.
- **No silent fallbacks.** Fail explicitly, or emit `unknown`. Never invent a
  plausible default — a generic C-major chord, a guessed section label — to keep
  a run green. An honest `unknown` costs the cue-authoring model nothing; a
  confident wrong answer costs it the show.
- **Confidence is a separate numeric field**, never folded into a display
  string, and never inflated. A low confidence is itself useful signal.
- **The reach test.** A feature is only real if it reaches the authoring model.
  Before building, name the projected file the signal lands in — the list is in
  [`docs/mcp-definition.md`](docs/mcp-definition.md). Improving an artifact
  nothing projects changes nothing about the show.
- **Only top-level song JSON is exposable.** The MCP server reads
  `data/analysis/{song}/*.json` and nothing else. `artifacts/` and
  `reference/` are readable by **the analyzer and the debugger UI only** — they
  are the raw material phase 4 uses to build the top-level files, never a
  delivery surface. A signal reaches the model only by being published at top
  level.
- **Musical correctness outranks compatibility.** Propose changing the schema,
  field names or file set rather than building a workaround or a shim.
- **Delete dead code rather than keeping it working.** A stage with no consumer
  costs maintenance, invites false confidence, and misleads every reader about
  what the system is for. ~6,000 lines left `src/` in v3.0 for exactly this reason.
- **Experiments stay out of `src/`, and `src/` never imports from them.**
  Method and the promotion gate: [`docs/experiments.md`](docs/experiments.md).
  When something beats the incumbent, **ask before promoting** — and say what
  gets deleted in the same change.
- **`reference/` is validation-only.** Never copy it into a generated artifact
  except through an explicit, confidence-gated, provenance-recorded promotion.
- **Determinism.** Same input + engine version ⇒ byte-identical artifacts. No
  hidden state, no mid-run downloads, seeded randomness, versioned schemas.
- **Time in seconds, bars 1-indexed.** For structural boundaries the physical
  onset wins over the nearest grid position — a cue fired late is a cue missed.
  Where the grid itself is uncertain, say so rather than snapping and implying a
  precision that isn't there.
- **Provenance.** Every artifact carries `generated_from`; every top-level
  (delivery-surface) file carries `field_sources` instead — no top-level file
  carries `generated_from` (v3.6 item 8). Every claim carries how it was
  arrived at.
- **Docs hold current material only.** Delete a doc in the change that makes it
  stale — git history is the archive. No numbered story files, no archive folder
  (`docs/archive/` is the sole exception). If intent and behaviour
  disagree, that is a defect to fix now, not a precedence rule to invoke.
- Clean up temporary scripts; use the session scratchpad, not the repo.

## Running things

```bash
docker compose build app mcp whisperx ui   # `build` alone builds only `ui`; the rest are on-demand

# `docker compose up` (no service) starts ONLY the `ui` debugger. `app`, `mcp`,
# `whisperx` and `test` carry the `ondemand` profile — `docker compose run`
# still starts them, or `docker compose --profile ondemand up` brings the
# whole set up.

# whisperX VAD (arrangement_state.json's vocals_phrase) — run before ./analyze;
# its own torch~=2.8.0 pin can't share the `app` image
docker compose run --rm whisperx --song "/data/songs/YOUR_SONG.mp3"

# full pipeline + validation report for one song
docker compose run --rm app ./analyze --song "/data/songs/YOUR_SONG.mp3"

# whole corpus (21 songs), each in its own subprocess
docker compose run --rm app ./analyze --all-songs --device cuda

# a single stage (prerequisite artifacts must already exist)
docker compose run --rm app ./analyze --song "/data/songs/YOUR_SONG.mp3" --stage segment-sections

docker compose run --rm test     # tests
docker compose up ui             # debugger at http://localhost:9090

# song-comprehension MCP server — spawned by its client over stdio, -T is mandatory
docker compose run --rm -T mcp
docker compose run --rm --no-deps -T --entrypoint python mcp mcp/tests/run.py smoke-test
```

Stage names come from `STAGE_PIPELINE_IDS` in
[`src/analyzer/pipeline.py`](src/analyzer/pipeline.py) — authoritative ahead of
any prose. Flags: [`docs/reference/cli.md`](docs/reference/cli.md).

## Where things live

| Path | Contents |
| --- | --- |
| `src/analyzer/pipeline.py` | stage registry and orchestration — start here for execution order |
| `src/analyzer/stages/` | one file per stage; each carries its measured numbers in its own docstring |
| `data/analysis/{song}/*.json` | the delivery surface — the only files the MCP server may read |
| `data/analysis/{song}/artifacts/` | intermediates. Analyzer and debugger UI only |
| `data/analysis/{song}/reference/` | human and external ground truth. Read-only to the pipeline; never exposed |
| `ui/` | the debugger (Preact + TS + Vite). Reads anything under `data/`; writes only `reference/human/` |
| `mcp/` | the song-comprehension MCP server. Reads top-level song JSON only — never `artifacts/` or `reference/` |
| `experiments/` | the sandbox. `src/` never imports from it |
