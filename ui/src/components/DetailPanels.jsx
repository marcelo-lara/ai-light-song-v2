import { formatRange } from "../lib/utils.js";

function SelectionDetail({ selection }) {
  if (!selection) {
    return <div className="empty">Click a region, overlay, or lane to inspect it and jump the shared cursor.</div>;
  }
  return (
    <div className="selection-card">
      <h3>{selection.label}</h3>
      <dl>
        <div>
          <dt>Lane</dt>
          <dd>{selection.laneLabel}</dd>
        </div>
        <div>
          <dt>Window</dt>
          <dd>{formatRange(selection.start_s, selection.end_s)}</dd>
        </div>
        <div>
          <dt>Primary Ref</dt>
          <dd>{selection.reference || "-"}</dd>
        </div>
        <div>
          <dt>Detail</dt>
          <dd>{selection.detail || "-"}</dd>
        </div>
      </dl>
      <div className="selection-summary">{selection.summary || "The shared cursor was moved to the start of this region. Playback state remains browser-local and read-only."}</div>
    </div>
  );
}

function ArtifactInspector({ artifactRecords, selectedArtifactKey, onSelectArtifact }) {
  const selectedArtifact = artifactRecords.find((artifact) => artifact.key === selectedArtifactKey && artifact.ok);
  return (
    <article className="panel">
      <div className="panel-header">
        <h2>Artifact Inspector</h2>
        <select value={selectedArtifactKey} onChange={onSelectArtifact}>
          <option value="">Select a loaded file</option>
          {artifactRecords.filter((artifact) => artifact.ok).map((artifact) => (
            <option value={artifact.key} key={artifact.key}>{artifact.label}</option>
          ))}
        </select>
      </div>
      <pre className="json-viewer">{selectedArtifact ? JSON.stringify(selectedArtifact.data, null, 2) : "No artifact selected."}</pre>
    </article>
  );
}

export default function DetailPanels({ artifactRecords, selectedArtifactKey, onSelectArtifact, selection }) {
  return (
    <section className="grid two-up">
      <article className="panel">
        <h2>Selection Detail</h2>
        <SelectionDetail selection={selection} />
      </article>

      <ArtifactInspector artifactRecords={artifactRecords} selectedArtifactKey={selectedArtifactKey} onSelectArtifact={onSelectArtifact} />
    </section>
  );
}