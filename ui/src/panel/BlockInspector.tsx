// BlockInspector.tsx — right-panel mode: read-only detail for a clicked lane
// block (design §4a). `label` heading, a Nocturne <dl> of fields from
// `blockFields(laneId, selection)`, the `summary` line, and a "show raw"
// disclosure dumping the block's full source object. No inputs, no Save.

import { useState } from "react";

import { blockFields, type BlockSelection } from "./blockFields";

interface BlockInspectorProps {
  selection: BlockSelection;
  /**
   * plan v1.5 item 9 / R8: turn the inspected event into a new, editable human
   * hint. Seeds an unsaved draft in the hint editor — it never writes to disk
   * (D10) and never marks the source artifact (D13).
   */
  onCreateHint: (selection: BlockSelection) => void;
}

export function BlockInspector({
  selection,
  onCreateHint,
}: BlockInspectorProps): React.JSX.Element {
  const [showRaw, setShowRaw] = useState(false);
  const fields = blockFields(selection.laneId, selection);

  return (
    <div className="block-inspector">
      <h3 className="block-inspector__title">{selection.label}</h3>

      <button
        type="button"
        className="btn btn-ghost btn-sm block-inspector__promote"
        data-testid="promote-hint"
        onClick={() => onCreateHint(selection)}
      >
        <i className="ph ph-rows-plus-bottom" />
        Create human hint
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
