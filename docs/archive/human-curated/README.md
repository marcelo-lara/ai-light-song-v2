> **ARCHIVED — historical record, not a specification.**
> This document describes how something was *planned or built at the time*. It
> is **not** a description of current behaviour and may contradict the code.
> Do not treat it as a contract and do not implement from it: verify against
> `src/` first. For what the system does today, read `CLAUDE.md` at the repo
> root.

# Human-Curated Artifacts

Docs describing artifacts a person authors, reviews, or corrects — the ground
truth the automated pipeline is measured against.

| Doc | What it covers |
|-----|----------------|
| [5.5.event_review_and_benchmark_story.md](5.5.event_review_and_benchmark_story.md) | Confidence/review/override workflow and benchmark-annotation tuning for musical events. |
| [lighting_score_template.md](../../reference/lighting_score_template.md) | Canonical human-readable format the generated `lighting_score.md` must match. |

Related data on disk: `data/analysis/<Song - Artist>/reference/` (human hints,
Moises reference, benchmark annotations). The UI editor that writes human hints is
specified in [../web-ui/8.8.human_hint_editor_story.md](../web-ui/8.8.human_hint_editor_story.md).
