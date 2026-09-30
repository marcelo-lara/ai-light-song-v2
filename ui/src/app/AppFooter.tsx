// AppFooter.tsx — the zoom controls, follow-playhead toggle and lane-list
// toggle. Split out of App.tsx (v3.9 item 7) with no behaviour change.

import { FitToWidthButton } from "../timeline/FitToWidthButton";
import { PX_PER_BAR_MAX, ppbLabel } from "../timeline/zoom";

export function AppFooter({
  pxPerBar,
  minZoomPxPerBar,
  onZoomOut,
  onZoomIn,
  onZoomChange,
  onFitToWidth,
  followPlayhead,
  onToggleFollow,
  laneListOpen,
  onToggleLaneList,
}: {
  pxPerBar: number;
  minZoomPxPerBar: number;
  onZoomOut: () => void;
  onZoomIn: () => void;
  onZoomChange: (value: number) => void;
  onFitToWidth: () => void;
  followPlayhead: boolean;
  onToggleFollow: () => void;
  laneListOpen: boolean;
  onToggleLaneList: () => void;
}): React.JSX.Element {
  return (
    <footer className="app-footer">
      <div className="app-footer__zoom">
        <button
          type="button"
          className="zic"
          data-testid="zoom-out"
          aria-label="Zoom out"
          onClick={onZoomOut}
        >
          <i className="ph ph-magnifying-glass-minus" />
        </button>
        <input
          type="range"
          min={minZoomPxPerBar}
          max={PX_PER_BAR_MAX}
          value={pxPerBar}
          aria-label="Zoom (px per bar)"
          style={{ width: 148 }}
          onChange={(event) => onZoomChange(Number(event.target.value))}
        />
        <button
          type="button"
          className="zic"
          data-testid="zoom-in"
          aria-label="Zoom in"
          onClick={onZoomIn}
        >
          <i className="ph ph-magnifying-glass-plus" />
        </button>
        <span className="app-footer__ppb">{ppbLabel(pxPerBar)}</span>
        <FitToWidthButton onClick={onFitToWidth} />
      </div>
      <div className="app-footer__spacer" />
      <button
        type="button"
        className="zbtn zbtn--icon"
        data-testid="follow-toggle"
        aria-pressed={followPlayhead}
        aria-label="Follow playhead"
        title="Follow the playhead while playing"
        onClick={onToggleFollow}
      >
        <i className="ph ph-arrows-in-line-horizontal" />
      </button>
      <button
        type="button"
        className="zbtn"
        aria-pressed={laneListOpen}
        aria-label="Lanes"
        onClick={onToggleLaneList}
      >
        <i className="ph ph-sliders-horizontal" />
      </button>
    </footer>
  );
}
