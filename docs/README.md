# Documentation map

Two kinds of document live here, and the difference is load-bearing:

| | Folder | Status |
| --- | --- | --- |
| **Current** | this file, [`constitution.md`](constitution.md), [`data_folder_reference.md`](data_folder_reference.md), [`source_files_reference.md`](source_files_reference.md), [`docker_development.md`](docker_development.md), [`issues.md`](issues.md), [`reference/`](reference/) | Describes how the system is meant to behave now. Keep in sync with the code. |
| **Historical** | [`archive/`](archive/) | Records how features were planned and built. **Not specifications.** Every file is banner-marked; inside `archive/`, the code wins over the doc. |

**Start at `CLAUDE.md` in the repo root** — it is the entry point for both people
and models: what the system does, which stages are trusted, and what the
measurements say is broken.

## Current documents

### Contracts and law

| Doc | What it covers |
| --- | --- |
| [`constitution.md`](constitution.md) | Project law. §1 defines the scope (musical facts, **not** fixture orchestration), §2 the honesty rules, §3 the experiment lifecycle, §4 the current-vs-archive doc tiers. Rewritten 2026-09-02. |
| [`data_folder_reference.md`](data_folder_reference.md) | Every file under `data/` and what produces it. The artifact contract. |
| [`source_files_reference.md`](source_files_reference.md) | Map of `src/` — where each pipeline stage lives. Update it when you move code. |
| [`docker_development.md`](docker_development.md) | Container runtime, GPU expectations, model caches. |

### Reference — [`reference/`](reference/)

| Doc | What it covers |
| --- | --- |
| [`analysis-input-guide.md`](reference/analysis-input-guide.md) | **The contract analysis quality is actually judged against**: which artifacts reach the cue-authoring model through the MCP server, and which are invisible to it. If a signal is not in one of the projected files, it does not affect the light show. |
| [`layer_manifest.md`](reference/layer_manifest.md) | Role of each `layer_*.json` artifact. |
| [`phase_1_validation_cli.md`](reference/phase_1_validation_cli.md) | `./analyze` flags, compare targets, exit codes, validation report shape. |
| [`drop_definition.md`](reference/drop_definition.md) | What a "drop" is, musically. Concept reference — see `CLAUDE.md` on why *drop* is being demoted from a detection target to a derived label. |
| [`lighting_score_template.md`](reference/lighting_score_template.md) | Required structure of the generated `lighting_score.md`. |
| [`ui_development.md`](reference/ui_development.md) | Debugger runtime and its read-only data contract. |
| [`mcp-server-product-definition.md`](reference/mcp-server-product-definition.md) | What the in-repo read-only MCP server is meant to be. **No code exists yet.** |
| [`ui-regression_guide.md`](reference/ui-regression_guide.md) | How to run and review the UI visual regression suite. |
| [`ui-design/`](reference/ui-design/) | "Score Analysis DAW" design reference for the shipped `UI v2`. |

### Open work

| Doc | State |
| --- | --- |
| [`issues.md`](issues.md) | Analysis-issue queue — **open issues only** (constitution §4.2). Solved entries move to [`archive/issues-solved.md`](archive/issues-solved.md). Currently empty. |
| [`product-refinement-v2.2.md`](product-refinement-v2.2.md) | **The** release worklist — one per release, covering core, `ui/`, MCP and experiments together (constitution §4.1). Drafted, **not started, premise under review** — its goal is a better *drop* detector, and the `experiments/drop_detection/` survey argues drops should be derived from section transitions rather than detected. |

### Experiments

[`../experiments/drop_detection/README.md`](../experiments/drop_detection/README.md)
— the hand-built drop detector and the 2026-09 pretrained-model survey
(`allin1`, MERT, CLAP, beat-this), with reproducible measurements against
hand-labelled ground truth. This is the current best evidence about what the
structural stages actually do.

## Archive — [`archive/`](archive/)

45 story specs, the v2.1 release plan and worklist, the former
`Implementation_Guide.md`, the `UI v2` rebuild close-out, and the working
checkpoint. Kept so that measured dead ends stay visible rather than being
reinvented. See [`archive/README.md`](archive/README.md) for what is in there
and which parts the measurements have overtaken.
