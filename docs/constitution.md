# Project Constitution: ai-light-song-v2

## 1. Mission Statement
To build a deterministic, musically intelligent pipeline that transforms raw audio into high-fidelity lighting design documents and fixture-aware orchestration.

## 2. Core Architectural Pillars

### 2.1 Spec-Driven Development (SDD)
- **Contracts First:** Implementation never begins without a Story spec. The spec defines the schema, inputs, and acceptance criteria.
- **Documentation as Truth:** If the code and the documentation disagree, the documentation is assumed to be correct until a formal spec change occurs.
- **Living Specifications:** Stories and specifications must be updated to reflect final implementation details. A task is not considered "done" until the corresponding Story file accurately reflects the current codebase.
- **Modular Epics:** The pipeline is divided into independent Epics (Audio, Harmonic, Symbolic, Energy, Events, Unified, UI).

### 2.2 Determinism and Reproducibility
- **Same Input, Same Output:** Given the same audio file and model version, the pipeline must produce byte-for-byte identical JSON artifacts.
- **No Hidden State:** All parameters must be explicit. No opportunistic mid-run downloads or reliance on non-versioned external APIs.

### 2.3 Environment Isolation
- **Docker is Authoritative:** The only valid development and execution environment is the project's Docker container. 
- **Always Test in Container:** All analysis logic, validation runs, and UI behaviors must be tested and verified within their respective Docker services (`app` or `ui`). Proposing host-side executions or host-installed dependencies is a constitutional violation.
- **GPU Dependency:** The system is optimized for NVIDIA/CUDA runtimes. CPU fallbacks are for debugging only and must not be used for canonical artifact generation.

## 3. Data Governance

### 3.1 Folder Sanctity
- **`data/reference/`**: Source of truth for validation. Read-only (except for Story 7.8 human hints).
- **`data/artifacts/`**: Machine-readable intermediate analysis. Read-only for the UI. Must use producer-scoped subfolders.
- **`data/output/`**: Stable UI contract. Must contain exactly the files specified in the `layer_manifest.md`.

### 3.2 Immutability
- Once an artifact is written to `data/artifacts/`, it is considered a historical record of that pipeline run. 
- The Internal Debugger (UI) is strictly forbidden from writing to `artifacts` or `output`.

## 4. Development Standards

### 4.1 Error Handling
- **Fail Explicitly:** The pipeline must never use silent fallbacks (e.g., if a chord model fails, do not invent a generic "C" major chord; fail the run or mark it as `unknown`).
- **Provenance:** Every generated file must include a `generated_from` block identifying the source files, engine version, and timestamps.

### 4.2 Code Quality
- **Logic Separation:** Keep analysis logic (`src/`) entirely separate from visualization logic (`ui/`).
- **Subprocess Isolation:** In batch mode, analyze each song in a separate subprocess to prevent memory/GPU state contamination between tracks.

## 5. Collaboration Contract (Human & AI)
- The AI (Gemini Code Assist) is a co-architect. It must respect these constitutional rules when proposing code or refactors.
- Every new feature must be introduced via a "Story" file in the `docs/` folder before being implemented in `src/`.

---
*Last Updated: 2026-04-20*
*Status: Active*