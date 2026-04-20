import { DEFAULT_ZOOM, MAX_ZOOM, MIN_ZOOM } from "../../../lib/config.js";
import { clamp } from "../../../lib/utils.js";

export default function Toolbar({ barIndicator, beatIndicator, zoom, onZoomChange, visibleWindowLabel, selectionLabel }) {
  return (
    <>
      <div className="current-beat-bar"><strong className="current-beat-bar-value">{barIndicator}.</strong><strong className="current-beat-bar-value">{beatIndicator}</strong></div>
      <div className="timeline-toolbar">
        <label className="range-control" htmlFor="zoom-control">
          <span>Zoom</span>
          <input id="zoom-control" type="range" min={MIN_ZOOM} max={MAX_ZOOM} step="2" value={zoom} onInput={(event) => onZoomChange(clamp(Number(event.currentTarget.value) || DEFAULT_ZOOM, MIN_ZOOM, MAX_ZOOM))} />
          <strong>{zoom} px/s</strong>
        </label>
        <div className="timeline-toolbar-readouts"><span>{visibleWindowLabel}</span><span>{selectionLabel}</span></div>
      </div>
    </>
  );
}