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
// v3.4 item 5: for the Moises Lyrics events panel only, each **word-token**
// card also carries a ✔ button (a sibling of the seek button, not nested in
// it — `stopPropagation()` so it never seeks). Clicking it toggles the token's
// human-validated state, which persists per-click via
// `PUT /api/lyric-validations/<song>` (D5.1 — no Save button, unlike the other
// reference/human/ writers). `<SOL>`/`<EOL>` markers get no button.

import { useCallback, useEffect, useRef, useState } from "react";

import type { ArtifactStatus } from "../data";
import { reviewKey } from "../data/blockReviewMatch";
import type {
  BlockReview,
  BlockReviewMatched,
  BlockReviewReason,
  BlockReviewVerdict,
} from "../data/types";
import type { LaneMarker } from "../timeline/laneRenderers";
import type { SparseBlock } from "../timeline/laneContent";
import { markerFor } from "../timeline/SparseLane";
import { sparseTint } from "../timeline/sparseTints";

import { activeBlockIndex, isInPlayheadWindow } from "./laneEvents";
import { RightPanel } from "./RightPanel";

export interface LyricValidationPanelProps {
  /** Moises word-token ids the operator has hand-verified */
  validatedIds: ReadonlySet<number>;
  /** persist a toggle immediately (per-click, no Save — D5.1) */
  onToggle: (tokenId: number, nextValidated: boolean) => void;
}

// v3.7 item 1 — the operator's three-state verdict (correct/wrong/misplaced)
// on a claim-bearing lane's emitted block, joined by (lane_id, start).
export interface BlockReviewPanelProps {
  /** every current review for the open lane, indexed by `reviewKey(lane_id, start)` */
  reviewsByKey: ReadonlyMap<string, BlockReviewMatched>;
  /** persist a verdict immediately (per-click, no Save — mirrors lyricValidation) */
  onSave: (review: BlockReview) => void;
}

const BLOCK_REVIEW_VERDICTS: readonly BlockReviewVerdict[] = [
  "correct",
  "wrong",
  "misplaced",
];
const BLOCK_REVIEW_REASONS: readonly BlockReviewReason[] = [
  "boundary",
  "label",
  "value",
];

/**
 * Three-state verdict control, one per block. Picking `correct` saves immediately (`reason: null`). Picking
 * `wrong` / `misplaced` reveals the fixed reason vocabulary — the reason pick
 * IS the save trigger, since `reason` is required non-null on those verdicts
 * (never a silently-defaulted reason). A stale review (no current block
 * within tolerance of its `start` — `../data/blockReviewMatch.ts`) renders a
 * visibly distinct "stale" badge rather than the normal verdict state.
 */
export function VerdictControl({
  laneId,
  start,
  review,
  onSave,
}: {
  laneId: string;
  start: number;
  review: BlockReviewMatched | undefined;
  onSave: (review: BlockReview) => void;
}): React.JSX.Element {
  const [pendingVerdict, setPendingVerdict] = useState<BlockReviewVerdict | null>(null);
  const [noteDraft, setNoteDraft] = useState(review?.note ?? "");

  useEffect(() => {
    setNoteDraft(review?.note ?? "");
  }, [review?.note]);

  const save = useCallback(
    (verdict: BlockReviewVerdict, reason: BlockReviewReason | null, note: string) => {
      onSave({
        lane_id: laneId,
        start: Number(start.toFixed(3)),
        verdict,
        reason: verdict === "correct" ? null : reason,
        note,
        reviewed_at: new Date().toISOString(),
      });
    },
    [laneId, start, onSave],
  );

  const pickVerdict = useCallback(
    (verdict: BlockReviewVerdict) => {
      if (verdict === "correct") {
        setPendingVerdict(null);
        save("correct", null, review?.note ?? "");
        return;
      }
      setPendingVerdict(verdict);
    },
    [save, review?.note],
  );

  const pickReason = useCallback(
    (reason: BlockReviewReason) => {
      if (!pendingVerdict) return;
      save(pendingVerdict, reason, review?.note ?? "");
      setPendingVerdict(null);
    },
    [pendingVerdict, save, review?.note],
  );

  const verdict = review?.verdict ?? null;
  const stale = review?.stale ?? false;
  const showReasonPicker = pendingVerdict != null;

  return (
    <div
      className="block-verdict"
      data-testid="block-verdict"
      data-lane={laneId}
      data-start={start.toFixed(3)}
      data-verdict={verdict ?? "unreviewed"}
      data-stale={stale}
    >
      {stale && (
        <span
          className="block-verdict__stale"
          data-testid="block-verdict-stale"
          title="No current block matches this review's start — stale, excluded from scoring"
        >
          stale
        </span>
      )}
      <div className="block-verdict__buttons" role="group" aria-label="Block verdict">
        {BLOCK_REVIEW_VERDICTS.map((v) => (
          <button
            key={v}
            type="button"
            className="block-verdict__btn"
            data-testid={`block-verdict-${v}`}
            aria-pressed={verdict === v}
            aria-label={v}
            onClick={(e) => {
              e.stopPropagation();
              pickVerdict(v);
            }}
          >
            {v}
          </button>
        ))}
      </div>
      {showReasonPicker && (
        <div className="block-verdict__reasons" role="group" aria-label="Reason">
          {BLOCK_REVIEW_REASONS.map((r) => (
            <button
              key={r}
              type="button"
              className="block-verdict__reason-btn"
              data-testid={`block-verdict-reason-${r}`}
              onClick={(e) => {
                e.stopPropagation();
                pickReason(r);
              }}
            >
              {r}
            </button>
          ))}
        </div>
      )}
      {verdict && verdict !== "correct" && review?.reason && !showReasonPicker && (
        <span className="block-verdict__reason-label" data-testid="block-verdict-reason">
          {review.reason}
        </span>
      )}
      {review && (
        <input
          type="text"
          className="block-verdict__note"
          data-testid="block-verdict-note"
          placeholder="note"
          value={noteDraft}
          onClick={(e) => e.stopPropagation()}
          onChange={(e) => setNoteDraft(e.target.value)}
          onBlur={() => {
            if (noteDraft !== (review.note ?? "")) {
              save(review.verdict, review.reason, noteDraft);
            }
          }}
        />
      )}
    </div>
  );
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
  /** v3.4 item 5 — supplied only for the Moises Lyrics panel */
  lyricValidation?: LyricValidationPanelProps | undefined;
  /** v3.7 item 1 — supplied only when `laneId` is in REVIEWABLE_LANE_IDS */
  blockReview?: BlockReviewPanelProps | undefined;
}

function displayBlockId(blockId: string): string {
  const split = blockId.lastIndexOf("-");
  if (split < 0) return blockId;
  const suffix = blockId.slice(split + 1).trim();
  return /^\d+$/.test(suffix) ? suffix : blockId;
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
  lyricValidation,
  blockReview,
}: LaneEventsPanelProps): React.JSX.Element {
  const activeIndex = activeBlockIndex(blocks, currentTime);
  const activeCardRef = useRef<HTMLButtonElement | null>(null);

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
  // v3.7 item 1 — reviewed/stale coverage counts for the panel header. A
  // stale review still counts toward "reviewed" here (it IS a verdict the
  // operator recorded, just against a block this run no longer emits) — it
  // is the scorer (experiments/truth_common/block_reviews.py) that excludes
  // it from the scored count, never this header.
  const reviewedCount = blockReview
    ? blocks.filter((b) =>
        blockReview.reviewsByKey.has(reviewKey(laneId, Number(b.start_s.toFixed(3)))),
      ).length
    : 0;
  const staleCount = blockReview
    ? [...blockReview.reviewsByKey.values()].filter((r) => r.stale).length
    : 0;

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
          {blockReview && (
            <span
              className="lane-events__rated"
              data-testid="block-review-count"
            >
              {reviewedCount} / {blocks.length} reviewed
              {staleCount > 0 ? ` (${staleCount} stale)` : ""}
            </span>
          )}
        </>
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
                    <span className="lane-events__captionrow">
                      <span className="lane-events__caption">{block.caption}</span>
                      <span className="lane-events__blockid">
                        {displayBlockId(block.id)}
                      </span>
                    </span>
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
                  {blockReview && (
                    <VerdictControl
                      laneId={laneId}
                      start={block.start_s}
                      review={blockReview.reviewsByKey.get(
                        reviewKey(laneId, Number(block.start_s.toFixed(3))),
                      )}
                      onSave={blockReview.onSave}
                    />
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
