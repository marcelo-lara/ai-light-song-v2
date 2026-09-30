// AppTimelineArea.tsx — the main content area: the artifact inspector, the
// song picker, a loading/fatal stub, or the timeline grid + lane list +
// degraded-lane banner. Split out of App.tsx (v3.9 item 7) with no behaviour
// change.

import { ArtifactInspector } from "../inspector";
import type { SongListState, SongLoadState } from "./loadStates";
import { SongPicker } from "./SongPicker";
import type { DrawerView } from "./useDrawer";
import type { Coords } from "../timeline/coords";
import { LaneList } from "../timeline/LaneList";
import type { Lane, UseLaneStateResult } from "../timeline/laneState";
import { TimelineGrid } from "../timeline/TimelineGrid";
import type { Transport } from "../timeline/useTransport";
import type { SectionRow } from "../data/types";
import type { SegmentBlock } from "../timeline/segments";

export function AppTimelineArea({
  activeView,
  song,
  songListState,
  songLoadState,
  coords,
  transport,
  sections,
  laneState,
  toggleExpandedGuarded,
  onSelectSegment,
  renderLaneBody,
  onOpenLaneEvents,
  eventsLaneId,
  scrollerRef,
  laneListOpen,
  onCloseLaneList,
  onPickSong,
  onPickAnotherSong,
}: {
  activeView: DrawerView;
  song: string | null;
  songListState: SongListState;
  songLoadState: SongLoadState;
  coords: Coords;
  transport: Transport;
  sections: readonly SectionRow[];
  laneState: UseLaneStateResult;
  toggleExpandedGuarded: (laneId: string) => void;
  onSelectSegment: (block: SegmentBlock) => void;
  renderLaneBody: (lane: Lane) => React.ReactNode;
  onOpenLaneEvents: (laneId: string) => void;
  eventsLaneId: string | null;
  scrollerRef: React.RefObject<HTMLDivElement>;
  laneListOpen: boolean;
  onCloseLaneList: () => void;
  onPickSong: (name: string) => void;
  onPickAnotherSong: () => void;
}): React.JSX.Element {
  return (
    <div
      className="app-timeline-wrap"
      style={{ position: "relative", flex: 1, minWidth: 0, display: "flex" }}
    >
      {activeView === "inspector" ? (
        <ArtifactInspector song={song} />
      ) : activeView === "song" ? (
        <SongPicker listState={songListState} current={song} onPick={onPickSong} />
      ) : song && songLoadState.kind === "loading" ? (
        <div className="app-timeline tl">
          <div className="app-timeline__stub" style={{ padding: "var(--space-8)" }}>
            Loading {song}…
          </div>
        </div>
      ) : song && songLoadState.kind === "fatal" ? (
        <div className="app-timeline tl">
          <div className="app-timeline__state" style={{ padding: "var(--space-8)" }}>
            <p className="card-kicker">Can’t open {song}</p>
            <p className="card-body">{songLoadState.message}</p>
            <button type="button" className="btn btn-ghost btn-sm" onClick={onPickAnotherSong}>
              Pick another song
            </button>
          </div>
        </div>
      ) : song ? (
        <>
          <TimelineGrid
            coords={coords}
            lanes={laneState.visibleLanes}
            sections={sections}
            currentTime={transport.currentTime}
            playing={transport.isPlaying}
            onSeek={transport.seekTo}
            onToggleExpand={toggleExpandedGuarded}
            onSelectSegment={onSelectSegment}
            renderLaneBody={renderLaneBody}
            onOpenLaneEvents={onOpenLaneEvents}
            eventsLaneId={eventsLaneId}
            scrollerRef={scrollerRef}
          />
          {laneListOpen && (
            <LaneList
              lanes={laneState.lanes}
              onToggleVisible={laneState.toggleVisible}
              onToggleExpanded={toggleExpandedGuarded}
              onShowAll={laneState.showAll}
              onHideAll={laneState.hideAll}
              onReset={laneState.resetToDefaults}
              onClose={onCloseLaneList}
            />
          )}
          {/* item 10 (refinement v2.2 §10): lane-status notices are
              low-urgency and belong out of the primary work area, so this
              renders below the timeline / lane stack, flush at the bottom. */}
          {songLoadState.kind === "degraded" && (
            <div className="app-timeline__banner app-timeline__banner--bottom" role="status">
              {songLoadState.missing.length} lane
              {songLoadState.missing.length === 1 ? "" : "s"} missing an artifact:{" "}
              {songLoadState.missing.join(", ")}. Those lanes show an empty state.
            </div>
          )}
        </>
      ) : (
        <div className="app-timeline tl">
          <div className="app-timeline__stub" style={{ padding: "var(--space-8)" }}>
            No song selected — open “Select Song”.
          </div>
        </div>
      )}
    </div>
  );
}
