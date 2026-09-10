# UI development — lane recipes

Mechanical `ui/` procedures. Follow literally; do not re-derive from source.

Rules and context (read only if the task needs a *decision*, not a *change*):
[`../ui-definition.md`](../ui-definition.md) (what the debugger may read/write,
badging rule), [`ui-regression.md`](ui-regression.md) (visual QA).

Worked precedent: `git show 7695d9e` (add lane). Removal precedent: plan v3.0
item 14 in git history.

## Commands (Docker only — never host npm)

```bash
docker compose up ui                       # dev server → http://localhost:9090
docker compose run --rm ui npm run test    # vitest — must pass
docker compose run --rm ui npm run build   # tsc + vite — must be clean
docker compose run --rm test               # analyzer tests — baseline unchanged
```

---

## Recipe A — add a sparse (block) lane

Use for any time-bearing block/event data. 8 code files + 4 docs. Do every
step; the lane silently renders empty if one is missed.

**Substitutions used below.** Fill these in once, then apply verbatim.

| Token | Meaning | Example |
| --- | --- | --- |
| `<laneId>` | camelCase lane id, used as the key everywhere | `fooBar` |
| `<Type>` | PascalCase type prefix | `FooBar` |
| `<file>.json` | filename under `reference/proposals/` | `foo_bar.json` |
| `<experiment>` | dir name under `experiments/` | `foo_bar` |
| `<Label>` | human lane label — **must match `<experiment>`**: same short name, or the experiment's item number in front. Never a free-choice prose label. | `Foo Bar` or `3. Foo Bar` for `experiments/foo_bar` |

### 1. `ui/src/data/paths.ts` — add to `artifactPaths`

```ts
  // Written by experiments/<experiment> (`run export`). <one line: what it is>.
  <laneId>: (song: string) =>
    encodePath(analysis(song, "reference", "proposals", "<file>.json")),
```

### 2. `ui/src/data/sparseArtifacts.ts` — types, parser, loader

Append a section. Helpers `num` / `st` / `arr` / `rec` already exist at the top
of the file. Parser must be tolerant (never throw). Loader must map 404 → empty.

```ts
// ---------------------------------------------------------------------------
// <laneId> — reference/proposals/<file>.json
// ---------------------------------------------------------------------------
//
// <1-3 lines: producer, what a block means, that it is a proposal not truth.>

export interface <Type>Block {
  start_s: number;
  end_s: number;
  // ... your fields; nullable numbers as `number | null`
}

export interface <Type>File {
  schema_version: string;
  song_name: string;
  blocks: <Type>Block[];
}

export function parse<Type>(raw: unknown): <Type>File {
  const o = asObject(raw, "reference/proposals/<file>.json");
  const blocks: <Type>Block[] = [];
  for (const row of arr(o.blocks)) {
    const r = rec(row);
    blocks.push({ start_s: num(r.start_s), end_s: num(r.end_s) /* , ... */ });
  }
  blocks.sort((a, b) => a.start_s - b.start_s);
  return { schema_version: st(o.schema_version), song_name: st(o.song_name), blocks };
}

export async function load<Type>(
  song: string,
  f?: typeof fetch,
): Promise<LoadResult<<Type>File>> {
  const result = await loadJson(artifactPaths.<laneId>(song), parse<Type>, f);
  if (!result.ok && result.error.kind === "http" && result.error.status === 404) {
    return { ok: true, data: { schema_version: "", song_name: song, blocks: [] } };
  }
  return result;
}
```

Also add `<laneId>` to the file-list in the module header comment (line 1-3).

### 3. `ui/src/data/loaders.ts` — 2 edits

```ts
import { ..., load<Type> } from "./sparseArtifacts";   // existing import block

export const artifactLoaders = {
  ...
  <laneId>: load<Type>,                                 // add one line
} as const;
```

### 4. `ui/src/timeline/laneContent.ts` — 5 edits

**4a.** Add `<Type>File` to the `import type { ... } from "../data/sparseArtifacts";` block.

**4b.** Add the adapter. Required `SparseBlock` fields: `id`, `start_s`,
`end_s`, `label`, `laneLabel`, `caption`, `reference`, `detail`, `summary`,
`raw`. Optional: `wideLabel` (drawn when the block is wide), `tintId`
(per-block tint override). `formatRange(a, b)` and `round(v, digits)` are
already defined in this file.

```ts
/**
 * <what it is> from `experiments/<experiment>`. A proposal to audition against
 * Human Hints, not ground truth.
 */
export function <laneId>Content(file: <Type>File | null): SparseBlock[] {
  return (file?.blocks ?? []).map((b, i) => ({
    id: `<laneId>-${i + 1}`,
    start_s: b.start_s,
    end_s: b.end_s,
    label: /* SHORT — blocks are narrow at overview zoom */ "",
    wideLabel: "",
    laneLabel: "<Label>",
    caption: `${formatRange(b.start_s, b.end_s)} · ...`,
    reference: `<laneId>-${i + 1}`,
    detail: "",
    summary: `experiments/<experiment> — ...`,
    raw: b,
  }));
}
```

Never substitute a value for a `null` field. Print the gap instead
(`"initial state"`, `"no confidence reported"`, `"DISPUTED"`).

**4c.** `LaneContentSources` interface: add `<laneId>?: <Type>File | null;`

**4d.** `SPARSE_LANE_IDS` array: add `"<laneId>",` in registry order.

**4e.** `buildLaneBlocks` switch: add

```ts
    case "<laneId>":
      return <laneId>Content(s.<laneId> ?? null);
```

### 5. `ui/src/timeline/laneState.ts` — add the `LANE_DEFS` row

Array position = top-to-bottom lane order. Put experiment lanes **below** the
hand-authored lanes they are auditioned against (`humanHints`, `moisesLyrics`).

```ts
  { id: "<laneId>", label: "<Label>", sub: "experiment · <what it shows>", kind: "proposals", height: 58, experiment: "<experiment>" },
```

- `kind: "proposals"` unless the lane needs a different renderer. A new `kind`
  = new `LaneKind` union member + new `renderLaneBody` branch in `App.tsx`.
- `experiment:` present ⇒ `ph-flask` badge renders. **Omit it** for lanes fed
  from `reference/human/` or `reference/moises/`.
- Add `"<laneId>"` to `DEFAULT_EXPANDED` only if it must be open on first load.

### 6. `ui/src/timeline/sparseTints.ts` — add to `BASE`

```ts
  <laneId>: [<hue>, <sat>, <light>], // <colour name> — distinct from <neighbour hues>
```

Existing hues to avoid colliding with: humanHints 35, reactiveBands 50,
arrangementState 95, characterShadow 96, vocalPhrasesSustained 280,
dropProposals 318, vocalPhrases 340, sections 174, chords 193, gridPhrase 188,
moisesLyrics 210, character 275, gestures 10.

Add a second entry (e.g. `<laneId>Disputed`) for every `tintId` the adapter emits.

### 7. `ui/src/App.tsx` — 3 edits

```ts
const TIMELINE_KEYS = [ ..., "<laneId>" ] as const;              // 7a

const SPARSE_LANE_ARTIFACT = { ..., <laneId>: "<laneId>" };      // 7b

const laneContentSources = useMemo<LaneContentSources>(
  () => ({ ..., <laneId>: artifacts.<laneId>.data }),            // 7c (object)
  [ ..., artifacts.<laneId>.data ],                              // 7c (deps array — both)
);
```

### 8. `ui/src/timeline/laneContent.test.ts` — add coverage

Import `<laneId>Content` and `type <Type>File`. Add three `it()` cases minimum:

```ts
describe("<laneId>Content", () => {
  const file: <Type>File = { schema_version: "1.0", song_name: "_test_song", blocks: [ /* 2 rows */ ] };
  const blocks = <laneId>Content(file);

  it("labels a normal block", () => { expect(blocks[0]!.label).toBe("..."); });
  it("renders a null field honestly", () => { expect(blocks[1]!.caption).not.toMatch(/.../); });
  it("never throws on a missing file", () => { expect(<laneId>Content(null)).toEqual([]); });
});
```

### 9. Docs — 4 files

| File | Edit |
| --- | --- |
| [`../ui-definition.md`](../ui-definition.md) | add a row to the Lanes table |
| [`ui-regression.md`](ui-regression.md) §5.5 | bump the flask-badge lane count + list |
| [`../experiments.md`](../experiments.md) | the experiment's entry says the lane exists |
| `experiments/<experiment>/README.md` | same |

### 10. Validate

Run all four Docker commands. `npm run build` must be tsc-clean. Then confirm
the wiring is complete:

```bash
grep -rn "<laneId>" ui/src --include=*.ts --include=*.tsx | cut -d: -f1 | sort -u
```

Expect exactly these 8 files: `App.tsx`, `data/loaders.ts`, `data/paths.ts`,
`data/sparseArtifacts.ts`, `timeline/laneContent.ts`,
`timeline/laneContent.test.ts`, `timeline/laneState.ts`,
`timeline/sparseTints.ts`. Fewer ⇒ a step was missed.

---

## Recipe B — remove a sparse lane

Reverse order of Recipe A. Delete, never leave the loader "working".

1. `laneState.ts` — delete the `LANE_DEFS` row; delete any `DEFAULT_EXPANDED`
   entry; delete the `LaneKind` member if now unused.
2. `App.tsx` — delete from `TIMELINE_KEYS`, `SPARSE_LANE_ARTIFACT`, the
   `laneContentSources` object **and** its deps array.
3. `laneContent.ts` — delete the adapter, the type import, the
   `LaneContentSources` field, the `SPARSE_LANE_IDS` entry, the `switch` case.
4. `laneContent.test.ts` — delete the `describe` block.
5. `sparseTints.ts` — delete every `BASE` entry for the lane.
6. `loaders.ts` — delete the `artifactLoaders` line and the import.
7. `sparseArtifacts.ts` — delete the section (interfaces, parser, loader) and
   the header-comment mention.
8. `paths.ts` — delete the `artifactPaths` accessor.
9. Docs — reverse the four edits in Recipe A step 9.
10. Verify: `grep -rn "<laneId>" ui/src docs experiments` returns nothing.
11. Run all four Docker commands.

If the lane is removed because the experiment was **promoted into `src/`**:
state in the commit message where the content now lives on the production
surface. Ask the user before promoting anything into `src/`.

---

## Recipe C — add a dense (canvas) lane

Rare. Body is `CanvasLane` + a draw function in `timeline/laneRenderers.ts`.

1. `data/paths.ts` — accessor for the essentia artifact.
2. `data/loaders.ts` — plain `loadJson` loader (**no** 404→empty; core
   artifacts must fail loudly) + `artifactLoaders` entry.
3. `App.tsx` — add key to `TIMELINE_KEYS`; add
   `<laneId>: { key: "<laneId>", kind: "<rendererKind>" }` to `CANVAS_LANES`.
4. `timeline/laneRenderers.ts` — add `<rendererKind>` to the
   `CanvasLaneSource` union and its draw branch.
5. `timeline/laneState.ts` — `LANE_DEFS` row, `kind` matching, `height` 84–112.
6. Tests: `CanvasLane.test.tsx`, `laneGeometry.test.ts`.

---

## Recipe D — one-file changes

| Task | File | Edit |
| --- | --- | --- |
| Rename lane label / sub-caption | `timeline/laneState.ts` | `LANE_DEFS` row `label` / `sub` only. **Never** change `id` — that is the wiring key across 8 files. |
| Reorder lanes vertically | `timeline/laneState.ts` | move the `LANE_DEFS` row; array order = render order. |
| Change which lanes open on load | `timeline/laneState.ts` | `DEFAULT_EXPANDED`. A user's `localStorage` (`als.timeline.laneState.v1`) overrides it. |
| Retint a lane | `timeline/sparseTints.ts` | `BASE[<laneId>]`. One `[hue, sat, light]`; alpha comes from the shared `FILL_A`/`STROKE_A`. |
| Add a per-block tint | `laneContent.ts` + `sparseTints.ts` | adapter emits `tintId: "<laneId><Variant>"`; add that key to `BASE`. Precedent: `dropProposalsMatched`, `gridDisputed`. |
| Add/remove the flask badge | `timeline/laneState.ts` | presence of `experiment:` on the `LaneDef`. |
| Change lane row height | `timeline/laneState.ts` | `height` (collapsed is always `COLLAPSED_LANE_HEIGHT` = 26). |

---

## Invariants (do not break)

1. **404 ⇒ empty lane.** Only status 404 maps to an empty file. Every other
   error propagates and renders the lane's error state.
2. **Parsers coerce, adapters do not invent.** A missing optional field renders
   as a stated gap, never a plausible default.
3. **One lane, one artifact key** in `SPARSE_LANE_ARTIFACT`. A lane needing two
   producers joins them inside the adapter from two `LaneContentSources` fields
   (precedent: `sectionsContent` joins `sections` + `sectionSegmentation` by
   `section_id`).
4. **The debugger writes only** `reference/human/human_hints.json`,
   `reference/human/song_facts.json` and `reference/human/block_energy.json`
   (the last is the Human Hints panel's per-block `energy`/`tension` rating,
   `PUT /api/block-energy/<song>`, v3.4 item 4), on explicit Save. Nothing in
   `src/` or `mcp/` reads any of them. Any other write is a new contract — stop
   and ask. (v3.4 item 5 adds `reference/human/lyric_validations.json` as a
   fourth.)
5. **Docs update in the same change** as the code (Recipe A step 9).
