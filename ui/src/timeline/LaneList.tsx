// LaneList.tsx — the "Analysis" lane list: show/hide and expand/collapse every
// lane. Rendered as a togglable panel over the timeline (opened from the footer
// / a drawer entry). Each lane's inline collapse caret in TimelineGrid toggles
// the same `expanded` state this panel shows.

import type { Lane } from "./laneState";

interface LaneListProps {
  lanes: readonly Lane[];
  onToggleVisible: (laneId: string) => void;
  onToggleExpanded: (laneId: string) => void;
  onShowAll: () => void;
  onReset: () => void;
  onClose: () => void;
}

export function LaneList({
  lanes,
  onToggleVisible,
  onToggleExpanded,
  onShowAll,
  onReset,
  onClose,
}: LaneListProps): React.JSX.Element {
  return (
    <div className="tl-lanelist" role="dialog" aria-label="Lane list">
      <div className="tl-lanelist__head">
        <span className="tl-lanelist__title">Analysis lanes</span>
        <button type="button" className="tp" aria-label="Close lane list" onClick={onClose}>
          <i className="ph ph-x" />
        </button>
      </div>

      <div className="tl-lanelist__actions">
        <button type="button" className="zbtn" onClick={onShowAll}>
          Show all
        </button>
        <button type="button" className="zbtn" onClick={onReset}>
          Reset
        </button>
      </div>

      <ul className="tl-lanelist__rows">
        {lanes.map((lane) => (
          <li key={lane.id} className={`tl-lanelist__row${lane.visible ? "" : " is-hidden"}`}>
            <label className="tl-lanelist__vis">
              <input
                type="checkbox"
                checked={lane.visible}
                onChange={() => onToggleVisible(lane.id)}
              />
              <span className="tl-lanelist__label">{lane.label}</span>
            </label>
            <button
              type="button"
              className="caret"
              disabled={!lane.visible}
              aria-label={lane.expanded ? `Collapse ${lane.label}` : `Expand ${lane.label}`}
              aria-expanded={lane.expanded}
              onClick={() => onToggleExpanded(lane.id)}
            >
              <i className={`ph ${lane.expanded ? "ph-caret-down" : "ph-caret-right"}`} />
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
