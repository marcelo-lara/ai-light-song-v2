# Audio Inference (Music Understanding)

The layer that turns processed features into a musical interpretation. This is the
place to iterate when improving how the pipeline understands a feature.

Includes trained ML models **and** the deterministic rule-based baselines,
vocabularies, and abstractions that feed or compete with them — kept together so a
feature can be improved end to end in one folder.

| Group | Docs |
|-------|------|
| ML models | 1.1 stem separation, 1.5 perceptual embedding, 2.2 chord detection, 2.4 MIDI transcription, 2.5 drums transcription, 3.1 section segmentation (neural SSM), 5.3 ML event classifier & training, 5.4 advanced event classification, 5.9 ML penalty logic |
| Structure understanding | 3.2 structural integrity audit |
| Identifier / event inference | 4.5 song identifier inference, 5.1 event vocabulary & schema, 5.2 rule-based event detection, 5.6 event timeline export |
| Guidance & abstraction | 6.1 genre guidance, 6.2 section hints, 6.3 unified LLM-friendly song map |

Upstream deterministic inputs: `../audio-processing/`. Ground truth & benchmarks:
`../human-curated/`. Keep published contracts stable for `../lighting-score/` and
`../web-ui/` while changing inference internals.
