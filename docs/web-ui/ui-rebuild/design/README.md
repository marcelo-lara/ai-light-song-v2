# Design reference — Score Analysis DAW

Imported from the Claude Design project
`claude.ai/design/p/06705e66-fe17-476d-8f92-5edfb95e5810`
(file `Score Analysis DAW.dc.html`), design system **Nocturne**
`nocturne-7bb68ef7-5a06-4960-93bb-2c04d70976b8`.

| File | Notes |
| --- | --- |
| [`design-notes.md`](design-notes.md) | The human-readable spec: Nocturne tokens, layout, per-lane rendering, interactions, artifact mapping, and what the mock is missing. **Start here.** |
| [`Score-Analysis-DAW.dc.html`](Score-Analysis-DAW.dc.html) | The canvas markup + its `<script type="text/x-dc">` component logic, verbatim. The markup is the layout reference; the script is the behavioural reference (it is not executed — it targets the canvas's own runtime). |

## Not vendored here

- `_ds/nocturne-…/styles.css` — Nocturne's token + component stylesheet. It is
  **not** copied into `docs/` (it is design-system source, not project docs); the
  tokens it defines are tabulated in `design-notes.md` §1, and the implementation
  vendors the file itself into `ui/src/styles/nocturne.css` (plan item 1).
- `_ds/nocturne-…/_ds_bundle.js`, `support.js` — the Claude Design canvas runtime
  (`<x-dc>` / `DCLogic` → React renderer). Not relevant to the rebuild, which is
  a normal React app.
- `_ds/nocturne-…/readme.md` — Nocturne's own styling guide; its rules are the
  styling contract and are summarised in `design-notes.md` §1.
