// BlockInspector.tsx — right-panel mode: read-only detail for a clicked lane
// block (design §4a). `label` heading, a Nocturne <dl> of fields from
// `blockFields(laneId, selection)`, the `summary` line, and a "show raw"
// disclosure dumping the block's full source object. No inputs, no Save.

import { useState } from "react";

import { blockFields, type BlockSelection } from "./blockFields";

interface BlockInspectorProps {
  selection: BlockSelection;
}

export function BlockInspector({ selection }: BlockInspectorProps): React.JSX.Element {
  const [showRaw, setShowRaw] = useState(false);
  const fields = blockFields(selection.laneId, selection);

  return (
    <div className="block-inspector">
      <h3 className="block-inspector__title">{selection.label}</h3>

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
