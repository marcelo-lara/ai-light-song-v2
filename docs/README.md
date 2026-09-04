# Documentation map

`docs/` holds **current material only** — how the system is meant to behave now.
Git history is the archive (constitution §4): if a document here has stopped
being true, fix it or delete it. The single exception is
[`archive/experiments.md`](archive/experiments.md), the standing record of
concluded experiments defined in §3.4.

**Start at [`../CLAUDE.md`](../CLAUDE.md)** — the entry point for people and
models alike: what the system does, which stages are trusted, and what the
measurements say is broken.

## Contracts and law

| Doc | What it covers |
| --- | --- |
| [`constitution.md`](constitution.md) | Project law. §1 scope (musical facts, **not** fixture orchestration), §2 honesty, §3 the experiment lifecycle, §4 documentation, §5 the four pipeline phases, §7 time, §9 data governance, §10 change control. |
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
| [`experiments_pending.md`](experiments_pending.md) | The experiment queue (constitution §3.4). One entry per experiment, carrying its plan, its measured results and its conclusion. A concluded entry leaves this file only when the operator picks archive or promote. |
| [`archive/experiments.md`](archive/experiments.md) | Concluded experiments and what they scored. The one archive file §4 permits. |

## Open release — v3.0

One refinement doc and one plan, per constitution §4.1. Both are open.

| Doc | State |
| --- | --- |
| [`product-refinement-v3.0.md`](product-refinement-v3.0.md) | The scoped items behind the wave-2 module verdicts — what is deleted, what is replaced, the decisions taken and the risks accepted. |
| [`implementation-plan-v3.0.md`](implementation-plan-v3.0.md) | The 16 ordered items that execute it. One commit per item, validated in the container before it is pushed. |
| `contract-change-v3.0.md` | The downstream handoff note. Created by plan item 5 and extended as each contract-changing item lands. |

## Measured evidence

Reproducible measurements against hand-labelled ground truth. This is the
current best account of what the structural stages actually do, and it does not
go stale with age (constitution §4).

| Experiment | What it establishes |
| --- | --- |
| [`../experiments/drop_detection/README.md`](../experiments/drop_detection/README.md) | The hand-built drop detector and the 2026-09 pretrained-model survey (`allin1`, MERT, CLAP, beat-this). |
| [`../experiments/allin1/README.md`](../experiments/allin1/README.md) | Named functional structure from All-In-One, exported per song and rendered as two debugger lanes. Beats the incumbent segmentation at less than half its boundary budget. **Not promoted.** |
| [`../experiments/clap/README.md`](../experiments/clap/README.md) | What CLAP infers *beyond* the arrangement: a character layer (breath / void / vocal lead / full power) built from the stems, CLAP's calm axis and allin1's frame-level shadow labels. Also the negative identity result that sets the MFCC baseline. **Not promoted.** |
