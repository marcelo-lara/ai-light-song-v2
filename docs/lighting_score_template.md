# Lighting Score Template Specification

## Purpose

Define the stable output structure for `lighting_score.md` so the generated score is both human-readable and consistent across songs.

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
- global energy arc
- strongest lifts and release windows
- structural observations that matter for lighting

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
- intensity guidance
- movement guidance
- accent behavior
- any special transition behavior

### Song-Specific Rules

Capture fixed instructions that should remain true across the whole song.

Expected content:

- persistent color mapping
- maximum brightness or aggression caps
- repeated phrase rules
- special fixture constraints

## Deterministic vs Optional Narrative

Deterministic pipeline content should provide:

- timing windows
- structural summaries
- palette mapping rules
- fixture-role assignments
- repeatable section intent rules

Optional LLM-refined prose may improve readability, but it must not invent contradictions or unsupported musical claims.

## Output Path

- `data/output/<Song - Artist>/lighting_score.md`

## Validation

- The generated score must include every required section.
- Timing windows must match the analyzed section windows.
- The prose must remain faithful to the structured analysis artifacts.