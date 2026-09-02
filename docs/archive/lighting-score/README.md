> **ARCHIVED — historical record, not a specification.**
> This document describes how something was *planned or built at the time*. It
> is **not** a description of current behaviour and may contradict the code.
> Do not treat it as a contract and do not implement from it: verify against
> `src/` first. For what the system does today, read `CLAUDE.md` at the repo
> root.

# Lighting Score Generation (Epic 7)

Transforms the validated music-feature layers into lighting behavior. Downstream
of `../audio-inference/`; consumes published contracts only.

| Doc | What it covers |
|-----|----------------|
| [7.1.music_feature_layers_story.md](7.1.music_feature_layers_story.md) | Assembles harmonic/symbolic/energy/pattern layers into one cross-layer artifact with deterministic timing anchors. |
| [7.3.energy_to_lighting_mapping.md](7.3.energy_to_lighting_mapping.md) | Fixture-agnostic mapping from features to normalized lighting behaviors and cue anchors. |
| [7.4.fixture_aware_mapping_story.md](7.4.fixture_aware_mapping_story.md) | Fixture-aware orchestration and final `lighting_score.md` generation. |

Target output format: [../human-curated/lighting_score_template.md](../../reference/lighting_score_template.md).
