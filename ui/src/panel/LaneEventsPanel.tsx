// LaneEventsPanel.tsx — right-panel mode "lane" (plan v1.5 item 3 / R1, R2).
//
// Every event of one sparse lane, stacked in the 296px right panel "just like
// the current timeline but stacked (without intermediate spaces)". Non-modal
// (D3): it rides through Play, timeline drags and scrolls, so it renders inside
// the shared `RightPanel` shell with `modal={false}` — no focus trap, no
// `aria-modal`, no outside-click dismissal; it closes via its ✕, `esc`, its
// lane's opener button, or a song change.
//
// A card click seeks (only when paused — item 1 / D1) and does nothing else
// (D2): the panel stays on the same lane. Card colour comes from the same
// `sparseTint` source the timeline blocks use so the two read as one thing.
//
// item 4 / R1 "highlight the active card": the card covering `currentTime`
// (per `activeBlockIndex`) gets `data-active="true"` / `aria-current`. While
// `playing`, the active card is scrolled into view on every index change;
// paused, the list never moves on its own, which keeps the screenshots stable.

import { useEffect, useRef } from "react";

import type { ArtifactStatus } from "../data";
import type { SparseBlock } from "../timeline/laneContent";
import { sparseTint } from "../timeline/sparseTints";

import { activeBlockIndex } from "./laneEvents";
import { RightPanel } from "./RightPanel";

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
}: LaneEventsPanelProps): React.JSX.Element {
  const activeIndex = activeBlockIndex(blocks, currentTime);
  const activeCardRef = useRef<HTMLButtonElement | null>(null);

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
            return (
              <li key={block.id}>
                <button
                  ref={active ? activeCardRef : undefined}
                  type="button"
                  className="lane-events__card"
                  data-testid={`lane-event-${block.id}`}
                  data-block-id={block.id}
                  data-active={active}
                  aria-current={active ? "true" : undefined}
                  style={{ background: tint.fill, borderLeftColor: tint.stroke }}
                  onClick={() => onSelectBlock(block)}
                >
                  <span className="lane-events__label">{block.label}</span>
                  <span className="lane-events__caption">{block.caption}</span>
                </button>
              </li>
            );
          })}
        </ol>
      )}
    </RightPanel>
  );
}
