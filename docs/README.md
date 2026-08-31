# Documentation Map

**Active release:** [product-refinement-v1.1.md](product-refinement-v1.1.md)
(worklist and version convention) →
[implementation-plan-v1.1.md](implementation-plan-v1.1.md) (ordered work).

Story specs are grouped by the *kind of work* they describe, so the music-feature
inference layer can be maintained and improved in isolation.

| Folder | Contents | Nature |
|--------|----------|--------|
| [`human-curated/`](human-curated/) | Artifacts and workflows owned by a human: reference/benchmark data, the review-and-override loop, the lighting-score target format. | Hand-authored ground truth |
| [`audio-processing/`](audio-processing/) | Deterministic DSP and feature math: timing grid, FFT bands, loudness, HPCP/chroma, key, alignment, energy/symbolic/event feature derivation. | Pure math, byte-reproducible |
| [`audio-inference/`](audio-inference/) | The music-understanding layer: ML models (stems, embeddings, chords, MIDI/drum transcription, section SSM, event classifier) plus the rule-based baselines, event vocabularies, identifier inference and LLM-friendly abstractions that feed or compete with them. | Interpretation of audio |
| [`lighting-score/`](lighting-score/) | Epic 7 generation stage: unified feature-layer assembly, feature-to-lighting mapping, fixture-aware orchestration. | Feature → lighting transform |
| [`web-ui/`](web-ui/) | Epic 8 internal debugger, the `build_ui_data` contract, the offline visualizer export, UI issue/regression notes, and the active [`web-ui/ui-rebuild/`](web-ui/ui-rebuild/) (React + TS rebuild as the "Score Analysis DAW" design). | Web interface |

Cross-cutting docs stay at `docs/` root: [`constitution.md`](constitution.md),
[`Implementation_Guide.md`](Implementation_Guide.md),
[`data_folder_reference.md`](data_folder_reference.md),
[`source_files_reference.md`](source_files_reference.md),
[`docker_development.md`](docker_development.md), [`issues.md`](issues.md), and
[`source references/`](source%20references/).

## Improving inferences

To improve how the pipeline understands a musical feature, work almost entirely
inside [`audio-inference/`](audio-inference/):

1. The upstream deterministic inputs are specified in `audio-processing/` and are
   assumed correct — change them only if the feature math itself is wrong.
2. Ground truth and benchmarks live in `human-curated/`.
3. Downstream consumers (`lighting-score/`, `web-ui/`) read published contracts;
   keep those contracts stable while iterating on the inference internals.
