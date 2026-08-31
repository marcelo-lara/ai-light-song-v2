# Internal Artifact Debugger — UI v2 (Score Analysis DAW)

Internal visual debugger for the analyzer's artifacts under
`data/analysis/<Song - Artist>/artifacts/`. **Not** the production consumer UI.

This is the from-scratch React + TypeScript + Vite rebuild
(`docs/web-ui/ui-rebuild/`). The previous Preact/MUI app was kept as a reference copy as
the behaviour reference until cutover (plan item 11), then deleted.

## Non-negotiable rules

- Never write into `data/analysis/**` except the two explicit human-save paths:
  `reference/human/human_hints.json` (hint editor) and
  `reference/human/song_facts.json` (review-queue editor). Both write only on an
  explicit Save, via the dev-server `PUT` handlers.
- Read-only against every other artifact.
- Own Compose `ui` service, port `8080` (host `9090`). Not folded into the
  analyzer container.
- Every colour / font / space / radius / shadow comes from
  `src/styles/nocturne.css` tokens. Every icon is Phosphor.
- **Target browser: Chrome 151 only.** No cross-browser fallbacks, polyfills or
  autoprefixer. `tsconfig` / vite `build.target` = `esnext`.

## Runtime

- Dev: `docker compose up ui` → Vite dev server with live reload, `:8080`
  (mapped to host `:9090`).
- Prod: `docker compose run --rm ui npm run build` then the `final` nginx stage
  of `ui/Dockerfile` serves `dist/`.
- Validation (in the container):
  - `docker compose run --rm ui npm install`
  - `docker compose run --rm ui npm run build` — `tsc --noEmit` + vite bundle
  - `docker compose run --rm ui npm run test` — vitest + @testing-library/react

## Keyboard (plan item 10 / refinement §10)

Resolved by the pure `src/app/keymap.ts` module (`resolveKeyAction`); `App.tsx`
owns the single `window` `keydown` listener. Ignored while focus is in an
`input` / `textarea` / `select` / `contentEditable` (only `esc` passes through);
any Ctrl / Meta / Alt chord is ignored.

| Key | Action |
| --- | --- |
| `space` | play / pause |
| `←` / `→` | step ∓1 beat |
| `shift` + `←` / `→` | step ∓1 bar |
| `+` `=` `]` | zoom in |
| `-` `_` `[` | zoom out |
| `f` | fit timeline to width |
| `esc` | close, in order: right panel → review-queue view → lane list → drawer |

**§10 deviation:** refinement §10 groups "`+` / `-` / `[` / `]` = zoom" without
splitting the four keys, and plan item 10 guessed `[` `]` might be prev/next
section. §10's explicit word is "zoom", so all four are zoom — `]`/`+`/`=` in,
`[`/`-`/`_` out. No prev/next-section binding was added.

Focus management: `src/app/useFocusTrap.ts` traps Tab inside `RightPanel` while
open and restores focus to the opener on close. The drawer is a persistent,
non-modal nav — it takes initial focus on an open transition but is not trapped.

## File map

| Path | Role |
| --- | --- |
| `index.html` | Vite entry document, `#root` mount |
| `src/main.tsx` | React root; imports the four stylesheets then mounts `<App/>` |
| `src/App.tsx` | App shell: header (3-col grid) / main (drawer · timeline · right panel) / footer. Chrome only — lanes stubbed. |
| `src/App.test.tsx` | Smoke tests for the shell (bands, four drawer entries, active Timeline, stub lanes) |
| `src/test/setup.ts` | vitest setup — `@testing-library/jest-dom` matchers |
| `src/vite-env.d.ts` | Vite client type reference |
| `src/styles/nocturne.css` | Nocturne design-system tokens + component classes. Reproduced from `docs/web-ui/ui-rebuild/design/design-notes.md` §1 (the DS `styles.css` is not vendored in-repo). Treat as vendored — do not retune locally. |
| `src/styles/daw.css` | Interface-local timeline classes (`.tp` / `.zbtn` / `.caret` / `.dr-item` / range + `.tl` scrollbar) ported from the design canvas `<style>` block to tokens, plus the `--tl-*` timeline-chrome locals |
| `src/styles/app.css` | The fixed-band app-shell layout |
| `src/styles/phosphor/` | Phosphor regular-weight `style.css` + `Phosphor.woff2/woff/ttf`, vendored (no unpkg at runtime) |
| `src/data/types.ts` | TS types for every artifact the UI reads, mirroring the v1.1 contracts. v1.1-added fields typed `T \| null` so a pre-v1.1 song still parses. |
| `src/data/parse.ts` | Structural-assertion toolkit (`ShapeError`, `asNumber`, `stringOrNull`, …) shared by the parsers |
| `src/data/parsers.ts` | Pure `(raw: unknown) => T` parser per artifact; throws `ShapeError` on a contract mismatch. Enforces the v1.1 B5 `section_id` uniqueness rule. |
| `src/data/paths.ts` | `/data` URL builders (`artifactPaths`, `listingPaths`, `encodePath`) — every segment percent-encoded |
| `src/data/loaders.ts` | One fetch+parse loader per artifact → `LoadResult<T>` (`{ ok, data }` \| `{ ok, error }`, never throws). `artifactLoaders` registry + `ArtifactKey` / `ArtifactData<K>`. |
| `src/data/discovery.ts` | Directory-index HTML parsing; `intersectSongs` = analysis dirs ∩ `data/songs` audio basenames; `discoverSongs()` fetch wrapper |
| `src/data/useSong.ts` | Hook: given a song, loads `info.json` + requested artifacts; `{ status, data, error }` per key, stale-run guarded, `reload()` |
| `src/data/saveHumanHints.ts` | `buildHumanHintsPayload` (the previous app's hint-editor validation) + `saveHumanHints` `PUT /api/human-hints/<song>` client |
| `src/data/index.ts` | Barrel re-export for the data layer |
| `src/data/__fixtures__/` | Trimmed real `_test_song` artifacts for the parser/discovery unit tests |
| `src/data/*.test.ts` | vitest: parsers (against fixtures), discovery filter, loader error mapping, hint-payload validation |
| `src/app/keymap.ts` | Pure keyboard model: `resolveKeyAction(event) → KeyAction \| null` + the input-focus guard + `shouldPreventDefault`. Unit-tested. |
| `src/app/loadStates.ts` | Pure state selectors: `selectSongListState` (song picker) + `selectSongLoadState` (a song: loading / fatal / degraded / ready). Unit-tested. |
| `src/app/useFocusTrap.ts` | Tab-cycle trap + initial focus + restore-on-close for `RightPanel`. |
| `src/app/*.test.ts` | vitest: keymap resolution (incl. focus guard, §10 deviation), load-state selection |
| `src/timeline/coords.ts` | Time-proportional `timeToX` / `xToTime`, real-beat `beatToX` / `xToBeat`, bar grid, `timeToBarBeat`. |
| `src/timeline/zoom.ts` | `pxPerBar` clamp/step, `fitToWidthPxPerBar`, `semanticZoom` threshold table. |
| `src/timeline/follow.ts` | `followScrollLeft` follow-playhead scroll maths; `LABEL_WIDTH`. |
| `src/timeline/laneState.ts` | `useLaneState` — lane registry (`visible` / `expanded`), localStorage-persisted. |
| `src/timeline/TimelineGrid.tsx` `LaneList.tsx` | Sticky grid + playhead; the show/hide + expand/collapse panel. |
| `src/timeline/useTransport.ts` | wavesurfer master clock — `play/pause`, `seekTo`, `stepBeat`, `stepBar`; pure `nextBeatTime` / `nextBarTime`. |
| `src/timeline/WaveformLane.tsx` | Waveform Anchor lane (wavesurfer v7, blurple). |
| `src/timeline/CanvasLane.tsx` `laneRenderers.ts` `palette.ts` | DPR canvas lane body + `fft` / `rms` / `env` / `drums` / `energy` renderers + ported palette. |
| `src/timeline/SparseLane.tsx` `laneContent.ts` | Reusable block-lane body + per-lane content adapters. |
| `src/panel/RightPanel.tsx` | 296px modal shell, three modes; `esc` / outside-click dismiss; focus trap + restore (item 10). |
| `src/panel/BlockInspector.tsx` `blockFields.ts` | Read-only block detail card + per-lane field map. |
| `src/panel/HintEditorPanel.tsx` `hintDraft.ts` | Hint-editor mode + draft ↔ payload mapping. |
| `src/panel/ReviewQueuePanel.tsx` `reviewQueue.ts` | Review-queue mode + `partitionReviewQueue` / `questionOptions`. |
| `src/data/saveSongFacts.ts` | `buildSongFactsPayload` + `PUT /api/song-facts/<song>` client (merge, not rewrite — D4). |
| `src/inspector/ArtifactInspector.tsx` `walk.ts` `jsonTree.ts` | Read-only raw-JSON browser: recursive `/data` walk of `data/analysis/<song>` (D5) + collapsible tree. |
| `vite.config.ts` | Vite + React plugin; `build.target: esnext`; vitest (`jsdom`) config; `data-mount-plugin` = `/data` static mount + directory listing + `PUT /api/human-hints/<song>` (ported from the previous app's `vite.config.js`, incl. path-escape guard + byte-range). Not in a `tsconfig` (build tooling, transpiled by esbuild — as the previous app's `.js` config was). |
| `tsconfig.json` | `strict` (+ `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, no-unused), `target`/`module` `esnext`; `include: ["src"]` |
| `Dockerfile` | `deps` → `dev` (Vite) / `build` (tsc + vite) → `final` (nginx) |
| `nginx.conf` | Static serve + SPA fallback + read-only `/data/` autoindex |

## Plan item status

Items 1–10 are done: shell, data layer, timeline (coords / grid / zoom / follow /
transport / waveform / canvas + sparse lanes), right panel (inspector / hint /
review), artifact inspector, and the keyboard model + non-happy-path states +
focus management. Parity sign-off and removal of the previous app was item 11. See
`docs/web-ui/ui-rebuild/implementation-plan.md`.
