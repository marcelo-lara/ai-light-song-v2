# Documentation map

`docs/` holds **current material only** — how the system is meant to behave now.
There is no archive folder: git history is the archive (constitution §4). If a
document here has stopped being true, fix it or delete it.

**Start at [`../CLAUDE.md`](../CLAUDE.md)** — the entry point for people and
models alike: what the system does, which stages are trusted, and what the
measurements say is broken.

## Contracts and law

| Doc | What it covers |
| --- | --- |
| [`constitution.md`](constitution.md) | Project law. §1 scope (musical facts, **not** fixture orchestration), §2 honesty, §3 the experiment lifecycle, §4 documentation, §6 time, §8 data governance, §9 change control. |
| [`data_folder_reference.md`](data_folder_reference.md) | Every file under `data/` and what produces it. The artifact contract. |
| [`source_files_reference.md`](source_files_reference.md) | Map of `src/` — where each pipeline stage lives. Update it when you move code. |
| [`docker_development.md`](docker_development.md) | Container runtime, GPU expectations, model caches. |

## Reference — [`reference/`](reference/)

| Doc | What it covers |
| --- | --- |
| [`analysis-input-guide.md`](reference/analysis-input-guide.md) | **The contract analysis quality is judged against.** Which artifacts reach the cue-authoring model, and which are invisible to it. A signal that lands in no projected file does not affect the show. |
| [`phase_1_validation_cli.md`](reference/phase_1_validation_cli.md) | `./analyze` flags, compare targets, exit codes, validation report shape. |
| [`ui_development.md`](reference/ui_development.md) | Debugger runtime and its read-only data contract. |
| [`ui-regression_guide.md`](reference/ui-regression_guide.md) | How to run and review the UI visual regression suite. |

## Open work

| Doc | State |
| --- | --- |
| [`issues.md`](issues.md) | The analysis-issue queue — **open issues only** (constitution §4.2). Currently empty. |

No release worklist is open. When one starts it is a single
`product-refinement-vX.Y.md` here covering core, `ui/`, MCP and experiments
together, and the previous one is deleted first — constitution §4.1.

## Measured evidence

[`../experiments/drop_detection/README.md`](../experiments/drop_detection/README.md)
— the hand-built drop detector and the 2026-09 pretrained-model survey
(`allin1`, MERT, CLAP, beat-this), with reproducible measurements against
hand-labelled ground truth. This is the current best account of what the
structural stages actually do, and it does not go stale with age.
