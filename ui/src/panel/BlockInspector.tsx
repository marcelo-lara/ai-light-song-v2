// BlockInspector.tsx — right-panel mode: read-only detail for a clicked lane
// block (design §4a). `label` heading, a Nocturne <dl> of fields from
// `blockFields(laneId, selection)`, the `summary` line, and a "show raw"
// disclosure dumping the block's full source object. No inputs, no Save.

import { useState } from "react";

import type { BlockReview, BlockReviewMatched } from "../data/types";

import { blockFields, type BlockSelection } from "./blockFields";
import { VerdictControl } from "./LaneEventsPanel";

interface BlockInspectorProps {
  selection: BlockSelection;
  /**
   * plan v1.5 item 9 / R8: turn the inspected event into a new, editable human
   * hint. Seeds an unsaved draft in the hint editor — it never writes to disk
   * (D10) and never marks the source artifact (D13).
   */
  onCreateHint: (selection: BlockSelection) => void;
  /**
   * Same, for the section-shaped lanes (`SECTION_SOURCE_LANES`): seeds an
   * unsaved draft in the segment editor instead of the hint editor.
   */
  onCreateSection: (selection: BlockSelection) => void;
  /** v3.7 item 1 — supplied only when `selection.laneId` is in REVIEWABLE_LANE_IDS */
  blockReview?:
    | {
        review: BlockReviewMatched | undefined;
        onSave: (review: BlockReview) => void;
      }
    | undefined;
}

/** Lanes whose blocks are section spans — promoted to a human *section*. */
export const SECTION_SOURCE_LANES: ReadonlySet<string> = new Set([
  "allin1Sections",
  "segmentSeeds",
  "moisesSections",
]);

export function BlockInspector({
  selection,
  onCreateHint,
  onCreateSection,
  blockReview,
}: BlockInspectorProps): React.JSX.Element {
  const [showRaw, setShowRaw] = useState(false);
  const fields = blockFields(selection.laneId, selection);
  const isSection = SECTION_SOURCE_LANES.has(selection.laneId);

  return (
    <div className="block-inspector">
      <h3 className="block-inspector__title">{selection.label}</h3>

      {blockReview && (
        <VerdictControl
          laneId={selection.laneId}
          start={selection.start_s}
          review={blockReview.review}
          onSave={blockReview.onSave}
        />
      )}

      <button
        type="button"
        className="btn btn-ghost btn-sm block-inspector__promote"
        data-testid={isSection ? "promote-section" : "promote-hint"}
        onClick={() => (isSection ? onCreateSection(selection) : onCreateHint(selection))}
      >
        <i className="ph ph-rows-plus-bottom" />
        {isSection ? "Create human section" : "Create human hint"}
      </button>

      <dl className="block-inspector__dl">
        {fields.map((field) => (
          <div key={field.label} className="block-inspector__row">
            <dt>{field.label}</dt>
            <dd>{field.value}</dd>
          </div>
        ))}
      </dl>

      {selection.summary && (
        <p className="block-inspector__summary">{selection.summary}</p>
      )}

      <details
        className="block-inspector__raw"
        open={showRaw}
        onToggle={(e) => setShowRaw((e.currentTarget as HTMLDetailsElement).open)}
      >
        <summary>show raw</summary>
        <pre>{JSON.stringify(selection.raw, null, 2)}</pre>
      </details>
    </div>
  );
}
