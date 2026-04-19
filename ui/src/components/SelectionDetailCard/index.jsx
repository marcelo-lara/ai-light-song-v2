import { buildSelectionFields } from "./selectionFields.js";

const defaultSummary = "The shared cursor was moved to the start of this region. Playback state remains browser-local and read-only.";

export default function SelectionDetailCard({ selection, emptyMessage = "Click a region, overlay, or lane to inspect it and jump the shared cursor." }) {
  if (!selection) {
    return <div className="empty">{emptyMessage}</div>;
  }

  return (
    <div className="selection-card">
      <h3>{selection.label}</h3>
      <dl>
        {buildSelectionFields(selection).map((field) => <div key={field.label}><dt>{field.label}</dt><dd>{field.value}</dd></div>)}
      </dl>
      <div className="selection-summary">{selection.summary || defaultSummary}</div>
    </div>
  );
}