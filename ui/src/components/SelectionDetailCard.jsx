import { formatRange } from "../lib/utils.js";

const defaultSummary = "The shared cursor was moved to the start of this region. Playback state remains browser-local and read-only.";

export default function SelectionDetailCard({ selection, emptyMessage = "Click a region, overlay, or lane to inspect it and jump the shared cursor." }) {
  if (!selection) {
    return <div className="empty">{emptyMessage}</div>;
  }

  const fields = [
    { label: "Lane", value: selection.laneLabel },
    { label: "Window", value: formatRange(selection.start_s, selection.end_s) },
    { label: "Reference", value: selection.reference || "-" },
    selection.detail && selection.detail !== "-" ? { label: "Detail", value: selection.detail } : null,
    selection.caption ? { label: "Context", value: selection.caption } : null,
  ].filter(Boolean);

  return (
    <div className="selection-card">
      <h3>{selection.label}</h3>
      <dl>
        {fields.map((field) => (
          <div key={field.label}>
            <dt>{field.label}</dt>
            <dd>{field.value}</dd>
          </div>
        ))}
      </dl>
      <div className="selection-summary">{selection.summary || defaultSummary}</div>
    </div>
  );
}