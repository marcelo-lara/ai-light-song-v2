// LaneEventsPanel.tsx — right-panel mode "lane" (plan v1.5 item 3 / R1, R2).
//
// Every event of one sparse lane, stacked in the 296px right panel "just like
// the current timeline but stacked (without intermediate spaces)". Non-modal
// (D3): it rides through Play, timeline drags and scrolls, so it renders inside
// the shared `RightPanel` shell with `modal={false}` — no focus trap, no
// `aria-modal`, no outside-click dismissal; it closes via its ✕, `esc`, its
// lane's opener button, or a song change.
//
// A card click seeks (only when paused — item 1 / D1), scrolling the
// timeline to keep the playhead visible if the seek target falls outside the
// current scroll window, and does nothing else (D2): the panel stays on the
// same lane. A card double-click seeks the same way and additionally opens
// the item-6 block inspector for that event (the humanHints lane opens the
// hint editor instead, same routing as a canvas double-click). Card colour
// comes from the same `sparseTint` source the timeline blocks use so the two
// read as one thing.
//
// item 4 / R1 "highlight the active card": the card covering `currentTime`
// (per `activeBlockIndex`) gets `data-active="true"` / `aria-current`. While
// `playing`, the active card is scrolled into view on every index change;
// paused, the list never moves on its own, which keeps the screenshots stable.
//
// Separately, every card covering `currentTime` — not just the one
// `activeBlockIndex` resolves to — gets `data-in-window="true"`, drawn as a 2px
// accent-300 left-edge marker. Blocks in a lane can overlap, so more than one
// card can carry this at once; `data-active` still names a single "primary"
// card (raised tint, bright label) among however many are in-window.
//
// v3.4 item 4 (D4.1): when `blockEnergy` is supplied — only for the Human Hints
// events panel — each card also carries two 1-5 segmented-button selectors
// (`energy`, `tension`) pre-filled from `reference/human/block_energy.json`,
// with an explicit "unrated" state (no segment pressed — never a defaulted 1).
// A panel-level Save persists every rating via the client; closing / Cancel
// does not write. The card is restructured to a wrapper `<div>` with the seek
// button and the rating controls as siblings so no `<button>` is nested inside
// another.

// v3.4 item 5: for the Moises Lyrics events panel only, each **word-token**
// card also carries a ✔ button (a sibling of the seek button, not nested in
// it — `stopPropagation()` so it never seeks). Clicking it toggles the token's
// human-validated state, which persists per-click via
// `PUT /api/lyric-validations/<song>` (D5.1 — no Save button, unlike the other
// reference/human/ writers). `<SOL>`/`<EOL>` markers get no button.

import { useCallback, useEffect, useRef, useState } from "react";

import type { ArtifactStatus } from "../data";
import type { BlockEnergyDraft } from "../data/saveBlockEnergy";
import type { BlockEnergyFile } from "../data/types";
import type { LaneMarker } from "../timeline/laneRenderers";
import type { SparseBlock } from "../timeline/laneContent";
import { markerFor } from "../timeline/SparseLane";
import { sparseTint } from "../timeline/sparseTints";

import { activeBlockIndex, isInPlayheadWindow } from "./laneEvents";
import { RightPanel } from "./RightPanel";

type RatingAxis = "energy" | "tension";

export interface BlockEnergyPanelProps {
  /** the loaded (or empty) ratings file, joined to the cards by `hint_id` */
  file: BlockEnergyFile | null;
  /** persist every card's rating via `saveBlockEnergy` (explicit Save only) */
  onSave: (drafts: BlockEnergyDraft[]) => Promise<void>;
}

export interface LyricValidationPanelProps {
  /** Moises word-token ids the operator has hand-verified */
  validatedIds: ReadonlySet<number>;
  /** persist a toggle immediately (per-click, no Save — D5.1) */
  onToggle: (tokenId: number, nextValidated: boolean) => void;
}

interface LaneEventsPanelProps {
  laneId: string;
  laneLabel: string;
  /** plan v1.5 item 7 — the `experiments/<name>/` sandbox feeding this lane, if any */
  experiment?: string | undefined;
  blocks: readonly SparseBlock[];
  status: ArtifactStatus;
  error: string | null;
  currentTime: number;
  playing: boolean;
  onClose: () => void;
  onSelectBlock: (block: SparseBlock) => void;
  /** double-click a card -> open the item-6 block inspector for it */
  onSelectMarker: (marker: LaneMarker) => void;
  /** v3.4 item 4 — supplied only for the Human Hints panel */
  blockEnergy?: BlockEnergyPanelProps | undefined;
  /** v3.4 item 5 — supplied only for the Moises Lyrics panel */
  lyricValidation?: LyricValidationPanelProps | undefined;
}

type AxisPair = { energy: number | null; tension: number | null };
type RatingState = Record<string, AxisPair>;
type SaveState = "idle" | "saving" | "saved" | "error";

function seedRatings(file: BlockEnergyFile | null): RatingState {
  const out: RatingState = {};
  for (const r of file?.ratings ?? []) {
    out[r.hint_id] = { energy: r.energy ?? null, tension: r.tension ?? null };
  }
  return out;
}

function SegmentedRating({
  axis,
  hintId,
  value,
  onPick,
}: {
  axis: RatingAxis;
  hintId: string;
  value: number | null;
  onPick: (hintId: string, axis: RatingAxis, v: number) => void;
}): React.JSX.Element {
  return (
    <div
      className="seg-rating"
      data-axis={axis}
      data-value={value ?? "unrated"}
    >
      <span className="seg-rating__label">{axis}</span>
      <div
        className="seg-rating__buttons"
        role="group"
        aria-label={`${axis} rating`}
      >
        {[1, 2, 3, 4, 5].map((n) => (
          <button
            key={n}
            type="button"
            className="seg-rating__btn"
            data-testid={`block-energy-${hintId}-${axis}-${n}`}
            aria-pressed={value === n}
            aria-label={`${axis} ${n}`}
            onClick={() => onPick(hintId, axis, n)}
          >
            {n}
          </button>
        ))}
      </div>
    </div>
  );
}

export function LaneEventsPanel({
  laneId,
  laneLabel,
  experiment,
  blocks,
  status,
  error,
  currentTime,
  playing,
  onClose,
  onSelectBlock,
  onSelectMarker,
  blockEnergy,
  lyricValidation,
}: LaneEventsPanelProps): React.JSX.Element {
  const activeIndex = activeBlockIndex(blocks, currentTime);
  const activeCardRef = useRef<HTMLButtonElement | null>(null);

  const rating = laneId === "humanHints" ? blockEnergy : undefined;
  const lyric = laneId === "moisesLyrics" ? lyricValidation : undefined;

  // D5.1 — guard against a double-fire from one click only (a rapid genuine
  // second toggle is still honoured after the short window).
  const lastToggleRef = useRef<Map<number, number>>(new Map());
  const toggleValidated = useCallback(
    (tokenId: number, currentlyValidated: boolean) => {
      if (!lyric) return;
      const now = Date.now();
      if (now - (lastToggleRef.current.get(tokenId) ?? 0) < 300) return;
      lastToggleRef.current.set(tokenId, now);
      lyric.onToggle(tokenId, !currentlyValidated);
    },
    [lyric],
  );
  const [ratings, setRatings] = useState<RatingState>(() =>
    seedRatings(rating?.file ?? null),
  );
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [saveError, setSaveError] = useState<string | null>(null);

  // Reseed from the on-disk file whenever it changes (song switch, a Save that
  // returns the server-normalised file). An unsaved click never changes
  // `rating.file`, so this does not fight the local edits.
  useEffect(() => {
    if (!rating) return;
    setRatings(seedRatings(rating.file ?? null));
    setSaveState("idle");
    setSaveError(null);
  }, [rating?.file]); // eslint-disable-line react-hooks/exhaustive-deps

  const setAxis = useCallback(
    (hintId: string, axis: RatingAxis, v: number) => {
      setRatings((cur) => {
        const prev = cur[hintId] ?? { energy: null, tension: null };
        // Clicking the pressed segment again clears the axis back to "unrated".
        const next = prev[axis] === v ? null : v;
        return { ...cur, [hintId]: { ...prev, [axis]: next } };
      });
      setSaveState("idle");
    },
    [],
  );

  const ratedCount = blocks.filter((b) => {
    const r = ratings[b.id];
    return !!r && r.energy != null && r.tension != null;
  }).length;

  const doSave = useCallback(async () => {
    if (!rating) return;
    setSaveState("saving");
    setSaveError(null);
    try {
      const drafts: BlockEnergyDraft[] = blocks.map((b) => ({
        hint_id: b.id,
        energy: ratings[b.id]?.energy ?? null,
        tension: ratings[b.id]?.tension ?? null,
      }));
      await rating.onSave(drafts);
      setSaveState("saved");
    } catch (err) {
      setSaveState("error");
      setSaveError(
        err instanceof Error ? err.message : "Unable to save ratings.",
      );
    }
  }, [rating, blocks, ratings]);

  // Follow: keep the active card visible while playing. Guarded so jsdom
  // (no `scrollIntoView`) does not throw.
  useEffect(() => {
    if (!playing || activeIndex < 0) return;
    activeCardRef.current?.scrollIntoView?.({ block: "nearest" });
  }, [playing, activeIndex]);
  // Mirrors SparseLane's `state` string exactly.
  const state =
    status === "loading"
      ? "Loading…"
      : status === "error"
        ? `Unavailable${error ? ` — ${error}` : ""}`
        : status === "ready" && !blocks.length
          ? "No data in this artifact"
          : null;

  return (
    <RightPanel
      open
      modal={false}
      onClose={onClose}
      aria-label={`${laneLabel} events`}
      header={
        <>
          {experiment && (
            <i
              className="ph ph-flask tl-lane-head__flask"
              role="img"
              aria-label="Experimental lane"
              title={`Experiment · experiments/${experiment} · not promoted to the pipeline`}
            />
          )}
          <span className="app-rightpanel__kicker">{laneLabel}</span>
          <span className="lane-events__count">{blocks.length} events</span>
          {rating && (
            <span
              className="lane-events__rated"
              data-testid="block-energy-count"
            >
              {ratedCount} / {blocks.length} blocks rated
            </span>
          )}
        </>
      }
      footer={
        rating ? (
          <div className="lane-events__ratings-footer">
            {saveState === "error" && (
              <p className="lane-events__save-status is-error">{saveError}</p>
            )}
            {saveState === "saved" && (
              <p className="lane-events__save-status is-ok">
                Saved to block_energy.json.
              </p>
            )}
            <button
              type="button"
              className="btn btn-primary"
              data-testid="block-energy-save"
              disabled={saveState === "saving"}
              onClick={() => void doSave()}
            >
              {saveState === "saving" ? "Saving…" : "Save ratings"}
            </button>
          </div>
        ) : undefined
      }
    >
      {state ? (
        <div className="tl-canvas-lane__state">{state}</div>
      ) : (
        <ol className="lane-events" data-testid="lane-events-panel" data-lane={laneId}>
          {blocks.map((block, index) => {
            const tint = sparseTint(block.tintId ?? laneId);
            const active = index === activeIndex;
            const inWindow = isInPlayheadWindow(block, currentTime);
            const pair = ratings[block.id];
            return (
              <li key={block.id}>
                <div
                  className="lane-events__card"
                  data-block-id={block.id}
                  data-active={active}
                  data-in-window={inWindow}
                  aria-current={active ? "true" : undefined}
                  style={{ background: tint.fill, borderLeftColor: tint.stroke }}
                >
                  <button
                    ref={active ? activeCardRef : undefined}
                    type="button"
                    className="lane-events__cardmain"
                    data-testid={`lane-event-${block.id}`}
                    onClick={() => onSelectBlock(block)}
                    onDoubleClick={() => onSelectMarker(markerFor(block, laneId))}
                  >
                    <span className="lane-events__label">{block.label}</span>
                    <span className="lane-events__caption">{block.caption}</span>
                  </button>
                  {lyric &&
                    block.lyricValidatable &&
                    block.lyricTokenId != null && (
                      <button
                        type="button"
                        className="lane-events__validate"
                        data-testid={`lyric-validate-${block.id}`}
                        aria-pressed={lyric.validatedIds.has(block.lyricTokenId)}
                        aria-label={
                          lyric.validatedIds.has(block.lyricTokenId)
                            ? "Un-validate token timing"
                            : "Validate token timing"
                        }
                        title={
                          lyric.validatedIds.has(block.lyricTokenId)
                            ? "Human-validated — click to undo"
                            : "Mark this token's timing human-validated"
                        }
                        onClick={(e) => {
                          e.stopPropagation();
                          toggleValidated(
                            block.lyricTokenId!,
                            lyric.validatedIds.has(block.lyricTokenId!),
                          );
                        }}
                      >
                        ✔
                      </button>
                    )}
                  {rating && (
                    <div
                      className="lane-events__rating"
                      data-testid={`block-energy-${block.id}`}
                    >
                      <SegmentedRating
                        axis="energy"
                        hintId={block.id}
                        value={pair?.energy ?? null}
                        onPick={setAxis}
                      />
                      <SegmentedRating
                        axis="tension"
                        hintId={block.id}
                        value={pair?.tension ?? null}
                        onPick={setAxis}
                      />
                    </div>
                  )}
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </RightPanel>
  );
}
