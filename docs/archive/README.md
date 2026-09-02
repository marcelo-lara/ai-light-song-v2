# Archive — historical process records

Everything in this folder is a **record of how the project got here**: story
specs, release worklists, implementation plans, and close-out notes. None of it
is a description of current behaviour, and none of it is a contract.

**Do not implement from these files.** They are kept because a documented dead
end is more useful than a forgotten one — knowing that an approach was tried
and how it turned out stops it from being reinvented. But a stale plan read as
a spec is exactly how wrong work gets started, so every file here opens with an
`ARCHIVED` banner.

For what the system actually does today: **`CLAUDE.md` at the repo root**, then
[`../reference/`](../reference/).

## What's in here

| Path | What it is |
| --- | --- |
| [`Implementation_Guide.md`](Implementation_Guide.md) | The former "canonical hub": epic/story ordering and repository contracts. Superseded by `CLAUDE.md` (stage map, now derived from `src/analyzer/pipeline.py`) and [`../data_folder_reference.md`](../data_folder_reference.md) (artifact contracts). |
| [`audio-processing/`](audio-processing/) | Story specs for the deterministic DSP stages (timing grid, FFT bands, loudness, HPCP, energy and symbolic feature derivation). The stages themselves are live and in good shape; only these *documents* are historical. |
| [`audio-inference/`](audio-inference/) | Story specs for the music-understanding stages (stems, chords, transcription, section segmentation, the event vocabulary and its rule/ML detectors). Several describe approaches the 2026-09 model survey measured as not working — see below. |
| [`lighting-score/`](lighting-score/) | Epic 7 story specs: feature-layer assembly, feature→lighting mapping, fixture-aware orchestration. |
| [`web-ui/`](web-ui/) | Epic 8 debugger story specs, the `UI v2` rebuild close-out and its parity archive, and the UI issue log. The shipped app is in `ui/`; its design reference stayed live at [`../reference/ui-design/`](../reference/ui-design/). |
| [`human-curated/`](human-curated/) | The event review/benchmark story. The lighting-score output format stayed live at [`../reference/lighting_score_template.md`](../reference/lighting_score_template.md). |
| [`implementation-plan-v2.1.md`](implementation-plan-v2.1.md), [`product-refinement-v2.1.md`](product-refinement-v2.1.md) | The v2.1 release worklist and its ordered plan. Shipped. |
| [`contract-change-v2.1.md`](contract-change-v2.1.md) | The v2.1 handover note to the downstream MCP server. Historical; the change it describes is already in the artifacts. |
| [`issues-solved.md`](issues-solved.md) | Closed analysis issues, moved out of `../issues.md` as they were solved (constitution §4.2). Kept for their evidence and validation notes. |
| [`mcp-server-implementation-plan.md`](mcp-server-implementation-plan.md) | A per-component plan for the in-repo MCP server. Never built, and now forbidden as a parallel track (constitution §4.1) — fold any surviving item into the single product-refinement. The component's definition stayed live at [`../reference/mcp-server-product-definition.md`](../reference/mcp-server-product-definition.md). |
| [`next_steps.md`](next_steps.md) | A working checkpoint of release state as of 2026-09-01. Replaced by `CLAUDE.md` — pointing a reader at process state instead of system behaviour was the specific problem this archive exists to fix. |

## Read these with the measurements in hand

The `experiments/drop_detection/` survey (2026-09) measured the structural
stages against hand-labelled ground truth and against off-the-shelf baselines.
Two results change how several documents here should be read:

- The shipped section segmentation (`3.1.section_segmentation_story.md`) scores
  **0/7 boundaries within ±1.0 s** of a human-marked impact — below a 20-line
  librosa baseline. The story describes the intended design faithfully; the
  design does not work.
- The whole Epic 5/6 event stack downstream of it inherits that segmentation,
  so its story specs describe behaviour built on a foundation the data does not
  support.

Full write-up and reproduction: [`../../experiments/drop_detection/README.md`](../../experiments/drop_detection/README.md).

## Why archiving instead of deleting

The constitution's *"Documentation as Truth"* rule (§2.1) says that when code
and docs disagree, the docs win until a formal spec change. That rule is what
turned 45 story files into apparent specifications for behaviour that has since
changed or been measured as wrong. Moving them here inverts the default for
this folder only: **inside `docs/archive/`, the code wins.** The rule still
stands for [`../reference/`](../reference/) and the root contracts.
