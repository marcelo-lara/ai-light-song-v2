# CLAUDE.md — orientation for `ai-light-song-v2`

## What this is

The **analysis module** of a three-part stage-lighting system. It turns a song
into structured musical analysis under `data/analysis/<Song - Artist>/`. A
separate MCP server (another repo) projects small, token-budgeted views of that
analysis to a model that authors the light show, targeting **moving-head
fixtures**.

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
| [`docs/ui-definition.md`](docs/ui-definition.md) | the debugger, its lanes, and the one thing it may write |
| [`docs/mcp-definition.md`](docs/mcp-definition.md) | what reaches the authoring model — the contract quality is judged against |

Lookups, not reading: [`docs/reference/`](docs/reference/) —
[`artifacts.md`](docs/reference/artifacts.md) (every `data/` file),
[`source-map.md`](docs/reference/source-map.md) (every `src/` file),
[`cli.md`](docs/reference/cli.md) (`./analyze` flags),
[`docker.md`](docs/reference/docker.md) (runtime and version pins),
[`ui-regression.md`](docs/reference/ui-regression.md) (visual QA runbook).

Queues: [`docs/issues.md`](docs/issues.md) (open issues only),
[`docs/experiments.md`](docs/experiments.md) (one entry per experiment),
[`docs/archive/experiments.md`](docs/archive/experiments.md) (concluded ones —
the only archive file that exists).

Measured evidence lives with the experiment: `experiments/*/README.md`. That is
the best account of what actually works, and it does not go stale with age.

## The four phases

| Phase | Reads | Produces |
| --- | --- | --- |
| 1 **measure** | audio | facts that cannot be musically wrong — beat grid, loudness, spectra, chroma, stems |
| 2 **interpret** | phase 1 + audio | claims — chords, key, sections and their names, drum events, genre |
| 3 **relate** | phase 2 only, **never audio** | identity, repetition, transitions, composite gestures |
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
| Chord labels | **informative, not settled.** Agreement with a second model: 1.00 / 0.69 / 0.51 / 0.38 across the gold songs |
| Structure (`segmentation.py`) | **improved, not solved.** F1 0.67 vs the old segmenter's 0.29. `function_status: "unknown"` is set honestly, and `same_label_as` is label repetition, not identity |
| Downbeats / bar numbers | **short of target — 0.226 F1** against a 0.50 goal. **Do not assume bar numbers are correct.** A `null` confidence is an honest "we don't know", not a guess |
| Gestures (`gestures.py`) | **better than what it replaced**: 4/7 @±1.0 s vs 2/7. Per-primitive *precision* has never been audited — see `docs/issues.md` |
| Section identity | **not shipped.** MFCC 0.73 is the number any attempt must beat |
| Character blocks (texture, not arrangement) | **measured in `experiments/clap/`, not shipped** |

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
- **Provenance.** Every generated file carries `generated_from`; every claim
  carries how it was arrived at.
- **Docs hold current material only.** Delete a doc in the change that makes it
  stale — git history is the archive. No numbered story files, no archive folder
  (`docs/archive/experiments.md` is the sole exception). If intent and behaviour
  disagree, that is a defect to fix now, not a precedence rule to invoke.
- Clean up temporary scripts; use the session scratchpad, not the repo.

## Running things

```bash
docker compose build

# full pipeline + validation report for one song
docker compose run --rm app ./analyze --song "/data/songs/YOUR_SONG.mp3"

# whole corpus (21 songs), each in its own subprocess
docker compose run --rm app ./analyze --all-songs --device cuda

# a single stage (prerequisite artifacts must already exist)
docker compose run --rm app ./analyze --song "/data/songs/YOUR_SONG.mp3" --stage segment-sections

docker compose run --rm test     # tests
docker compose up ui             # debugger at http://localhost:9090
```

Stage names come from `STAGE_PIPELINE_IDS` in
[`src/analyzer/pipeline.py`](src/analyzer/pipeline.py) — authoritative ahead of
any prose. Flags: [`docs/reference/cli.md`](docs/reference/cli.md).

## Where things live

| Path | Contents |
| --- | --- |
| `src/analyzer/pipeline.py` | stage registry and orchestration — start here for execution order |
| `src/analyzer/stages/` | one file per stage; each carries its measured numbers in its own docstring |
| `data/analysis/<Song - Artist>/` | exactly five top-level files plus `artifacts/` |
| `data/analysis/<Song - Artist>/reference/` | human and external ground truth. Read-only to the pipeline |
| `ui/` | read-only artifact debugger (Preact + TS + Vite) |
| `experiments/` | the sandbox. `src/` never imports from it |
