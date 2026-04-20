import { formatRange } from "../../lib/utils.js";

export function buildSelectionFields(selection) {
  return [
    { label: "Lane", value: selection.laneLabel },
    { label: "Window", value: formatRange(selection.start_s, selection.end_s) },
    { label: "Reference", value: selection.reference || "-" },
    selection.detail && selection.detail !== "-" ? { label: "Detail", value: selection.detail } : null,
    selection.caption ? { label: "Context", value: selection.caption } : null,
  ].filter(Boolean);
}