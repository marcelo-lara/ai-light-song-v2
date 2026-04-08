# Lighting Score Template Specification

## Purpose

Define the stable output structure for `lighting_score.md` so the generated score is both human-readable and consistent across songs.

The score is intended to be the final structured handoff for an LLM-guided light-show authoring step. Exact timing must come from deterministic analysis artifacts, while the LLM is allowed to refine wording, emphasis, and visual rationale without inventing unsupported times or musical claims.

## Required Upstream Analysis And Artifacts

The score contract assumes these upstream inputs already exist and are internally consistent:

- canonical beat and bar timing from Story 1.2
- section windows and labels from Story 4.2
- accent windows, peaks, dips, and energy transitions from Story 4.3
- phrase-aligned symbolic timing and phrase-grouping anchors from Story 3.3
- motif-level and repeated-phrase summaries from `layer_b_symbolic.json`
- harmonic progression-pattern occurrences from `layer_d_patterns.json`
- unified timing and cross-layer references from `music_feature_layers.json`
- fixture-aware or fixture-ready lighting events from Story 5.5

If those inputs are incomplete, the score may still be readable, but it is not complete enough to serve as a reliable LLM light-show prompt.

## Preferred Upstream Reference Fields

When the upstream artifacts expose IDs and timing references, the lighting-score pipeline should prefer these canonical field names:

- `phrase_windows[].id`, `phrase_windows[].phrase_group_id`, `phrase_windows[].start_s`, `phrase_windows[].end_s`
- `motif_summary.dominant_motif_id`, `motif_summary.motif_groups[].id`, `motif_summary.repeated_phrase_groups[].id`
- `patterns[].id`, `patterns[].occurrences[].start_s`, `patterns[].occurrences[].end_s`
- `lighting_context.cue_anchors[].id`, `lighting_context.cue_anchors[].time_s`, `lighting_context.cue_anchors[].anchor_type`
- `lighting_context.pattern_callbacks[].pattern_id`, `lighting_context.pattern_callbacks[].callback_action`
- `lighting_context.motif_callbacks[].motif_group_id`, `lighting_context.motif_callbacks[].callback_action`

## Required Sections

### Metadata

Must include:

- song title
- artist
- duration
- BPM
- time signature
- key
- high-level energy trend
- high-level brightness trend

### Feature Summary

Summarize the most important musical and energy findings that affect the show design.

Expected content:

- harmonic or loop identity
- motif or repeated-phrase identity when present
- global energy arc
- strongest lifts and release windows
- structural observations that matter for lighting

### Timing Anchors

Surface the exact deterministic timing anchors that the light show must respect.

Expected content:

- exact section start and end times in seconds
- phrase start and end anchors when available
- accent windows, hits, and transition timestamps
- bar-aligned change points that should drive cue changes
- repeated pattern occurrence windows that should trigger repeated or intentionally varied looks

### Visual Strategy

Describe the overall visual language of the song.

Expected content:

- palette logic
- movement philosophy
- contrast strategy
- section boundary treatment

### Fixture Intentions

Describe how each fixture role behaves.

Expected content:

- main moving-head role
- FX moving-head role
- parcan role
- supporting wash or pulse role

### Section Plan

Include one subsection per inferred section window.

Each subsection must include:

- section label
- start and end time in seconds
- phrase or bar-level cue anchors inside the section when available
- intensity guidance
- movement guidance
- accent behavior
- repeated-pattern or motif callback behavior
- any special transition behavior

### Song-Specific Rules

Capture fixed instructions that should remain true across the whole song.

Expected content:

- persistent color mapping
- maximum brightness or aggression caps
- repeated phrase rules
- pattern callback rules and allowed variation rules
- special fixture constraints

## Deterministic vs Optional Narrative

Deterministic pipeline content should provide:

- exact timing windows
- phrase anchors and bar-aligned change points
- accent anchors and transition timestamps
- structural summaries
- motif and repeated-phrase summaries
- harmonic pattern identities and occurrence times
- palette mapping rules
- fixture-role assignments
- repeatable section intent rules

Optional LLM-refined prose may improve readability, but it must not invent contradictions, unsupported musical claims, or exact times not present in the structured artifacts.

## Output Path

- `data/output/<Song - Artist>/lighting_score.md`

## Compact Example Skeleton

This is a structural example only. It shows how deterministic timing anchors and callback rules should appear in the score. It is not a generated song result.

```md
# Lighting Score

## Metadata
- Song: Song - Artist
- Duration: 210.473s
- BPM: 125
- Time Signature: 4/4
- Key: D major

## Feature Summary
- Dominant harmonic loop: pattern_A
- Dominant motif group: motif_alpha
- Global energy arc: restrained intro, rising pre-chorus, high-drive chorus

## Timing Anchors
- Section `intro`: 0.00s -> 15.36s
- Phrase `phrase_group_A_1`: 1.23s -> 4.88s
- Cue anchor `anchor_intro_1_downbeat`: 1.23s
- Pattern occurrence `pattern_A` occurrence 1: 8.00s -> 15.80s

## Visual Strategy
- Use low-motion cool washes in the intro.
- Escalate movement speed and contrast on repeated harmonic callbacks.

## Fixture Intentions
- `moving_head_main`: carry large section changes and chorus pushes.
- `moving_head_fx`: answer motif callbacks with tighter motion.

## Section Plan
### intro
- Window: 0.00s -> 15.36s
- Cue anchors: 1.23s, 4.88s, 8.00s
- Callback rule: first `motif_alpha` occurrence is restrained; repeated occurrence may echo with added width.

## Song-Specific Rules
- Reuse `pattern_A` callbacks with controlled color variation.
- Do not move cue times away from deterministic anchors.
```

## Validation

- The generated score must include every required section.
- Exact timestamps must match the analyzed section, phrase, accent, and pattern-occurrence windows when those anchors are available upstream.
- Repeated motifs and harmonic patterns must be reflected consistently in callback or variation rules.
- The prose must remain faithful to the structured analysis artifacts.