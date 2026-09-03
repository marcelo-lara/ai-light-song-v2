// TimelineGrid.tsx — the timeline shell: a `212px max-content` CSS grid with
// two sticky header rows (Segments h26, Bars ruler h30), one row per visible
// lane (sticky label cell + body cell with the shared bar / 4-bar grid lines),
// and the accent playhead spanning every lane.
//
// Item 3 does NOT render lane bodies — the waveform is item 4 and the canvas
// data lanes are item 5. Each lane body here is the grid backdrop only. The
// Segments header and Bars ruler ARE item 3 and render from real artifacts.

import { useCallback } from "react";

import type { SectionRow } from "../data/types";

import type { Coords } from "./coords";
import type { Lane } from "./laneState";
import { SPARSE_LANE_IDS } from "./laneContent";
import { buildSegments, type SegmentBlock } from "./segments";
import { semanticZoom } from "./zoom";

export const LABEL_WIDTH = 212;

interface TimelineGridProps {
  coords: Coords;
  lanes: readonly Lane[];
  sections: readonly SectionRow[];
  currentTime: number;
  playing: boolean;
  onSeek: (time: number) => void;
  onToggleExpand: (laneId: string) => void;
  /** item 6 block inspector — stubbed no-op for now */
  onSelectSegment?: (block: SegmentBlock) => void;
  /** per-lane body content drawn over the grid backdrop (waveform / canvas) */
  renderLaneBody?: (lane: Lane) => React.ReactNode;
  /** plan v1.5 item 3 — open the stacked events panel for a sparse lane */
  onOpenLaneEvents?: (laneId: string) => void;
  /** lane id whose events panel is currently open, for the opener's pressed state */
  eventsLaneId?: string | null;
  scrollerRef: React.RefObject<HTMLDivElement>;
}

const SPARSE_LANE_ID_SET: ReadonlySet<string> = new Set(SPARSE_LANE_IDS);

export function TimelineGrid({
  coords,
  lanes,
  sections,
  currentTime,
  playing,
  onSeek,
  onToggleExpand,
  onSelectSegment,
  renderLaneBody,
  onOpenLaneEvents,
  eventsLaneId,
  scrollerRef,
}: TimelineGridProps): React.JSX.Element {
  const { timelineW, barLines } = coords;
  const zoom = semanticZoom(coords.pxPerBar);
  const segments = buildSegments(sections, coords);
  const playheadX = LABEL_WIDTH + coords.timeToX(currentTime);

  const seekFromEvent = useCallback(
    (event: React.MouseEvent<HTMLDivElement>) => {
      const rect = event.currentTarget.getBoundingClientRect();
      onSeek(coords.xToTime(event.clientX - rect.left));
    },
    [coords, onSeek],
  );

  const beatTicks = zoom.beatSubTicks
    ? coords.beats.filter((b) => b.type !== "downbeat" && b.beat !== 1)
    : [];

  return (
    <div className="app-timeline tl" data-testid="timeline-viewport" ref={scrollerRef}>
      <div className="app-timeline__grid" style={{ position: "relative" }}>
        {/* ---- Segments header (sticky, h26) ---- */}
        <div
          className="app-timeline__lane-head app-timeline__header-row tl-sticky-head"
          style={{ top: 0, zIndex: 11, height: 26 }}
        >
          <i className="ph ph-flag" style={{ fontSize: 11 }} />
          <span>Segments</span>
        </div>
        <div
          className="app-timeline__header-row tl-sticky-body"
          style={{ top: 0, zIndex: 8, height: 26, width: timelineW }}
        >
          {segments.map((seg) => (
            <button
              key={seg.key}
              type="button"
              className={`tl-seg-block${seg.accent ? " is-accent" : ""}`}
              style={{ left: seg.left, width: seg.width }}
              title={`${seg.name}${seg.barsText ? ` · ${seg.barsText}` : ""}`}
              onClick={() => onSelectSegment?.(seg)}
            >
              {seg.showLabel && (
                <>
                  <span className="tl-seg-name">{seg.name}</span>
                  {seg.barsText && <span className="tl-seg-len">{seg.barsText}</span>}
                </>
              )}
            </button>
          ))}
        </div>

        {/* ---- Bars ruler (sticky, h30) ---- */}
        <div
          className="app-timeline__lane-head tl-ruler-head tl-sticky-head"
          style={{ top: 26, zIndex: 11, height: 30 }}
        >
          <span>Bars</span>
        </div>
        <div
          className="tl-ruler-body tl-sticky-body"
          style={{ top: 26, zIndex: 8, height: 30, width: timelineW }}
          onClick={seekFromEvent}
          role="presentation"
        >
          {beatTicks.map((beat, i) => (
            <div
              key={`bt-${i}`}
              className="tl-beat-tick"
              style={{ left: coords.timeToX(beat.time) }}
            />
          ))}
          {barLines.map((line) => {
            const major = line.bar % 4 === 1;
            return (
              <div
                key={`bar-${line.bar}`}
                className={`tl-bar-tick${major ? " is-major" : ""}`}
                style={{ left: line.x, height: major ? 13 : 8 }}
              />
            );
          })}
          {barLines
            .filter((line) => (line.bar - 1) % zoom.barLabelEvery === 0)
            .map((line) => (
              <div
                key={`lbl-${line.bar}`}
                className="tl-bar-label"
                style={{ left: line.x + 4 }}
              >
                {line.bar}
              </div>
            ))}
        </div>

        {/* ---- Lanes ---- */}
        {lanes.map((lane) => (
          <LaneRow
            key={lane.id}
            lane={lane}
            barLines={barLines}
            timelineW={timelineW}
            onToggleExpand={onToggleExpand}
            onOpenEvents={
              onOpenLaneEvents && SPARSE_LANE_ID_SET.has(lane.id)
                ? onOpenLaneEvents
                : undefined
            }
            eventsOpen={eventsLaneId === lane.id}
            body={renderLaneBody?.(lane)}
          />
        ))}

        {/* ---- Playhead (spans every lane) ---- */}
        <div
          className={`tl-playhead${playing ? " is-playing" : ""}`}
          style={{ left: playheadX }}
        >
          <div className="tl-playhead__caret-anchor">
            <div className="tl-playhead__caret" />
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * The sticky lane label cell. Split out (and exported) so the item 5/6 layout
 * invariants are unit-testable in isolation:
 *  - item 5 / R1: the sub-caption node renders ONLY when the lane is expanded.
 *  - item 6 / R5: the collapse caret is the first flex child of a
 *    `align-items: flex-start` row, so its bounding box is the same x/y in both
 *    states — toggling `expanded` never moves it.
 */
export function LaneHeader({
  lane,
  onToggleExpand,
  onOpenEvents,
  eventsOpen,
}: {
  lane: Lane;
  onToggleExpand: (laneId: string) => void;
  /** plan v1.5 item 3 — present only for the sparse (block) lanes */
  onOpenEvents?: ((laneId: string) => void) | undefined;
  eventsOpen?: boolean | undefined;
}): React.JSX.Element {
  return (
    <div
      className="app-timeline__lane-head tl-lane-head"
      style={{ height: lane.renderHeight }}
      data-lane={lane.id}
      data-lane-collapsed={lane.expanded ? "false" : "true"}
    >
      <button
        type="button"
        className="caret"
        data-testid={`lane-collapse-${lane.id}`}
        aria-label={lane.expanded ? `Collapse ${lane.label}` : `Expand ${lane.label}`}
        aria-expanded={lane.expanded}
        onClick={() => onToggleExpand(lane.id)}
      >
        <i className={`ph ${lane.expanded ? "ph-caret-down" : "ph-caret-right"}`} />
      </button>
      <div className="tl-lane-head__text">
        <div className="tl-lane-head__name">{lane.label}</div>
        {lane.expanded && <div className="tl-lane-head__sub">{lane.sub}</div>}
      </div>
      {onOpenEvents && (
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
      )}
    </div>
  );
}

interface LaneRowProps {
  lane: Lane;
  barLines: Coords["barLines"];
  timelineW: number;
  onToggleExpand: (laneId: string) => void;
  onOpenEvents?: ((laneId: string) => void) | undefined;
  eventsOpen?: boolean | undefined;
  body?: React.ReactNode;
}

function LaneRow({
  lane,
  barLines,
  timelineW,
  onToggleExpand,
  onOpenEvents,
  eventsOpen,
  body,
}: LaneRowProps): React.JSX.Element {
  const collapsed = lane.expanded ? "false" : "true";
  return (
    <>
      <LaneHeader
        lane={lane}
        onToggleExpand={onToggleExpand}
        onOpenEvents={onOpenEvents}
        eventsOpen={eventsOpen}
      />
      <div
        className="app-timeline__lane-body tl-lane-body"
        style={{ height: lane.renderHeight, width: timelineW }}
        data-lane={lane.id}
        data-lane-collapsed={collapsed}
      >
        {barLines.map((line) => (
          <div
            key={`g-${line.bar}`}
            className={`tl-grid-line${line.bar % 4 === 1 ? " is-major" : ""}`}
            style={{ left: line.x }}
          />
        ))}
        {body}
      </div>
    </>
  );
}
