# Web UI Rebuild (UI v2) — shipped

The internal artifact debugger in `ui/` was rebuilt from scratch as the
**"Score Analysis DAW"** design, on **React + TypeScript + Vite** with
**wavesurfer.js** as the audio player and master clock. Internal debugger only —
the constitution's "not a production consumer experience" rule stands.

**Status:** UI v2 items 1–11 complete and committed. The follow-on **UI v2.1**
polish-and-fix pass (D3 live-browser parity defects + refinements) is also
**complete** — all 10 plan items implemented and committed one per item, plus a
Playwright visual-regression suite under `tests/ui-visual/`. Both passes are
archived under [`archive/`](archive/). The pre-rebuild Preact/MUI app was removed
at cutover (item 11); nothing in the repo references it.

Defects and refinements from the D3 parity pass were collected in
[`archive/v2.1/product-refinement-ui-v2.1.md`](archive/v2.1/product-refinement-ui-v2.1.md)
and worked through
[`archive/v2.1/implementation-plan-ui-v2.1.md`](archive/v2.1/implementation-plan-ui-v2.1.md)
(10 items; item 1 stood up the visual-regression suite). The living
visual-regression reference is
[`../ui-regression_guide.md`](../ui-regression_guide.md).

| File | What it is |
| --- | --- |
| [`design/design-notes.md`](design/design-notes.md) | Nocturne tokens, layout anatomy, per-lane spec (incl. §3a — the FFT/RMS/Envelope palette carried verbatim from the previous app), the 3-mode right panel, and how each lane maps onto a real analyzer artifact. |
| [`design/Score-Analysis-DAW.dc.html`](design/Score-Analysis-DAW.dc.html) | The Claude Design canvas markup + behavioural script, verbatim, as the visual/interaction reference. |
| [`archive/implementation-plan.md`](archive/implementation-plan.md) | UI v2: the completed, checkboxed, one-commit-per-item plan (items 1–11), the D1–D8 decision log, and the item-11 **parity sign-off** table + dev/prod serve + no-writes-grep results. |
| [`archive/product-refinement.md`](archive/product-refinement.md) | UI v2: the intent + scoped worklist (`R1`–`R10`), parity checklist (signed off in item 11), decisions, out-of-scope. |
| [`archive/v2.1/implementation-plan-ui-v2.1.md`](archive/v2.1/implementation-plan-ui-v2.1.md) | UI v2.1: the completed 10-item polish-and-fix plan (harness, `B1`/`B2` bug fixes, refinements `R1`–`R7`), each item with its per-item resolution notes and Visual QA block. |
| [`archive/v2.1/product-refinement-ui-v2.1.md`](archive/v2.1/product-refinement-ui-v2.1.md) | UI v2.1: the intent + scoped worklist for the parity-pass defects and refinements. |

## What shipped

- **React + TS + Vite**, wavesurfer.js as player **and** master clock.
  **Target: Chrome 151 only.** Build target `esnext`.
- Time-proportional timeline x (bars drift with tempo). Sticky header is
  **Segments + Bars only** — no conductor / tempo / "global" track.
- All 17 lanes from the old `laneDefinitions.js` ship; the design's five
  expanded, the rest collapsed by default, all toggle-able from the lane list.
  `validation` (Regression Overlay) ships as an empty-state stub (D6).
- **Click any lane block → read-only detail in the right panel** (+ playhead
  seek). The right panel is one shell, three modes: block inspector (read-only),
  hint editor, review-queue editor (functional first version).
- Dev-server `/data` mount + `PUT /api/human-hints/<song>` +
  `PUT /api/song-facts/<song>` in `ui/vite.config.ts` — the only two writers of
  `data/analysis/**`, both behind a path-escape guard.
- `ui/Dockerfile` — the `dev` stage (Vite) is the Compose `ui` service; the
  `final` stage (nginx, `listen 8080`) is the prod build. Both verified serving
  in item 11.

**Source design:** Claude Design project `06705e66-…`, file
`Score Analysis DAW.dc.html`, design system **Nocturne** (`7bb68ef7-…`). Nocturne's
`styles.css` is the token source of truth and is vendored into the app unchanged.

The Epic 8 story files (`docs/web-ui/8.*.md`) remain the **behaviour parity**
reference; each carries a "UI v2 component map" section pointing at the shipped
files.
