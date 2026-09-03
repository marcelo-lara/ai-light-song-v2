# Implementation Plan — UI v1.5

Nine independently-shippable items for the debugger UI (`ui/`), one per commit.
Nothing here touches `src/`, the analyzer, or any artifact contract — this
release is entirely the read-only debugger's interaction surface, so no
downstream handoff note is due (constitution §4, last bullet).

**This plan is self-contained.** The refinement doc it was drafted from has been
deleted; the operator's requirements are reproduced below word for word and are
the only statement of them that survives. Do not go looking for another source.

| ID | Requirement (verbatim, as the operator wrote it) |
| --- | --- |
| **R1** | "I want to see all events of a lane, stacked in the right panel, just like the current timeline but stacked (without intermediate spaces). When the song plays, highlight the active card." |
| **R2** | "To display the right panel with the stacked events, there should be an icon (use 'columns-plus-right') at right of `lane-head__name` (aligned to the right of the container div) when clicked, show this lane events replacing any other previous lane panel." |
| **R3** | "When playing, do not move the playhead position to the card I click on, just do nothing (right panel or events lane)." |
| **R4** | "when a song is selected, hide the left panel" |
| **R5** | "when click anywhere outside the left panel, hide the left panel" |
| **R6** | "add an icon (arrows-in-line-horizontal) to the left of the footer 'lanes' button: this icon is a toggle to follow the playhead when playing; if the user scrolls while playing, set the 'follow playhead off' so the lane position does not move." |
| **R7** | "flag lanes produced by not promoted experiments; add a 'flask' icon to the title left to let the user know that it is not a 'production' lane." |
| **R8** | "on infered block lanes, add a (rows-plus-bottom) icon displayed on the top right of the event ONLY when NOT playing and on hover -> this button should promote this particular event as a new entry on 'human hints' that could be edited (the goal of this item is to capture events that worths to be confirmed by a human)." |
| **R9** | "remove the 'app-header__barbeat-caption'." |
| **R10** | "reserve space in advance for time and barbeat. this is because both values are moving while the values changes." |

---

## How this plan is worked

- **Validate each item, then push it on its own.** Work one plan item at a
  time. When an item is complete, run its checks in the containers as the
  project requires (never on the host — constitution §8); only if they pass,
  tick its checkboxes — **both** the `- [ ]` boxes inside the item and its row
  in the Status table, which flips from `[ ] pending` to `[x] done` — then
  commit and push that item by itself before starting the next. Name the commit after the plan item as this plan writes it — for
  example ``3. Lane events panel + `columns-plus-right` opener``. One commit per
  item, never a single batch commit at the end: a later failure then cannot
  strand the validated work in front of it, and the history reads as this
  plan's own sequence.
- **Use the recommendation; only a genuinely blocking decision stops an item.**
  An open question that surfaces mid-implementation is resolved by adopting the
  best recommendation and continuing — do not idle waiting to ask. The
  exception is a decision where proceeding under any assumption would make the
  work wrong or wasted. In that case write the decision and its options into
  this plan as a new `D` item, then **continue with the next item**, skipping
  only those that genuinely depend on the blocked one. A single unresolved
  question must never stall the whole run; everything independent of it still
  gets built.

---

## Status

| # | Item | Requirements | State |
| --- | --- | --- | --- |
| 1 | A card click never moves the playhead while the transport is playing | R3 | [x] done |
| 2 | Left panel hides on song pick and on any outside click | R4, R5 | [x] done |
| 3 | Lane events panel + `columns-plus-right` opener | R1 (stack), R2 | [x] done |
| 4 | Active-card highlight and follow during playback | R1 (highlight) | [x] done |
| 5 | Header readout — drop the bar.beat caption, reserve the space | R9, R10 | [x] done |
| 6 | Follow-playhead toggle in the footer | R6 | [ ] pending |
| 7 | Flask badge on lanes fed by unpromoted experiments | R7 | [ ] pending |
| 8 | `captured_from` note on the human-hints schema | R8 (enabling half) | [ ] pending |
| 9 | “Create human hint” button in the block inspector | R8 (the button) | [ ] pending |

Order matters in three places, and nowhere else:

- item 1 defines the click rule items 3 and 9 obey;
- item 3 builds the panel item 4 highlights and item 7 badges;
- item 7 lands the `experiment` field on `LaneDef` that item 9's
  `captured_from` note reads, and item 8 lands the schema field item 9 writes.

Items 1, 2, 5 and 6 are independent of everything else. If an item blocks,
skip it and carry on with the next one that does not depend on it.

---

## Decisions already taken

These were resolved while writing the plan. Do not re-open them mid-run; if
one turns out to be wrong, log it per "When something fails after an item is
committed" below.

- **D1 — "just do nothing" (R3) means "do not seek".** A click on a card while
  playing still opens/updates the right panel exactly as it does today; only
  the `transport.seekTo` call is suppressed. Rationale: the complaint names the
  playhead specifically, and suppressing the whole click would make the block
  inspector unreachable during playback, which nothing in R3 asks for. The rule applies to **cards** — a sparse-lane block, a Segments
  header block, and a right-panel event card. It does **not** apply to clicks
  on empty lane background or on the Bars ruler: those exist to seek, and
  disabling them during playback would remove the only pointer-driven scrub.
- **D2 — a right-panel card click does not swap the panel.** Clicking a card in
  the lane events panel seeks (when paused, per D1) and nothing else. The panel
  stays on the same lane. Rationale: R2 says a lane panel is replaced by
  *another lane's* panel; swapping to the block inspector on every card click
  would make the stacked list unusable as a list.
- **D3 — the lane events panel is non-modal.** Unlike the inspector / hint /
  review modes, it must survive clicking Play, dragging the timeline and
  scrolling, because R1's whole point is watching it during playback. So it
  ships with no focus trap, no `aria-modal`, and no outside-click dismissal; it
  closes via its own ✕, via `esc`, via its lane's opener button, or on a song
  change. This requires a `modal` flag on the shared `RightPanel` shell
  (item 3).
- **D4 — R4 fires on a user picking a song, not on the `?song=` deep link.**
  Closing the drawer on every `song` change would break the persistence check
  in `tests/ui-visual/specs/left-panel.spec.ts` (open the drawer → reload →
  expect it still open), and a deep-linked load is not "selecting a song" in
  the sense the requirement means. Implement it in the picker's `onPick`.
- **D5 — a degenerate block (`end_s <= start_s`) is never the active card.**
  No invented minimum duration (constitution §2: no plausible defaults). It
  still renders as a card; it just never highlights.
- **D6 — "if the user scrolls while playing" is detected by elimination.** The
  follow effect writes `el.scrollLeft` itself, so the scroll listener cannot
  tell whose scroll it is observing without help. Record the value the effect
  last wrote and treat any observed offset further than 1 px from it as the
  user's. This covers wheel, trackpad, scrollbar drag and keyboard alike —
  where listening for `wheel`/`touchmove` would miss a scrollbar drag — and it
  is a pure function, so it is unit-testable without a browser (item 6).
- **D7 — the follow flag persists per session, default on.** It joins the lane
  state and the left-panel flag in `localStorage`. Default `true` keeps
  today's behaviour for a first-time load; the requirement asks for a way to
  turn following off, not for it to start off.
- **D8 — the flask means "from an unpromoted `experiments/` sandbox", not
  "unvalidated".** So it flags exactly the lanes fed by
  `reference/proposals/`: `dropProposals`, `allin1Transitions`,
  `allin1Sections`, `character`, `vocalTranscription`. It does **not** flag
  `machineEvents`, `mlEvents`, `sections` or the other `src/`-produced lanes —
  those ship in the production pipeline even where `CLAUDE.md` records them as
  untrusted, and conflating "experimental" with "unreliable" would make the
  badge mean nothing. It is the same set that leaves the lane registry when an
  experiment is promoted or abandoned (constitution §3.2).
- **D9 — the promote control lives in the right-panel block inspector, not on
  the timeline block.** Lane blocks are drawn on a canvas, so there is no
  element to hover and no place to hang a per-block button without
  hit-testing pointer moves and overlaying DOM on the canvas. The inspector is
  already the surface a block click opens, and it is where the event's details
  are read — which is exactly when the reader decides the event is worth
  capturing. **Operator's instruction, 2026-09-03.**
  This also settles which events qualify with no extra list: every selection
  the inspector can show. A Human Hints block never opens the inspector (App
  routes it to the hint editor), so the hand-authored lane cannot be its own
  source, and no `INFERRED_LANE_IDS` constant is needed.
- **D10 — promoting seeds an unsaved draft; it never writes to disk.**
  `reference/human/` is hand-authored ground truth (constitution §9, and
  `reference/` is validation-only). The button opens the hint editor with a
  pre-filled draft; the file changes only when the human presses Save, exactly
  as the existing "new hint" path works. Anything else would let the debugger
  manufacture ground truth from machine output.
- **D11 — a captured hint is indistinguishable from a hand-marked one, except
  for one informative string.** The saved hint carries `captured_from`: a single
  human-readable string naming the experiment or lane the event came from, for
  the benefit of whoever opens the file. Nothing reads it — it is not
  structured provenance, it is not consumed by any scoring or validation code,
  and no other field is added. Hand-authored hints omit the key entirely, so
  their shape is unchanged. **Operator's instruction, 2026-09-03**, overruling
  an earlier proposal for a structured `promoted_from: { lane, block_id }`
  object; that idea is closed, do not reintroduce it.
  The one thing to verify rather than assume: the analyzer must tolerate the
  extra key. Every Python reader goes through `.get(...)` on the hint dict
  (`src/analyzer/stages/hint_alignment.py`,
  `src/analyzer/stages/validation/form_drops.py`) and none validates against a
  strict schema — **re-confirm that with a grep before writing the field**, and
  if a strict validator has since appeared, extend it in the same commit.
- **D12 — the button shows in both transport states.** R8's "ONLY when NOT
  playing" was a property of the hover affordance: a control that appears under
  the pointer while the timeline is moving is noise. A panel button overlays
  nothing and appears only for an event the reader deliberately clicked, so
  hiding it mid-playback would just make the panel change shape while a song
  runs. If the operator wants the original constraint back it is one guard in
  `BlockInspector` plus one QA check — say so rather than re-deriving it.
- **D13 — promoting creates a plain new human hint; it never marks the source.**
  The experiment's own artifact under `reference/proposals/` is not written to,
  and no "confirmed" flag is set on the block. The action is the existing
  "new hint" flow with the fields pre-filled from the event.
  **Operator's instruction, 2026-09-03.**
- **D14 — the ten `.app-timeline__grid` screenshot baselines were already stale
  on the branch tip (`f421b48 checkpoint before ui changes`) before this run
  started.** Running the full Playwright suite against an unmodified checkout
  fails the same ten specs (`song-full`, `song-full-waveform`, `song-no-audio`,
  `left-panel`, `lane-collapsed`, `timeline-scrolled`, `timeline-zoom` min+max,
  `fit-to-width`, `hint-drag`) on pixel diffs. This pre-dates plan v1.5. Items
  that change no `.app-timeline__grid` pixels are validated on the delta (new
  spec green, no *new* failures) rather than on an impossible "zero
  `--update-snapshots`"; items 3 and 7 already mandate re-capturing this exact
  baseline set and will bring the suite fully green. Resolved 2026-09-03.

---

## Conventions for every item

**Everything runs in a container. Never on the host** (constitution §8).

```bash
# unit tests + typecheck/build (per item, always)
docker compose run --rm ui npm run test
docker compose run --rm ui npm run build      # tsc --noEmit + vite build

# visual regression: start the UI against the frozen fixture set …
docker compose -f docker-compose.yml -f docker-compose.visual.yml up -d --build ui
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:9090/    # expect 200

# … then run the suite in the pinned Playwright image
docker run --rm --network host -v "$PWD/tests/ui-visual:/work" -w /work \
  mcr.microsoft.com/playwright:v1.56.0-noble \
  sh -c "npm ci && npx playwright test"
# report: tests/ui-visual/report/index.html

# re-capture baselines (only when an item's Visual QA block says to)
docker run --rm --network host -v "$PWD/tests/ui-visual:/work" -w /work \
  mcr.microsoft.com/playwright:v1.56.0-noble \
  sh -c "npm ci && npx playwright test --update-snapshots"
```

**The regression harness already exists** — fixtures, the `data-ui-ready`
readiness marker, the runtime-assertion helper, the config and the initial
baselines all landed with an earlier release (see
[`reference/ui-regression_guide.md`](reference/ui-regression_guide.md) §9). No
item in this plan builds harness skeleton; each item **extends** the guide and
adds or re-captures the baselines its own block names.

**The executor contract** (guide §1) governs every Visual QA block below: run
every check, compare observed values against the stated expected values, report
each as pass/fail with the observed value, and never decide for yourself
whether something "looks reasonable". A check whose expected value this plan
fails to give is a spec defect to report back, not a judgement call.

**The visual suite never presses Play.** Audio playback in the pinned
Playwright container is unproven — no spec in the suite has ever decoded a
fixture mp3 — so no Visual QA block in this plan starts the transport, and none
asserts anything that requires `transport.isPlaying` to be true. Behaviour that
only happens while playing is covered instead by unit tests on the pure rules
that decide it (`seekTimeForCardClick`, `activeBlockIndex`, `isUserScroll`,
`followScrollLeft`), and by the operator auditioning the debugger against a real
song. **Operator's instruction, 2026-09-03.** Do not add a playback check to a
spec, and do not add a `data-ui-playing` marker to the app: with the playing
checks gone it would have no consumer (constitution §10).

**The two unchecked boxes in `reference/ui-regression_guide.md` §9 are out of
scope** — the `_test_song` audio question with Ops, and folding
`ui/README.HELPER_UI.md`'s smoke-check list into explicit assertions. They
predate this release. Leave them unticked and untouched; add only the §9 lines
this plan's own items name. **Operator's instruction, 2026-09-03.**

**Every Visual QA block starts with the guide §3 runtime assertions**
(`assertNoRuntimeErrors`): no `console.error` / `console.warn`, no `pageerror`
or unhandled rejection, no failed response for anything under
`/data/analysis/`. They are listed once here rather than repeated per item, but
they are mandatory in each.

**Primary fixture:** `RegFull - Fixture` (fully populated; `?song=RegFull%20-%20Fixture`).
Its frozen `human_hints.json` is the QA target for every block-list check —
three non-overlapping hints, recorded in guide §3.1:

| id | title | `start_time` | `end_time` |
| --- | --- | ---: | ---: |
| `hint-001` | Drop - approach | 40.0 | 48.0 |
| `hint-002` | drop build | 52.0 | 60.0 |
| `hint-003` | drop tension | 64.0 | 72.0 |

Header clock format is `m:ss.s` (`formatClock` in `ui/src/App.tsx`), so 52.0 s
reads `0:52.0` and 64.0 s reads `1:04.0`.

---

## 1. A card click never moves the playhead while the transport is playing

**Requirement:** R3. **Decisions:** D1.

### Deliverable

- [ ] `ui/src/app/transportRules.ts` (new) — one pure, exported rule:

      ```ts
      /**
       * R3: a click on a card (lane block, segment block, right-panel event
       * card) must not reposition the playhead while the transport is playing.
       * Returns the time to seek to, or null for "do not seek".
       */
      export function seekTimeForCardClick(playing: boolean, time: number): number | null;
      ```

      `playing === true` → `null`. `playing === false` → `time`.
- [ ] `ui/src/app/transportRules.test.ts` (new) — both branches, plus `time === 0`
      (must return `0`, not `null`: a falsy time is still a seek target).
- [ ] `ui/src/App.tsx` — `handleSelectMarker` and `handleSelectSegment` route
      their `transport.seekTo(...)` through `seekTimeForCardClick(transport.isPlaying, …)`
      and skip the call when it returns `null`. Everything else in both
      handlers (opening the hint editor, setting `selection`, setting
      `panelMode`) is unchanged.
- [ ] **Do not** touch `SparseLane`'s or `CanvasLane`'s background-click seek,
      or `TimelineGrid`'s Bars-ruler `seekFromEvent` (D1).

### Docs to update in this commit

- [ ] `reference/ui-regression_guide.md` §9 — add a ticked line for R3's spec.
- [ ] `tests/ui-visual/playwright.config.ts` header comment points at
      `../../docs/web-ui/ui-regression_guide.md`, which does not exist. Correct
      it to `../../docs/reference/ui-regression_guide.md` while you are here.

### Visual QA — item 1

New spec: `tests/ui-visual/specs/card-click-seek.spec.ts`. **No baseline
image**: this item changes no pixels. Confirming that is part of the QA.

Surface: `/?song=RegFull - Fixture`, awaited via `gotoSong` (readiness marker +
fonts). Human Hints is expanded by default, so its blocks are clickable without
any lane toggling; `page.mouse` does not auto-scroll, so bring a block into
view first the way `hint-drag.spec.ts`'s `lanePoint` helper does.

1. Guide §3 runtime assertions — all clean.
2. **Paused card click seeks.** Click the centre of the `hint-002` block on the
   `humanHints` lane. Header clock (`.app-header__time`) reads exactly `0:52.0`.
3. **And it opened the panel.** `.app-rightpanel` count === **1** (the
   `humanHints` lane routes to the hint editor).
4. Click the `hint-003` block. Clock reads exactly `1:04.0`.
5. **A segment card seeks too.** Click the **second** `.tl-seg-block` in the
   Segments header — the first starts at `0.0`, where the playhead may already
   be, so it proves nothing. The clock reads exactly `0:15.2`
   (`sections.json[1].start === 15.23` in the fixture; the Segments header is
   built from the top-level `sections.json`, not from any artifact under
   `artifacts/`).
6. **Background clicks still seek.** Click the Bars ruler at the horizontal
   centre of the *visible* timeline. Do not use `locator.click({ position })`:
   `.tl-ruler-body` is `timelineW` px wide and its box origin sits off-screen
   once the timeline has scrolled, so a position-relative click lands outside
   the viewport and Playwright rescrolls unpredictably. Instead read
   `timeline-viewport`'s box and `.tl-ruler-body`'s box and issue
   `page.mouse.click(vp.x + vp.width / 2, ruler.y + ruler.height / 2)`. The
   clock changes to a value > **20.0 s**.
7. **No pixel change:** run the whole suite; every existing baseline in
   `tests/ui-visual/__screenshots__/` passes with **zero** `--update-snapshots`.
   A baseline diff here means something else moved — investigate, do not
   re-capture.

> The playing half of R3 — that these same clicks do **not** seek while the
> transport runs — is covered by `transportRules.test.ts`, which is the whole
> rule in one pure function. The suite cannot press Play (see "Conventions for
> every item"), so do not try to assert it here.

---

## 2. Left panel hides on song pick and on any outside click

**Requirement:** R4, R5. **Decisions:** D4.

### Deliverable

- [ ] `ui/src/app/panelState.ts` — extend the existing pure module:

      ```ts
      /** Clicks inside these never dismiss the left panel. */
      export const LEFT_PANEL_KEEP_OPEN =
        '[data-testid="left-panel"], [data-testid="burger-toggle"]';

      /** R5: does this pointer target dismiss the left panel? */
      export function shouldDismissLeftPanel(open: boolean, target: Element | null): boolean;
      ```

      `true` only when `open` is `true`, `target` is non-null, and
      `target.closest(LEFT_PANEL_KEEP_OPEN)` is `null`. The burger must be
      excluded or the pair (`mousedown` closes → `click` toggles) would leave
      the drawer open on every burger press.
- [ ] `ui/src/app/panelState.test.ts` — truth table: target inside the drawer →
      `false`; target inside the burger → `false`; target elsewhere → `true`;
      `open === false` → `false`; `target === null` → `false`.
- [ ] `ui/src/App.tsx` — while `drawerOpen`, a document `mousedown` listener
      calls `setDrawerOpen(false)` when `shouldDismissLeftPanel` says so.
      `mousedown` (not `click`), matching `RightPanel`'s existing dismissal, so
      a drag that starts outside also closes it. Register only while open;
      remove on cleanup.
- [ ] `ui/src/App.tsx` — `SongPicker`'s `onPick` also calls
      `setDrawerOpen(false)` (R4/D4). Do **not** close on the `?song=` deep-link
      effect or on the `song`-change reset effect.
- [ ] Persistence is unchanged: the existing `saveLeftPanelOpen` effect records
      the closed state, which is intended — after picking a song the drawer
      stays closed across reloads.

### Docs to update in this commit

- [ ] `reference/ui-regression_guide.md` §2 — extend the `sidebar-expanded`
      row's notes with the new dismissal behaviour, so the surface table and
      the app agree.
- [ ] `reference/ui-regression_guide.md` §9 — ticked line for R4/R5's spec.

### Visual QA — item 2

Extend `tests/ui-visual/specs/left-panel.spec.ts` with a second `test(...)`
block (leave the existing one untouched — it is the R2/persistence regression
and must keep passing). **No new baseline image**; `left-panel-open.png` is
unchanged and must still pass.

Surface: `/?song=RegFull - Fixture`.

1. Guide §3 runtime assertions — all clean.
2. Click `burger-toggle`; `left-panel` has `data-open="true"`.
3. Click a drawer entry (`getByRole("button", { name: "Timeline" })`).
   `left-panel` still has `data-open="true"` — an inside click never dismisses.
4. Click the timeline viewport centre (`getByTestId("timeline-viewport")`).
   `left-panel` count === **0**.
5. Click `burger-toggle` → `data-open="true"`. Click `burger-toggle` again →
   `left-panel` count === **0** (proves the mousedown/click pair does not
   re-open it).
6. Click `burger-toggle` → open. Press `Escape` → count === 0 (unchanged
   existing behaviour, re-asserted because the new listener sits next to it).
7. **R4 path.** Navigate to `/` (no `?song=`) and wait for readiness. Click
   `burger-toggle` → open. Click the "Select Song" drawer entry. Click the
   `RegFull - Fixture` entry in the picker list. Then:
   `left-panel` count === **0**, and `page.url()` contains
   `song=RegFull+-+Fixture` or the percent-encoded equivalent.
8. Existing baselines: full suite green with zero `--update-snapshots`.

---

## 3. Lane events panel + `columns-plus-right` opener

**Requirement:** R1 (the stacked list), R2. **Decisions:** D1, D2, D3.

The highlight half of R1 is item 4 — this item ships the panel with no active
card.

### Deliverable

- [x] `ui/src/panel/RightPanel.tsx` — add `modal?: boolean` (**default `true`**,
      so the three existing modes are byte-identical in behaviour). When
      `modal === false`: skip `useFocusTrap`, skip the outside-`mousedown`
      dismissal, render `<aside role="complementary">` without `aria-modal`.
      Keep the `esc` handler and the ✕ button in both modes. (D3.)
- [x] `ui/src/panel/RightPanel.tsx` — `PanelMode` gains `"lane"`.
- [x] `ui/src/panel/LaneEventsPanel.tsx` (new) — the stacked list. Props:
      `laneId`, `laneLabel`, `blocks: readonly SparseBlock[]`,
      `status: ArtifactStatus`, `error: string | null`, `onClose`,
      `onSelectBlock(block)`. Renders inside `RightPanel` with `modal={false}`:
      - header: `<span className="app-rightpanel__kicker">{laneLabel}</span>`
        followed by `<span className="lane-events__count">{n} events</span>`;
      - body: `<ol className="lane-events" data-testid="lane-events-panel"
        data-lane={laneId}>`, one `<li>` per block **in `blocks` order** (the
        adapters already emit chronological order — do not re-sort), each
        holding `<button type="button" className="lane-events__card"
        data-testid={"lane-event-" + block.id} data-block-id={block.id}>`;
      - card content: `<span className="lane-events__label">{block.label}</span>`
        then `<span className="lane-events__caption">{block.caption}</span>`.
        Use `label`, never `wideLabel` — the panel is 296 px wide;
      - card colour comes from the same source as the timeline so the two read
        as one thing (R1 "just like the current timeline"):
        `sparseTint(block.tintId ?? laneId)` from
        `ui/src/timeline/sparseTints.ts`, `fill` as the card background and
        `stroke` as a 3 px left border;
      - empty / non-ready states mirror `SparseLane`'s `state` string exactly:
        `status === "loading"` → `Loading…`; `status === "error"` →
        `Unavailable — {error}`; ready with no blocks →
        `No data in this artifact`.
- [x] `ui/src/panel/index.ts` — export `LaneEventsPanel`.
- [x] `ui/src/timeline/TimelineGrid.tsx` — `LaneHeader` gains optional
      `onOpenEvents?: (laneId: string) => void` and `eventsOpen?: boolean`. When
      `onOpenEvents` is present it renders, as the **last flex child of
      `.tl-lane-head`** (after `.tl-lane-head__text`):

      ```tsx
      <button
        type="button"
        className="tl-lane-head__events"
        data-testid={`lane-events-${lane.id}`}
        aria-label={`Show ${lane.label} events`}
        aria-pressed={eventsOpen ?? false}
        onClick={() => onOpenEvents(lane.id)}
      >
        <i className="ph ph-columns-plus-right" />
      </button>
      ```

      `ph-columns-plus-right` is present in the vendored subset
      (`ui/src/styles/phosphor/style.css`) — do not add an icon dependency.
- [x] `ui/src/timeline/TimelineGrid.tsx` — `TimelineGrid` takes
      `onOpenLaneEvents?: (laneId: string) => void` and `eventsLaneId?: string | null`,
      and passes `onOpenEvents` down **only for lanes in `SPARSE_LANE_IDS`**
      (imported from `./laneContent`). Waveform, the canvas data lanes and the
      Regression Overlay therefore get no button — they have no event list.
- [x] `ui/src/App.tsx` — `const [eventsLaneId, setEventsLaneId] = useState<string | null>(null)`;
      `toggleLaneEvents(laneId)`: if `panelMode === "lane" && eventsLaneId === laneId`
      → close (`setPanelMode(null); setEventsLaneId(null)`); otherwise
      `setSelection(null); setActiveHintRef(null); setHintSeed(null);
      setEventsLaneId(laneId); setPanelMode("lane")` — R2's "replacing any
      other previous lane panel". Add `setEventsLaneId(null)` to both
      `closePanel` and the `song`-change reset effect. Render the panel under
      `activeView === "timeline" && song && panelMode === "lane" && eventsLaneId`,
      feeding it `buildLaneBlocks(eventsLaneId, laneContentSources)` and the
      status of `artifacts[SPARSE_LANE_ARTIFACT[eventsLaneId]]`.
- [x] `ui/src/App.tsx` — `onSelectBlock` seeks through
      `seekTimeForCardClick(transport.isPlaying, block.start_s)` (item 1) and
      does nothing else (D2).
- [x] `ui/src/styles/daw.css`:
      - `.tl-lane-head__events` — mirror `.caret`: 18×18 grid, transparent
        background, `color: var(--color-neutral-700)`, `font-size: 11px`,
        `border: none`, `border-radius: 3px`, `flex: none`,
        **`align-self: flex-start`** so its box is identical whether the lane is
        expanded or collapsed (the invariant `caret-fixed-position.spec.ts`
        guards for the caret). Hover / focus-visible copy `.caret`'s.
      - `.lane-events` — `list-style: none`, `margin: 0 calc(-1 * var(--space-6))`
        (full-bleed past `.app-rightpanel`'s padding), `padding: 0`,
        `display: flex`, `flex-direction: column`, **`gap: 0`** (R1: "without
        intermediate spaces").
      - `.lane-events__card` — full width, `text-align: left`,
        `padding: var(--space-2) var(--space-4)`, `border: 0`,
        `border-left: 3px solid` (tint stroke, inline), `border-bottom: 1px solid
        var(--tl-border)`, `display: flex`, `flex-direction: column`,
        `gap: 1px`, `cursor: pointer`.
      - `.lane-events__label` — reuse `.tl-lane-head__name`'s font stack/size;
        `.lane-events__caption` — reuse `.tl-lane-head__sub`'s.
- [x] Unit tests:
      - `ui/src/timeline/LaneHeader.test.tsx` — the button renders when
        `onOpenEvents` is given and is absent when it is not; `aria-pressed`
        follows `eventsOpen`; clicking it calls `onOpenEvents(lane.id)` and
        **not** `onToggleExpand`.
      - `ui/src/panel/LaneEventsPanel.test.tsx` (new) — renders one card per
        block in source order; card labels/captions match the blocks; the three
        state strings render for loading / error / ready-empty; clicking a card
        calls `onSelectBlock` with that block.
      - `ui/src/App.test.tsx` — `PanelMode` union still typechecks; no new
        assertions required (App renders without a song in jsdom).

### Docs to update in this commit

- [x] `reference/ui-regression_guide.md` §2 — new surface row
      `lane-events-panel`: "`song-full` with the Human Hints lane's events panel
      open · click `lane-events-humanHints` · stacked cards, no inter-card gap".
- [x] `reference/ui-regression_guide.md` §5.5 — add `lane-events-<laneId>` (the
      opener, on every block lane's head), `lane-events-panel` (the `<ol>`), and
      `lane-event-<blockId>` (each card).
- [x] `reference/ui-regression_guide.md` §9 — ticked lines for the new spec and
      the baseline re-capture, with the one-line justification below.

### Visual QA — item 3

New spec: `tests/ui-visual/specs/lane-events.spec.ts`. Surface:
`/?song=RegFull - Fixture`, awaited via `gotoSong`.

1. Guide §3 runtime assertions — all clean.
2. **Opener present exactly where it belongs.** For each of the block lanes
   visible by default (`humanHints`, `dropProposals`, `allin1Transitions`,
   `sections`, `character`, `vocalTranscription`, `allin1Sections`, `chords`,
   `patterns`, `identifierHints`, `machineEvents`, `mlEvents`, `phrases`):
   `lane-events-<laneId>` count === **1**.
3. **Absent where there is no event list:** `lane-events-waveform`,
   `lane-events-fftBands`, `lane-events-rmsLoudness`,
   `lane-events-loudnessEnvelope`, `lane-events-drums`, `lane-events-energy`,
   `lane-events-validation` each count === **0**.
4. **Right-aligned in the head (R2).** For `humanHints`: the button's
   `boundingBox().x + width` is within **2.0 px** of
   `.tl-lane-head[data-lane="humanHints"]`'s `x + width - 11.2`
   (`--space-4`, the head's right padding).
5. **The button does not move the caret.** `lane-collapse-humanHints`'s
   bounding box `x` and `y` are unchanged after collapsing and re-expanding the
   lane, to within **1.0 px** — and `caret-fixed-position.spec.ts` still passes.
6. **Opening.** Click `lane-events-humanHints`. `lane-events-panel` count === 1,
   its `data-lane` === `humanHints`, and the button's `aria-pressed` === `"true"`.
7. **Contents.** The panel holds exactly **3** `.lane-events__card` elements,
   whose `data-block-id`s in DOM order are `["hint-001","hint-002","hint-003"]`
   and whose `.lane-events__label` texts are
   `["Drop - approach","drop build","drop tension"]`.
8. **No intermediate spaces (R1).** For each consecutive card pair, observed
   `next.y - (prev.y + prev.height)` ≤ **1.0 px**.
9. **Full-bleed.** Each card's `boundingBox().width` is within **1.0 px** of
   `.app-rightpanel`'s `boundingBox().width`.
10. **Non-modal (D3).** Click the timeline viewport centre, then a lane's
    collapse caret, then the footer's zoom-in button: `lane-events-panel` count
    is still **1** after each. (An inspector-mode panel would have dismissed on
    the first of those — that is the difference this check exists for.)
11. **Replacement (R2).** Click `lane-events-allin1Sections`.
    `lane-events-panel` count === **1** (never 2) and its `data-lane` ===
    `allin1Sections`; `lane-events-humanHints`'s `aria-pressed` === `"false"`.
12. **Toggle off.** Click `lane-events-allin1Sections` again →
    `lane-events-panel` count === **0**.
13. **Esc closes.** Re-open `lane-events-humanHints`, press `Escape` →
    count === 0.
14. **Baseline.** Re-open `lane-events-humanHints`, seek to start, then
    `await expect(page.locator(".app-rightpanel")).toHaveScreenshot("lane-events-panel.png")`.
15. **Re-capture every existing baseline.** The opener adds an 18 px glyph to
    thirteen lane heads, which is under `maxDiffPixelRatio: 0.01` on a
    full-grid capture — the old baselines may *pass* while being wrong, so
    re-capture them regardless of whether the run is green, and commit them
    with the justification "lane heads gain the `columns-plus-right` events
    opener (plan v1.5 item 3)":
    `song-full`, `song-full-waveform`, `song-no-audio`, `left-panel-open`,
    `lane-collapsed`, `lanes-hidden-all`, `timeline-scrolled-50`,
    `timeline-zoom-min` (both the `timeline-zoom` and `fit-to-width` snapshot
    dirs), `timeline-zoom-max`, `hint-drag-resized` — every baseline whose
    locator is `.app-timeline__grid`, which is all of them but
    `waveform-no-audio.png` (that one targets `.tl-lane-body[data-lane="waveform"]`,
    which has no lane head; it must **not** change — if it does, something else
    broke). Review each diff before committing: the only change in any of them
    must be the new icon in the lane heads.

---

## 4. Active-card highlight and follow during playback

**Requirement:** R1 (highlight). **Decisions:** D5.

### Deliverable

- [x] `ui/src/panel/laneEvents.ts` (new) — one pure selector:

      ```ts
      /**
       * Index of the card to highlight at `time`, or -1 when none covers it.
       * Half-open [start_s, end_s): a boundary instant belongs to the block
       * that is starting. Overlapping blocks resolve to the one with the
       * latest start_s (the innermost). A degenerate block (end_s <= start_s)
       * is never active (plan v1.5 D5).
       */
      export function activeBlockIndex(
        blocks: readonly SparseBlock[],
        time: number,
      ): number;
      ```
- [x] `ui/src/panel/laneEvents.test.ts` (new) — before the first block → `-1`;
      in the gap between two blocks → `-1`; exactly at `start_s` → that block;
      exactly at `end_s` → `-1` (or the next block if it starts there);
      overlapping blocks → the later start wins; degenerate block → never;
      empty list → `-1`.
- [x] `ui/src/panel/LaneEventsPanel.tsx` — new props `currentTime: number` and
      `playing: boolean`. The card at `activeBlockIndex(blocks, currentTime)`
      gets `data-active="true"` and `aria-current="true"`; every other card gets
      `data-active="false"` and no `aria-current`.
- [x] `ui/src/panel/LaneEventsPanel.tsx` — follow: a `useEffect` on the active
      index scrolls the active card into view with
      `scrollIntoView({ block: "nearest" })` **only when `playing` is true**.
      Paused, the list never moves on its own — which is what keeps every
      screenshot in this plan deterministic. Guard the call
      (`el?.scrollIntoView?.()`) so jsdom unit tests do not throw.
- [x] `ui/src/App.tsx` — pass `currentTime={transport.currentTime}` and
      `playing={transport.isPlaying}`.
- [x] `ui/src/styles/daw.css` — `.lane-events__card[data-active="true"]`:
      raise the tint (a second inline background at higher alpha, or a
      `filter: brightness(1.6)` on the card background), widen the left border
      to 3 px `var(--color-accent)`, and set the label ink to
      `var(--color-neutral-100)`. It must be unmistakable at a glance in a
      296 px column.
- [x] Unit tests in `ui/src/panel/LaneEventsPanel.test.tsx` — exactly one card
      carries `data-active="true"` for a time inside a block; zero cards carry
      it for a time in a gap.

### Docs to update in this commit

- [x] `reference/ui-regression_guide.md` §2 — new surface row
      `lane-events-active`.
- [x] `reference/ui-regression_guide.md` §9 — ticked line for the highlight
      spec and its baseline.

### Visual QA — item 4

Extend `tests/ui-visual/specs/lane-events.spec.ts` with a second `test(...)`.
Surface: `/?song=RegFull - Fixture`; open `lane-events-humanHints`.

1. Guide §3 runtime assertions — all clean.
2. **Nothing active at the start.** After "To start" (clock `0:00.0`), the
   panel holds **0** elements matching `[data-active="true"]` (the first hint
   starts at 40.0 s).
3. **Paused card click highlights it.** Click card `lane-event-hint-002`.
   Header clock reads exactly `0:52.0`; exactly **1** card has
   `data-active="true"` and its `data-block-id` === `hint-002`.
4. Click card `lane-event-hint-003`. Clock reads `1:04.0`; the single active
   card is `hint-003`.
5. **Baseline.** With `hint-003` active,
   `await expect(page.locator(".app-rightpanel")).toHaveScreenshot("lane-events-active.png")`.
6. **The highlight clears in a gap.** Click card `lane-event-hint-002` (clock
   `0:52.0`, active card `hint-002`), then press the "Previous beat" transport
   button once. The clock reads `0:51.8` (the fixture's beat grid has a beat at
   51.77 s, and the previous one at 51.29 s — either is inside the 48.0–52.0
   gap between `hint-001` and `hint-002`). `[data-active="true"]` count ===
   **0**. If the clock lands outside 48.0–52.0, report it as a spec defect
   rather than choosing another target.
7. **`lane-events-panel.png` from item 3 still passes** — the paused,
   at-start panel must be unchanged by this item (no card is active at 0:00.0).

> R1's "when the song plays" wording describes the same rule sampled at a
> different rate: the highlight follows `currentTime`, whatever moves it. The
> rule itself is `activeBlockIndex`, unit-tested above; the suite drives
> `currentTime` by seeking rather than by playing (see "Conventions for every
> item"). The `scrollIntoView` follow is playback-only by construction and is
> therefore not visually asserted — keep it guarded so a paused seek never
> scrolls the list, which is what keeps steps 3–5's screenshots stable.

---

## 5. Header readout — drop the bar.beat caption, reserve the space

**Requirement:** R9, R10.

No existing baseline covers the header — every one of them is scoped to
`.app-timeline__grid` — so this item changes no committed image and adds the
first header baseline.

### Deliverable

- [x] `ui/src/App.tsx` — delete the `app-header__barbeat-caption` span (R9). The
      wrapper `<div style={{ display: "flex", alignItems: "baseline", gap: … }}>`
      around it exists only to pair the value with that caption; collapse it so
      the bar.beat value is a direct child of `.app-header__center`.
- [x] `ui/src/styles/app.css` — delete the now-unused
      `.app-header__barbeat-caption` rule (constitution §10: delete, don't keep
      it working).
- [x] `ui/src/styles/app.css` — reserve the readouts' width (R10). Both already
      inherit `font-variant-numeric: tabular-nums` from `.app-header__center`;
      restate it on each rule so a later refactor of the parent cannot silently
      remove the guarantee, and give each a fixed box:
      - `.app-header__time` — `display: inline-block; min-width: 7ch; text-align: right;`
        (`formatClock` emits `m:ss.s`, seven characters once a song passes ten
        minutes);
      - `.app-header__total` — `display: inline-block; min-width: 7ch; text-align: left;`
      - `.app-header__barbeat` — `display: inline-block; min-width: 6ch; text-align: right;`
        (`bar.beat`, six characters at a four-digit bar). Right-aligned so the
        decimal point holds still as the bar number grows.
- [x] No JS-side formatting change. `formatClock` and `coords.timeToBarBeat`
      keep their current output; this item is layout only.

### Docs to update in this commit

- [x] `reference/ui-regression_guide.md` §2 — new surface row `header-readout`.
- [x] `reference/ui-regression_guide.md` §9 — ticked line for the spec + baseline.

### Visual QA — item 5

New spec: `tests/ui-visual/specs/header-readout.spec.ts`. Surface:
`/?song=RegFull - Fixture`.

1. Guide §3 runtime assertions — all clean.
2. **R9.** `.app-header__barbeat-caption` count === **0**, and `.app-header`'s
   `innerText` does not contain the string `bar.beat` (case-insensitive).
3. **R10 — nothing shifts as the values change.** Record
   `.app-header__center`, `.app-header__time` and `.app-header__barbeat`
   bounding boxes at `0:00.0` / bar `1.1` (press "To start" first). Then click
   the `hint-003` block on the `humanHints` lane — it starts at 64.0 s, far
   off-screen at the default zoom, so bring it into view with
   `hint-drag.spec.ts`'s `lanePoint` helper first (`page.mouse` never
   auto-scrolls). The clock then reads `1:04.0` and the bar number goes from one
   digit to two or three.
   Re-read all three boxes. Every `x`, `y` and `width` is identical to within
   **0.5 px**. *(Before this item the bar.beat box grows with the digit count
   and drags the centre group with it — that is the defect R10 names.)*
4. Reserved widths are real, not incidental: `.app-header__time` width ≥
   **48 px** and `.app-header__barbeat` width ≥ **40 px** at `0:00.0` / `1.1`,
   when the rendered strings are shorter than their reservations.
5. **Baseline.** With the playhead at `1:04.0`,
   `await expect(page.locator(".app-header")).toHaveScreenshot("header-readout.png")`.
6. Full suite green, **zero** `--update-snapshots` on the existing baselines —
   none of them include the header.

---

## 6. Follow-playhead toggle in the footer

**Requirement:** R6. **Decisions:** D6, D7.

### Deliverable

- [ ] `ui/src/timeline/follow.ts` — extend the module that already owns
      `followScrollLeft`:

      ```ts
      export const DEFAULT_FOLLOW_PLAYHEAD = true;          // D7
      export function loadFollowPlayhead(): boolean;         // localStorage
      export function saveFollowPlayhead(on: boolean): void; // best-effort
      /**
       * D6: did the user scroll, or did the follow effect? `lastProgrammatic`
       * is the offset the effect last wrote (null when it has written none).
       */
      export function isUserScroll(
        observed: number,
        lastProgrammatic: number | null,
        tolerancePx?: number,   // default 1
      ): boolean;
      ```

      Copy `panelState.ts`'s storage shape exactly: a `STORAGE_KEY` constant
      (`als.ui.followPlayhead.v1`), `try`/`catch` around both accessors, and
      the default returned on anything unreadable.
- [ ] `ui/src/timeline/follow.test.ts` — `isUserScroll`: `null` last-write →
      `true`; observed within tolerance → `false`; observed 400 px away →
      `true`; exactly at tolerance → `false`. Plus load/save round-trip and the
      blocked-storage fallback.
- [ ] `ui/src/App.tsx` — `const [followPlayhead, setFollowPlayhead] = useState(loadFollowPlayhead)`,
      persisted by an effect mirroring the `drawerOpen` one.
- [ ] `ui/src/App.tsx` — the follow effect runs only when
      `followPlayhead && transport.isPlaying`, and records what it writes:
      `autoScrollRef.current = next` immediately before `el.scrollLeft = next`.
- [ ] `ui/src/App.tsx` — the existing scroll listener (the rAF-coalesced one
      that tracks `scrollLeft` / `viewportWidth`) additionally calls
      `setFollowPlayhead(false)` when `transport.isPlaying && followPlayhead &&
      isUserScroll(el.scrollLeft, autoScrollRef.current)`. Keep it inside the
      existing handler — do not add a second `scroll` listener.
- [ ] `ui/src/App.tsx` — footer button, **immediately before** the existing
      `Lanes` button so it renders to its left:

      ```tsx
      <button
        type="button"
        className="zbtn zbtn--icon"
        data-testid="follow-toggle"
        aria-pressed={followPlayhead}
        aria-label="Follow playhead"
        title="Follow the playhead while playing"
        onClick={() => setFollowPlayhead((on) => !on)}
      >
        <i className="ph ph-arrows-in-line-horizontal" />
      </button>
      ```

      Icon only — R6 asks for an icon, and the `Lanes` button beside it carries
      the only text label in that corner.
- [ ] `ui/src/styles/daw.css` — `.zbtn--icon`: square padding, no text gap,
      and an unmistakable pressed state (`[aria-pressed="true"]` →
      `color: var(--color-accent-300)`, `background: var(--color-accent-900)`),
      because the button's meaning is entirely in its state.

### Docs to update in this commit

- [ ] `reference/ui-regression_guide.md` §2 — new surface row `footer-follow`.
- [ ] `reference/ui-regression_guide.md` §5.5 — add `follow-toggle`.
- [ ] `reference/ui-regression_guide.md` §9 — ticked line for the spec + baseline.

### Visual QA — item 6

New spec: `tests/ui-visual/specs/follow-playhead.spec.ts`. Surface:
`/?song=RegFull - Fixture`. Clear `localStorage` at the start of the test so
the persisted flag from a previous run cannot decide the outcome.

1. Guide §3 runtime assertions — all clean.
2. **Placement.** `follow-toggle` exists; its `boundingBox().x + width` is
   **less than** the `Lanes` button's `boundingBox().x` (it sits to the left).
3. **Default on.** `follow-toggle` `aria-pressed` === `"true"`.
4. **Paused, nothing follows.** Press "To start" (`scrollLeft` is now 0). Click
   the `hint-003` block on the `humanHints` lane: the playhead moves to 64.0 s
   and `scrollLeft` is **unchanged at 0**, because `followScrollLeft` returns
   the current offset whenever `playing` is false. This is the only scroll
   behaviour the suite can observe without playback.
5. **Toggling.** Click `follow-toggle` → `aria-pressed` === `"false"`; click
   again → `"true"`. The button's pressed styling differs between the two
   states: its computed `color` is not the same string in both (read it with
   `evaluate(el => getComputedStyle(el).color)`), so the state is visible and
   not just announced.
6. **Persistence.** Click `follow-toggle` to `"false"`, reload,
   `waitReady`, and `aria-pressed` is still `"false"`. Then clear
   `localStorage` so the rest of the suite starts from the default.
7. **Baseline.** With follow off and the transport paused,
   `await expect(page.locator(".app-footer")).toHaveScreenshot("footer-follow.png")`.
8. Existing baselines: full suite green, zero `--update-snapshots` (the footer
   is outside every `.app-timeline__grid` capture).

> R6's behavioural half — that following moves the timeline while playing, and
> that a user scroll during playback turns the toggle off — is covered by
> `followScrollLeft` and `isUserScroll` in `follow.test.ts`, which are the two
> pure functions the whole feature reduces to. The suite cannot press Play (see
> "Conventions for every item"). Audition it against a real song before ticking
> the item, and say in the commit message that you did.

---

## 7. Flask badge on lanes fed by unpromoted experiments

**Requirement:** R7. **Decisions:** D8.

### Deliverable

- [ ] `ui/src/timeline/laneState.ts` — `LaneDef` gains
      `experiment?: string`: the `experiments/<name>/` folder the lane's
      proposal file comes from, absent on production lanes. Set it on exactly
      five lanes (D8):

      | lane id | `experiment` |
      | --- | --- |
      | `dropProposals` | `drop_detection` |
      | `allin1Transitions` | `allin1` |
      | `allin1Sections` | `allin1` |
      | `character` | `clap` |
      | `vocalTranscription` | `vocalparse + acestep_transcriber` |

      The value is rendered into the tooltip as
      `Experiment · experiments/<value> · not promoted to the pipeline`, so it
      is a human-readable source, not a path to resolve. **`vocalTranscription`
      genuinely has two producers** — `experiments/vocalparse/export.py` and
      `experiments/acestep_transcriber/export.py` both write
      `reference/proposals/vocal_transcription.json`, and its adapter emits one
      block per line per source (whisper baseline, ACE-Step, VocalParse). Name
      both rather than picking one; a block's own label and caption already say
      which model produced that particular line.

      Leave a comment naming constitution §3.2: this field and these lanes come
      out of the registry together when an experiment is promoted or abandoned.
- [ ] `ui/src/timeline/TimelineGrid.tsx` — `LaneHeader` renders, as the **first
      child of `.tl-lane-head__name`**, before the label text:

      ```tsx
      {lane.experiment && (
        <i
          className="ph ph-flask tl-lane-head__flask"
          role="img"
          aria-label="Experimental lane"
          title={`Experiment · experiments/${lane.experiment} · not promoted to the pipeline`}
        />
      )}
      ```

      The label text moves into `<span className="tl-lane-head__name-text">` so
      the ellipsis still applies to the text and not to the icon.
- [ ] `ui/src/styles/daw.css` — `.tl-lane-head__name` becomes
      `display: flex; align-items: center; gap: 4px;` with its
      `white-space`/`overflow`/`text-overflow` rules moved to
      `.tl-lane-head__name-text` (plus `min-width: 0`).
      `.tl-lane-head__flask` — `flex: none; font-size: 10px;
      color: var(--color-neutral-600);`. It must read as a quiet badge, not a
      control: no hover state, not focusable.
- [ ] `ui/src/panel/LaneEventsPanel.tsx` — the same badge before the header
      kicker when the panel's lane carries `experiment`, so a lane's events read
      as experimental in the panel too. Pass `experiment?: string` as a prop
      from `App.tsx` (look it up in `LANE_DEFS`).
- [ ] **Out of scope for this item:** the lane-visibility list (`LaneList.tsx`)
      is not badged. R7 says "the title", and the list is a settings surface,
      not a reading surface. Do not extend it here.
- [ ] Unit tests in `ui/src/timeline/LaneHeader.test.tsx` — the flask renders
      for a lane with `experiment` set and is absent without it; the accessible
      name is `Experimental lane`; `.tl-lane-head__name`'s `textContent` is
      still exactly the label (the icon contributes no text).

### Docs to update in this commit

- [ ] `reference/ui-regression_guide.md` §5.5 — note that experiment lane heads
      carry `.tl-lane-head__flask`.
- [ ] `reference/ui-regression_guide.md` §9 — ticked line for the spec + the
      baseline re-capture.
- [ ] `reference/ui_development.md` — one line under the debugger's data-access
      rules: lanes reading from `reference/proposals/` are badged as
      experimental in the head.

### Visual QA — item 7

New spec: `tests/ui-visual/specs/experiment-badge.spec.ts`. Surface:
`/?song=RegFull - Fixture`.

1. Guide §3 runtime assertions — all clean.
2. **Badged, exactly these five.** For `dropProposals`, `allin1Transitions`,
   `allin1Sections`, `character`, `vocalTranscription`:
   `.tl-lane-head[data-lane="<id>"] .tl-lane-head__flask` count === **1**.
3. **Not badged.** For `waveform`, `humanHints`, `sections`, `chords`,
   `patterns`, `identifierHints`, `machineEvents`, `mlEvents`, `phrases`,
   `fftBands`, `rmsLoudness`, `loudnessEnvelope`, `drums`, `energy`,
   `validation`: the same selector count === **0**.
4. **Whole-document count is 5** (`.tl-lane-head__flask` overall), so a stray
   badge anywhere fails.
5. **Left of the title.** For `character`: the flask's `boundingBox().x + width`
   ≤ `.tl-lane-head[data-lane="character"] .tl-lane-head__name-text`'s
   `boundingBox().x`.
6. **The label still fits.** For every badged lane,
   `.tl-lane-head__name-text`'s `scrollWidth - clientWidth` ≤ **0** at the
   default 1280 px viewport, i.e. no label became ellipsised by the badge. If
   one does, narrow the gap or the icon rather than accepting the truncation —
   and report the observed values.
7. **The caret has not moved.** `caret-fixed-position.spec.ts` still passes.
8. **Panel header.** Open `lane-events-character`; the panel header holds
   exactly **1** `.tl-lane-head__flask` (or the panel's own class if you scope
   it separately — state which in the guide).
9. **Baselines.** Re-capture the same eleven `.app-timeline__grid` baselines
   listed in item 3, justification "experiment lanes gain the flask badge (plan
   v1.5 item 7)". `waveform-no-audio.png` must again be unchanged.

---

## 8. `captured_from` note on the human-hints schema

**Requirement:** R8 (enabling half). **Decisions:** D11.

One optional string on a hint, naming the experiment or lane the event was
captured from, so a person opening `human_hints.json` can tell where an entry
came from. Nothing reads it. This item adds the field and its display; item 9
adds the only thing that writes it — land this one first so item 9 does not
ship a write with nowhere to put the note.

### Deliverable

- [ ] **Re-confirm the analyzer tolerates the new key before writing it**:
      `grep -rn "human_hints" src/ --include=*.py` and check every reader goes
      through `.get(...)` on the hint dict with no strict schema validation. At
      the time of writing, `src/analyzer/stages/hint_alignment.py` and
      `src/analyzer/stages/validation/form_drops.py` do. If that has changed,
      extend the validator in this commit.
- [ ] `ui/src/data/types.ts` — on `HumanHint`:

      ```ts
      /**
       * Where this hint was captured from, e.g. "allin1 Sections ·
       * experiments/allin1". Informative only — nothing reads it. Absent on
       * hand-authored hints (plan v1.5 D11).
       */
      captured_from?: string;
      ```
- [ ] `ui/src/data/saveHumanHints.ts` — `HintDraft` gains the same optional
      field; `buildHumanHintsPayload` emits the key **only** when the draft
      carries a non-empty string, trimmed. An empty or whitespace-only value
      means "no note" and the key is omitted — there is nothing to validate and
      nothing to throw over.
- [ ] `ui/vite.config.ts` — `normalizeHumanHintPayload` passes `captured_from`
      through when it is a non-empty string, omitting the key otherwise. It
      currently rebuilds each hint from a fixed field list, so without this
      change the note would be dropped on save and never survive a round-trip.
- [ ] `ui/src/panel/hintDraft.ts` — `HintDraftFields` gains
      `capturedFrom?: string`; `hintToDraft` and `draftToHint` carry it through
      untouched. It is never editable in the form — it is a note about where the
      entry came from, not a field the human authors.
- [ ] `ui/src/panel/HintEditorPanel.tsx` — when the active draft carries it,
      render one read-only line above the inputs: `Captured from <value>`.
      Style it as a quiet caption (reuse `.app-rightpanel__kicker`'s treatment
      or the block inspector's caption ink); it is information, not a control.
- [ ] Unit tests:
      - `ui/src/data/saveHumanHints.test.ts` — a draft without the field emits
        no key; with a value it round-trips trimmed; with `""` or `"   "` the
        key is omitted.
      - `ui/src/panel/hintDraft.test.ts` — `hintToDraft` / `draftToHint`
        round-trip preserves it.
      - A `HintEditorPanel` render test: the line shows for a hint carrying the
        note and is absent for a hand-authored one.

### Docs to update in this commit

- [ ] `data_folder_reference.md` — the `reference/human/human_hints.json`
      section gains `captured_from`: optional string, written only by the
      debugger's "Create human hint" action, absent on hand-authored hints,
      informative only — no code reads it.
- [ ] `reference/ui-regression_guide.md` §3.1 — note that `RegFull`'s frozen
      `human_hints.json` stays hand-authored (no `captured_from`), so the
      field's absence is itself under test.
- [ ] No downstream handoff note: `human_hints.json` lives under `reference/`
      and is not one of the files projected to the cue-authoring model
      (`reference/analysis-input-guide.md`). Say so in the commit message.

### Visual QA — item 8

Mostly a unit-tested item; the UI surface is one read-only line.

1. Guide §3 runtime assertions on `/?song=RegFull - Fixture` — all clean.
2. Open the hint editor on `hint-001` (click its block on the `humanHints`
   lane). The editor contains **no** text matching `/^Captured from/` — the
   fixture's hints are hand-authored.
3. Save an untouched `hint-001` through the editor's Save button, then reload
   and re-open it: the three fixture hints still match the table in "Conventions
   for every item" exactly, and no `captured_from` key appears in
   `tests/ui-visual/fixtures/analysis/RegFull - Fixture/reference/human/human_hints.json`
   (assert on the file after the run — `hint-drag.spec.ts` already snapshots and
   restores this file; follow the same pattern).
4. Full suite green, zero `--update-snapshots`.

---

## 9. "Create human hint" button in the block inspector

**Requirement:** R8 (the button). **Decisions:** D9, D10, D11, D12, D13.

Clicking any lane block already opens the right-panel block inspector
(`App.handleSelectMarker` → `panelMode: "inspector"`; a Human Hints block goes
to the hint editor instead). This item adds one action to that panel: turn the
event being inspected into a new, editable human hint. There is no canvas
hover affordance and no per-block overlay — see D9.

### Deliverable

- [ ] `ui/src/panel/BlockInspector.tsx` — a `rows-plus-bottom` action button,
      rendered directly under the `block-inspector__title` heading so it reads
      as an action on the thing named above it:

      ```tsx
      <button
        type="button"
        className="btn btn-ghost btn-sm block-inspector__promote"
        data-testid="promote-hint"
        onClick={() => onCreateHint(selection)}
      >
        <i className="ph ph-rows-plus-bottom" />
        Create human hint
      </button>
      ```

      New required prop `onCreateHint: (selection: BlockSelection) => void`.
      Visible in both transport states (D12). Match whatever `btn btn-ghost
      btn-sm` already looks like in `daw.css` — do not invent a new button
      style; add only `.block-inspector__promote { align-self: flex-start; }`
      plus the icon gap if the shared class does not already provide one.
- [ ] `ui/src/App.tsx` — `handleCreateHintFromSelection(selection)`:
      - `end` is `selection.end_s` when finite, otherwise `selection.start_s + 1.0`
        (a point marker gets the same 1.0 s span the existing "new hint"
        double-click creates — do not invent a different default);
      - `capturedFrom` is the note item 8 stores — one readable string built
        from the lane the event came from: `"<lane label>"` for a production
        lane, and `"<lane label> · experiments/<experiment>"` when the lane
        carries item 7's `experiment` field, e.g.
        `"allin1 Sections · experiments/allin1"` — and, for the two-producer
        vocal lane, `"Vocal Transcription · experiments/vocalparse +
        acestep_transcriber"`. The note is lane-level on purpose: a vocal
        block's own label already names the model behind that line, and one
        uniform rule is worth more here than per-lane cleverness. Resolve the label through
        `LANE_LABELS` and the experiment through `LANE_DEFS`, both of which
        already exist; when the lane id is in neither, use the raw lane id
        rather than inventing a name (constitution §2);
      - sets `setSelection(null); setActiveHintRef(null);` then
        `setHintSeed({ start, end, title: selection.label, summary: selection.summary ?? "", capturedFrom, nonce: Date.now() })`
        and `setPanelMode("hint")`, so the inspector is replaced by the hint
        editor holding the pre-filled draft;
      - does **not** seek, does **not** save, and does **not** touch the source
        artifact (D10, D13).
      Pass it to `<BlockInspector onCreateHint={…} />`.
- [ ] `ui/src/App.tsx` — the hint seed widens from `{ time, nonce }` to
      `{ start, end, title?, summary?, capturedFrom?, nonce }`. The existing
      double-click path `handleCreateHintAt(time)` becomes
      `{ start: time, end: time + 1.0, nonce }` — identical behaviour to today.
- [ ] `ui/src/panel/hintDraft.ts` — add
      `hintDraftFromSeed(seed, existing): HintDraftFields`, building the draft
      from the widened seed (id from `nextHintId`, `title` falling back to
      `Hint <n>` when the seed carries none, times through `formatSeconds`,
      `capturedFrom` carried straight through).
      **Delete `newHintDraft`** — `hintDraftFromSeed` supersedes it and its only
      caller is the seed effect. Remove its export from `ui/src/panel/index.ts`
      and fold its tests into the new function's (constitution §10: delete dead
      code rather than keeping it working).
- [ ] `ui/src/panel/HintEditorPanel.tsx` — the seed effect consumes the widened
      seed through `hintDraftFromSeed`. Everything else about that effect (the
      nonce guard, append-don't-reseed, focusing `#hint-title`,
      `onScrollToTime`) is unchanged.
- [ ] **Not in scope:** the lane events panel's cards (item 3) do not get this
      button. A card click seeks and nothing else (D2); promoting goes through
      the inspector, which is the surface that shows the event's fields. Say so
      in the commit message so its absence reads as a decision.
- [ ] Unit tests:
      - `ui/src/panel/hintDraft.test.ts` — `hintDraftFromSeed` maps every seed
        field; a seed with no title gets the `Hint <n>` fallback; the id
        continues the existing sequence; `capturedFrom` survives.
      - `ui/src/panel/BlockInspector.test.tsx` (new) — the button renders with
        an accessible name containing "Create human hint" and calls
        `onCreateHint` with the exact `selection` object it was given.
      - An `App`-level test is not required: the wiring is covered end-to-end by
        the Visual QA below.

### Docs to update in this commit

- [ ] `reference/ui_development.md` — the human-hint write path now has a second
      entry point (the block inspector's "Create human hint"), still landing in
      the same editor and the same single writable file.
- [ ] `reference/ui-regression_guide.md` §2 — new surface row
      `inspector-promote`: "`song-full` with an `allin1Sections` block selected ·
      click the block, then `promote-hint` · hint editor pre-filled".
- [ ] `reference/ui-regression_guide.md` §5.5 — add `promote-hint` (the
      inspector's action button).
- [ ] `reference/ui-regression_guide.md` §9 — ticked lines for the spec and the
      baseline, and repeat §9's existing warning that any spec touching the hint
      file must snapshot and restore it.

### Visual QA — item 9

New spec: `tests/ui-visual/specs/promote-hint.spec.ts`. It writes to
`RegFull`'s `human_hints.json`, so **snapshot the file in `beforeAll` and
restore it in `afterAll` and before each test**, exactly as `hint-drag.spec.ts`
does. Surface: `/?song=RegFull - Fixture`. The `allin1Sections` lane is the
source: expand it first (it is collapsed by default) and scroll a block into
view — `page.mouse` never auto-scrolls.

1. Guide §3 runtime assertions — all clean.
2. **Nothing before a selection.** `promote-hint` count === **0** on load.
3. **The inspector offers it.** Click the first `allin1Sections` block. The
   block inspector is open, and `promote-hint` count === **1** with an
   accessible name containing `Create human hint`.
4. **Human Hints does not route here.** Click a `humanHints` block: the hint
   editor opens (`hint-editor` present) and `promote-hint` count === **0** —
   the hand-authored lane cannot be its own source (D9).
5. **Present for every inspected event (D12).** Re-select the `allin1Sections`
   block; then expand the `machineEvents` lane (collapsed by default — a click
   on a collapsed lane selects nothing) and click one of its blocks; then click
   the second `.tl-seg-block` in the Segments header. `promote-hint` count ===
   **1** on each. The button is unconditional in the inspector — there is no
   transport-state guard to assert.
6. **It opens a pre-filled, unsaved draft.** Click `promote-hint`. Then:
   - `hint-editor` is present (the inspector has been replaced);
   - the title input's value === the block's label as shown in the inspector's
     `block-inspector__title`;
   - the start/end inputs equal the block's `start_s`/`end_s` from
     `reference/proposals/allin1.json` for that block, to within **0.01 s**;
   - the line `Captured from allin1 Sections · experiments/allin1` is present
     (item 8's read-only note);
   - the header clock is **unchanged** from before the click — promoting never
     seeks.
7. **Nothing written yet (D10).** Re-read
   `fixtures/analysis/RegFull - Fixture/reference/human/human_hints.json` from
   disk: still exactly the three hints from the table in "Conventions for every
   item", no fourth entry.
8. **The source artifact is untouched (D13).** Re-read
   `fixtures/analysis/RegFull - Fixture/reference/proposals/allin1.json`: byte-
   identical to the committed fixture.
9. **Saving writes it, with the note.** Press the editor's Save. Re-read the
   hints file: **4** hints; the new one carries the block's title and times, and
   `captured_from` === `"allin1 Sections · experiments/allin1"`. The original
   three are unchanged and carry **no** `captured_from` key — a hand-marked
   hint is indistinguishable from before (D11).
10. **It appears on the Human Hints lane.** Without reloading, open
    `lane-events-humanHints` (item 3): `.lane-events__card` count === **4**, and
    the fourth card's label is the promoted block's label.
11. **Baseline.** Restore the fixture file, reload, click the first
    `allin1Sections` block, and
    `await expect(page.locator(".app-rightpanel")).toHaveScreenshot("inspector-promote.png")`.
12. **Existing baselines unchanged.** This item adds nothing to
    `.app-timeline__grid`: full suite green, zero `--update-snapshots`.

---

## When something fails after an item is committed

A failure caught while working an item is fixed *before* that item's commit and
is not logged anywhere. A failure found against **already-committed** work is
routed by two questions — which component, and does fixing it need a decision:

- **A UI defect needing no design decision** → an entry in the frontend issue
  log with finding, severity, location, root cause and fix applied. This repo
  has no `docs/web-ui/ui-issues.md`; create `docs/ui-issues.md` for the first
  one, and delete it again when it empties (constitution §4.2 — the tracker
  holds open issues only). Put failing screenshots / console logs under
  `tests/ui-visual/` and link them from the entry.
- **An analysis/backend defect** → [`issues.md`](issues.md), the `ISS-NNN`
  queue, same rules.
- **Needs a design decision, or must be sequenced with other work** → a new
  numbered item appended to this plan, written to the same shape as the others
  (deliverable, docs, Visual QA block), and a row in the Status table. There is
  no separate refinement doc to park it in — this plan is the release's only
  worklist.
- **Found mid-run against an earlier item** → log it and keep going. Halt only
  if it blocks the item currently being worked. Never fix across item
  boundaries: the history stays one commit per item.

## Done means

All nine items ticked, the full unit suite and `npm run build` green in the
`ui` container, the Playwright suite green in the pinned image with the
re-captured baselines committed, and
[`reference/ui-regression_guide.md`](reference/ui-regression_guide.md) carrying
the new surfaces, selectors and checklist lines. At that point this plan is
deleted in the release commit (constitution §4 — a document goes when it stops
being true), and [`README.md`](README.md)'s "Open work" table returns to "No
release worklist is open."
