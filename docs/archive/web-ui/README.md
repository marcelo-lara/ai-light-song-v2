> **ARCHIVED — historical record, not a specification.**
> This document describes how something was *planned or built at the time*. It
> is **not** a description of current behaviour and may contradict the code.
> Do not treat it as a contract and do not implement from it: verify against
> `src/` first. For what the system does today, read `CLAUDE.md` at the repo
> root.

# Web UI Interface

The internal artifact debugger (Epic 8), the data contract it reads, the offline
visualizer export, and UI issue/regression notes. Read-only against generated
data (except the human-hint editor, 8.8).

**Current app:** `UI v2` — a from-scratch **React + TypeScript + Vite** rebuild of
the debugger as the "Score Analysis DAW" design, with wavesurfer.js as the audio
player and master clock. Shipped (items 1–11 committed); the `ui-v2` tag is held
pending a live-browser parity pass (D3). The pre-rebuild Preact/MUI app was
removed at cutover. The Epic 8 stories below are the behaviour parity reference;
each carries a "UI v2 component map" section.

| Group | Docs |
|-------|------|
| Rebuild (shipped, archived) | [ui-rebuild/README.md](ui-rebuild/README.md), [ui-rebuild/design/design-notes.md](../../reference/ui-design/design-notes.md), [ui-rebuild/archive/implementation-plan.md](ui-rebuild/archive/implementation-plan.md) (parity sign-off), [ui-rebuild/archive/product-refinement.md](ui-rebuild/archive/product-refinement.md) |
| UI data contract | 7.2 build_ui_data |
| Visualizer | 7.5 beatdrop offline visualizer export |
| Debugger shell | 8.1 auto-discovery, 8.2 master sync & waveform anchor, 8.3 DAW-style lanes, 8.6 semantic zoom & performance |
| Lanes | 8.4 sparse data lanes, 8.5 high-density lanes, 8.7 regression validation overlay, 8.9 identifier & ML event lanes |
| Editing | 8.8 human hint editor (writes `reference/human/human_hints.json`) |
| Notes | ui-issues.md, ui-issues_console.log, ui-regression_guide.md |
