import { laneDefinitions } from "../../lib/config.js";

export default function LaneTogglesPanel({ timelineLoaded, laneVisibility, onLaneToggle }) {
  return (
    <section className="panel controls">
      <div className="panel-header compact-header">
        <h2>Lane Toggles</h2>
        <span className="hint">Local only</span>
      </div>
      {timelineLoaded ? (
        <div className="lane-toggle-list">
          {laneDefinitions.map((lane) => (
            <label className="lane-toggle" htmlFor={`lane-toggle-${lane.id}`} key={lane.id}>
              <input id={`lane-toggle-${lane.id}`} type="checkbox" checked={Boolean(laneVisibility[lane.id])} onChange={(event) => onLaneToggle(lane.id, event.currentTarget.checked)} />
              <span><strong>{lane.label}</strong><span>{lane.description}</span></span>
            </label>
          ))}
        </div>
      ) : <div className="lane-toggle-list empty">Load a song to enable lane visibility controls.</div>}
    </section>
  );
}