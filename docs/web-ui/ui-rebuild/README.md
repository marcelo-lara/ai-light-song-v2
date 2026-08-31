# Web UI Rebuild (UI v2) — shipped

The internal artifact debugger in `ui/` was rebuilt from scratch as the
**"Score Analysis DAW"** design, on **React + TypeScript + Vite** with
**wavesurfer.js** as the audio player and master clock. Internal debugger only —
the constitution's "not a production consumer experience" rule stands.

**Status:** items 1–11 complete and committed (one commit per item). The
pre-rebuild Preact/MUI app was removed at cutover (item 11); nothing in the repo
references it. The `ui-v2` git tag is **held** pending the D3 live-browser
visual / interaction parity pass — see the *Parity sign-off (item 11)* section of
the archived plan.

Defects and refinements found during the D3 parity pass are collected in
[`product-refinement-ui-v2.1.md`](product-refinement-ui-v2.1.md) (active
worklist) and planned in
[`implementation-plan-ui-v2.1.md`](implementation-plan-ui-v2.1.md) (8 items,
one commit each; item 1 stands up a Playwright visual-regression suite under
`tests/ui-visual/`).

| File | What it is |
| --- | --- |
| [`design/design-notes.md`](design/design-notes.md) | Nocturne tokens, layout anatomy, per-lane spec (incl. §3a — the FFT/RMS/Envelope palette carried verbatim from the previous app), the 3-mode right panel, and how each lane maps onto a real analyzer artifact. |
| [`design/Score-Analysis-DAW.dc.html`](design/Score-Analysis-DAW.dc.html) | The Claude Design canvas markup + behavioural script, verbatim, as the visual/interaction reference. |
| [`archive/implementation-plan.md`](archive/implementation-plan.md) | The completed, checkboxed, one-commit-per-item plan (items 1–11), the D1–D8 decision log, and the item-11 **parity sign-off** table + dev/prod serve + no-writes-grep results. |
| [`archive/product-refinement.md`](archive/product-refinement.md) | The intent + scoped worklist (`R1`–`R10`), parity checklist (signed off in item 11), decisions, out-of-scope. |

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
