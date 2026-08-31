// The right panel — one shell (RightPanel) with modes: block inspector
// (read-only), hint editor, and — from item 7 — the review queue.

export { RightPanel, type PanelMode } from "./RightPanel";
export { BlockInspector } from "./BlockInspector";
export { HintEditorPanel } from "./HintEditorPanel";
export {
  blockFields,
  selectionFromSection,
  selectionFromMarker,
  formatRange,
  LANE_LABELS,
  type BlockSelection,
  type Field,
} from "./blockFields";
export {
  hintToDraft,
  draftToHint,
  newHintDraft,
  parseTimeInput,
  draftIdForReference,
  type HintDraftFields,
} from "./hintDraft";
