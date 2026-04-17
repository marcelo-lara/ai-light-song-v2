import SelectionDetailCard from "./SelectionDetailCard.jsx";

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
        <SelectionDetailCard selection={selection} />
      </article>

      <ArtifactInspector artifactRecords={artifactRecords} selectedArtifactKey={selectedArtifactKey} onSelectArtifact={onSelectArtifact} />
    </section>
  );
}