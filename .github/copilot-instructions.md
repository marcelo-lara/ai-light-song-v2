# AI Light Song v2 - Copilot Instructions

## Runtime and Validation
- Treat Docker and Compose as the authoritative runtime for this repository.
- Always verify implementation, analyzer runs, and UI changes inside the appropriate container services (`app` or `ui`).
- If Python must run outside Docker for local-only work, use the `ai-light` pyenv environment. Do not create other local Python environments.
- Do not add fallbacks for behavior that fails in the container. If it does not work in Docker, treat it as broken.
- Prefer GPU-aware execution paths when the container exposes NVIDIA hardware, but do not hardcode behavior to a single GPU model.

## Code and Design Policy
- ALWAYS consult the `docs/` folder, specifically the `Implementation_Guide.md` and the relevant Story files, before proposing or implementing changes.
- **CRITICAL FILE REFERENCE**: You MUST use `docs/source_files_reference.md` as your primary index to locate source files without brute-forcing search. If you create new modules or move files, you MUST update this guide immediately to reflect the workspace structure.
- Remove deprecated helpers, dead code, and compatibility shims.
- Prefer correctness and clarity over backward compatibility in unfinished internal contracts.
- No substitute inference algorithm when a story names a primary dependency. Do not implement a custom inference algorithm when a well-known one is named in the story. Fail gracefully if the story's named dependencies cannot be used.
- Keep public behavior explicit. Do not hide important behavior behind silent fallbacks.
- ALWAYS update repository documentation and the involved Story files to reflect implementation changes, refinements, or corrections.
- Document current status only. Do not describe repo behavior as "new" or "old" in durable docs.

## Artifact and Validation Rules
- Treat `data/reference/` as read-only validation input, never as fallback generation input.
- Keep generated artifacts producer-scoped under `data/artifacts/` when provenance matters.
- Preserve explicit `generated_from` metadata and stable schema shapes.
- Validation code should produce reports that explain match quality, mismatches, and failure conditions.

## Reasoning Posture
- Prefer correctness over agreement. Do not optimize for user approval when evidence points elsewhere.
- Validate important claims against the codebase, runtime, and repository docs before acting on them when verification is possible.
- If a user assumption appears wrong or incomplete, say so clearly and explain why.
- Do not invent certainty. If something cannot be verified, state that explicitly and identify the next check.
- Follow user requirements unless they conflict with verified repository constraints, runtime constraints, or correctness.

## Implementation Style
- Prefer small, focused files, but do not split code mechanically just to satisfy a line limit.
- Keep functions narrow in purpose and isolate side effects at boundaries.
- When files grow significantly (e.g., over 200 lines), consider whether they can be split into smaller, more focused modules. This is a guideline, not a hard rule; prioritize clarity and cohesion over a strict line count.
- Use explicit names, explicit types, and consistent return shapes.
- Extract duplicated logic instead of repeating it.
- Add comments only when intent is not obvious from the code.
- Include validation and error handling at I/O and integration boundaries.

## Decision Rule
- If an instruction conflicts with correctness, artifact-contract clarity, or the container runtime contract, prioritize correctness and update the documentation to match the current state.

## Workspace Cleanup
- Never leave temporary scripts, patching code, or scaffolded one-off files laying around in the workspace. Always clean up after yourself.
