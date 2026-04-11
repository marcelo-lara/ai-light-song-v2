# Lighting Score Template Specification

## Purpose

Define the stable output structure for `lighting_score.md` so the generated score is both human-readable and consistently usable as an LLM handoff.

The score has two layers:

- a deterministic core derived from analysis artifacts
- an optional curation layer that helps a human reviewer add intent, priorities, and rig-aware interpretation without inventing unsupported timings

Exact timing must come from structured upstream artifacts. Optional prose may improve readability, emphasis, and show-planning clarity, but it must not contradict the deterministic analysis.

## Required Upstream Analysis And Artifacts

The score contract assumes these upstream inputs already exist and are internally consistent:

- canonical beat and bar timing from Story 1.2
- section windows and labels from Story 4.2
- accent windows, peaks, dips, and energy transitions from Story 4.3
- phrase-aligned symbolic timing and phrase-grouping anchors from Story 3.3
- motif-level and repeated-phrase summaries from `layer_b_symbolic.json`
- harmonic progression-pattern occurrences from `layer_d_patterns.json`
- unified timing and cross-layer references from `music_feature_layers.json`
- fixture-aware or fixture-ready lighting events from Story 6.5

If those inputs are incomplete, the score may still be readable, but it is not complete enough to serve as a reliable LLM light-show prompt.

## Title Format

The final markdown document title must use this exact format:

```md
# <Song Title> - Lighting Score
```

Use the human-facing song title, not the full `Song - Artist` compound string, unless the title itself contains that separator.

## Preferred Upstream Reference Fields

When the upstream artifacts expose IDs and timing references, the lighting-score pipeline should prefer these canonical field names:

- `phrase_windows[].id`, `phrase_windows[].phrase_group_id`, `phrase_windows[].start_s`, `phrase_windows[].end_s`
- `motif_summary.dominant_motif_id`, `motif_summary.motif_groups[].id`, `motif_summary.repeated_phrase_groups[].id`
- `patterns[].id`, `patterns[].occurrences[].start_s`, `patterns[].occurrences[].end_s`
- `lighting_context.cue_anchors[].id`, `lighting_context.cue_anchors[].time_s`, `lighting_context.cue_anchors[].anchor_type`
- `lighting_context.pattern_callbacks[].pattern_id`, `lighting_context.pattern_callbacks[].callback_action`
- `lighting_context.motif_callbacks[].motif_group_id`, `lighting_context.motif_callbacks[].callback_action`

## Deterministic Core Sections

These sections form the stable machine-authored contract and should always be present in the final score.

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

Recommended helper fields when available:

- song id
- genre
- energy profile
- mood tags
- reference songs or styles
- a short human summary of how the song should feel live

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
- human-editable hint lines from `data/output/<Song - Artist>/hints.json` when available
- any special transition behavior

### Song-Specific Rules

Capture fixed instructions that should remain true across the whole song.

Expected content:

- persistent color mapping
- maximum brightness or aggression caps
- repeated phrase rules
- pattern callback rules and allowed variation rules
- special fixture constraints

## Recommended Curation Layer

These sections are optional but strongly recommended when the score is reviewed, edited, or handed to an LLM for richer show planning.

### Rig Context

Use this section to summarize the practical rig setup in plain language.

Helpful fields:

- fixture source file
- rig notes
- fixture behavior notes for the LLM

### Global Show Intent

Use this section to describe the overall artistic direction and any hard show constraints.

Helpful fields:

- artistic direction
- strobe or white-light caps
- top-priority visual moments
- safe-mode notes

### Section Summary

Provide a compact table of the main structural sections with energy and lighting intent.

This is a human-friendly summary layer, not a replacement for the exact `Timing Anchors` or `Section Plan` sections.

### Canonical Event Vocabulary Reference

When event-aware planning is enabled, include the canonical event names most relevant to the song so human editors and LLMs use the same vocabulary.

### Event Timeline

Summarize the most important musical events using one canonical event name per row.

Each row should include:

- time
- event type
- intensity
- confidence
- what happens musically
- lighting meaning
- notes to the LLM

This section is especially useful when Story 5.8 exports a compact event timeline.

### Priority Moments

Identify the top moments where the show must visibly change.

Helpful fields:

- time
- event type
- why it matters
- whether the show must change there
- priority level
- notes

### Event-to-Lighting Guidance

Use this section to explain how recurring event types should be treated for this specific song when the generic event vocabulary is too broad.

### Color And Mood Arc

Describe how the palette should evolve across the song.

### Motion Arc

Describe how motion should enter, widen, freeze, or ease back across the song.

### Human Override Notes

Capture subjective or artistic constraints that the raw analysis cannot know.

### Compact LLM Handoff Summary

Provide a short briefing block the LLM can read before generating detailed cue language.

Suggested fields:

- song feel
- main event types
- top three moments
- lighting strategy
- things to avoid
- rig constraints

### Optional Machine-Readable Block

An optional JSON block may be included near the end of the document to make the score easier to pass into later structured tooling.

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

## Related Output

- `data/output/<Song - Artist>/hints.json`

## Compact Example Skeleton

This is a structural example only. It shows how deterministic timing anchors and helper sections may appear in the score. It is not a generated song result.

```md
# Song - Lighting Score

## Metadata
- Song: Song
- Artist: Artist
- Duration: 210.473s
- BPM: 125
- Time Signature: 4/4
- Key: D major
- High-level energy trend: restrained intro, rising pre-chorus, high-drive chorus

## Rig Context
- Fixtures file: fixtures.json
- Rig notes: keep pars as the readable wash layer and reserve the main moving head for large section changes.

## Global Show Intent
- Start restrained and moody.
- Save the biggest contrast for the final major release.

## Feature Summary
- Dominant harmonic loop: pattern_A
- Dominant motif group: motif_alpha
- Global energy arc: restrained intro, rising pre-chorus, high-drive chorus

## Timing Anchors
- Section `intro`: 0.00s -> 15.36s
- Phrase `phrase_group_A_1`: 1.23s -> 4.88s
- Cue anchor `anchor_intro_1_downbeat`: 1.23s
- Pattern occurrence `pattern_A` occurrence 1: 8.00s -> 15.80s

## Event Timeline
| Time | Event Type | Intensity | Confidence | What Happens Musically | Lighting Meaning | Notes to LLM |
|---:|---|---|---|---|---|---|
| 15.36 | build | medium | high | Energy and tension increase | Start visible escalation | Grow movement without peaking too early |
| 31.04 | drop_explode | very high | high | Full release with bass and transient impact | Main burst moment | Use one of the top looks here |

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
- Hint: Treat the first phrase as the establishing visual idea and keep later recalls visibly related.
- Callback rule: first `motif_alpha` occurrence is restrained; repeated occurrence may echo with added width.

## Compact LLM Handoff Summary
- Song feel: restrained opening, strong lift, high-contrast release.
- Main event types: build, drop_explode, groove_loop.
- Things to avoid: blowing full white before the main release.

## Song-Specific Rules
- Reuse `pattern_A` callbacks with controlled color variation.
- Do not move cue times away from deterministic anchors.
```

## Validation

- The generated score must use the required title format.
- The generated score must include every deterministic core section.
- Exact timestamps must match the analyzed section, phrase, accent, and pattern-occurrence windows when those anchors are available upstream.
- Repeated motifs and harmonic patterns must be reflected consistently in callback or variation rules.
- The prose must remain faithful to the structured analysis artifacts.