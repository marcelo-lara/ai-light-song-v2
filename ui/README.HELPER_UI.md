# Internal Artifact Debugger — UI v2 (Score Analysis DAW)

Internal visual debugger for the analyzer's artifacts under
`data/analysis/<Song - Artist>/artifacts/`. **Not** the production consumer UI.

This is the from-scratch React + TypeScript + Vite rebuild
(`docs/web-ui/ui-rebuild/`). The previous Preact/MUI app is kept at `ui.old/` as
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

## File map (as of plan item 1)

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
| `src/data/saveHumanHints.ts` | `buildHumanHintsPayload` (ui.old's hint-editor validation) + `saveHumanHints` `PUT /api/human-hints/<song>` client |
| `src/data/index.ts` | Barrel re-export for the data layer |
| `src/data/__fixtures__/` | Trimmed real `_test_song` artifacts for the parser/discovery unit tests |
| `src/data/*.test.ts` | vitest: parsers (against fixtures), discovery filter, loader error mapping, hint-payload validation |
| `src/timeline/` `src/panel/` | Empty — populated by plan items 3–9 |
| `vite.config.ts` | Vite + React plugin; `build.target: esnext`; vitest (`jsdom`) config; `data-mount-plugin` = `/data` static mount + directory listing + `PUT /api/human-hints/<song>` (ported from `ui.old/vite.config.js`, incl. path-escape guard + byte-range). Not in a `tsconfig` (build tooling, transpiled by esbuild — as `ui.old`'s `.js` config was). |
| `tsconfig.json` | `strict` (+ `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, no-unused), `target`/`module` `esnext`; `include: ["src"]` |
| `Dockerfile` | `deps` → `dev` (Vite) / `build` (tsc + vite) → `final` (nginx) |
| `nginx.conf` | Static serve + SPA fallback + read-only `/data/` autoindex |

## Plan item status

Item 1 (this tree) delivers the shell only. Data layer, timeline, lanes, panels,
inspector, review queue and keyboard model follow in items 2–10; parity sign-off
and `ui.old/` deletion is item 11. See
`docs/web-ui/ui-rebuild/implementation-plan.md`.
