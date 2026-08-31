# Web UI Rebuild (UI v2)

A from-scratch rebuild of the internal artifact debugger in `ui/` as the
**"Score Analysis DAW"** design, on **React + TypeScript + Vite** with
**wavesurfer.js** as the audio player and master clock. Internal debugger only —
the constitution's "not a production consumer experience" rule stands.

| File | What it is |
| --- | --- |
| [`product-refinement.md`](product-refinement.md) | Intent + scoped worklist (`R1`–`R10`), parity checklist, decisions, out-of-scope. |
| [`implementation-plan.md`](implementation-plan.md) | Ordered, checkboxed, one-commit-per-item plan (items 1–11) with the two standing handoff rules and the container test commands. |
| [`design/design-notes.md`](design/design-notes.md) | Nocturne tokens, layout anatomy, per-lane spec (incl. §3a — the FFT/RMS/Envelope palette carried verbatim from `ui.old`), the 3-mode right panel, and how each lane maps onto a real analyzer artifact. |
| [`design/Score-Analysis-DAW.dc.html`](design/Score-Analysis-DAW.dc.html) | The Claude Design canvas markup + behavioural script, verbatim, as the visual/interaction reference. |

## Scope

- **React + TS + Vite**, wavesurfer.js as player **and** master clock; the old
  app moves to `ui.old/` in item 1's commit (reference) and is deleted at
  cutover; internal-debugger constraint kept. **Target: Chrome 151 only.**
- Time-proportional timeline x (bars drift with tempo). Sticky header is
  **Segments + Bars only** — no conductor / tempo / "global" track.
- **All** lanes from `laneDefinitions.js` ship; the design's five expanded, the
  rest **collapsed by default**, all toggle-able from a lane list.
- **Click any lane block → read-only detail in the right panel** (+ playhead
  seek). The right panel is one shell, three modes: block inspector (read-only),
  hint editor, review-queue editor (functional first version).

**Source design:** Claude Design project `06705e66-…`, file
`Score Analysis DAW.dc.html`, design system **Nocturne** (`7bb68ef7-…`). Nocturne's
`styles.css` is the token source of truth and is vendored into the rebuilt app
unchanged.

The Epic 8 story files (`docs/web-ui/8.*.md`) remain the **behaviour parity**
reference and are updated per plan item as the rebuild lands.
