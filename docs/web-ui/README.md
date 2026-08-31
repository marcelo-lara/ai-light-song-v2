# Web UI Interface

The internal artifact debugger (Epic 8), the data contract it reads, the offline
visualizer export, and UI issue/regression notes. Read-only against generated
data (except the human-hint editor, 8.8).

**Active work:** [`ui-rebuild/`](ui-rebuild/) — a from-scratch **React + TypeScript**
rebuild of the debugger (`UI v2`) as the "Score Analysis DAW" design, with
wavesurfer.js as the audio player. The Epic 8 stories below are the behaviour
parity reference and are updated per plan item as the rebuild lands.

| Group | Docs |
|-------|------|
| Rebuild (active) | [ui-rebuild/product-refinement.md](ui-rebuild/product-refinement.md), [ui-rebuild/implementation-plan.md](ui-rebuild/implementation-plan.md), [ui-rebuild/design/design-notes.md](ui-rebuild/design/design-notes.md) |
| UI data contract | 7.2 build_ui_data |
| Visualizer | 7.5 beatdrop offline visualizer export |
| Debugger shell | 8.1 auto-discovery, 8.2 master sync & waveform anchor, 8.3 DAW-style lanes, 8.6 semantic zoom & performance |
| Lanes | 8.4 sparse data lanes, 8.5 high-density lanes, 8.7 regression validation overlay, 8.9 identifier & ML event lanes |
| Editing | 8.8 human hint editor (writes `reference/human/human_hints.json`) |
| Notes | ui-issues.md, ui-issues_console.log, ui-regression_guide.md |
