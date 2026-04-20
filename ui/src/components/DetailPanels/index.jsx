import SelectionDetailCard from "../SelectionDetailCard/index.jsx";

import ArtifactInspector from "./ArtifactInspector.jsx";

export default function DetailPanels({ artifactRecords, selectedArtifactKey, onSelectArtifact, selection, onAddHumanHint }) {
  return (
    <section className="grid two-up">
      <article className="panel">
        <div className="compact-header sidebar-title-row">
          <h2>Selection Detail</h2>
          <button className="secondary-button" type="button" onClick={onAddHumanHint}>New Human Hint</button>
        </div>
        <SelectionDetailCard selection={selection} />
      </article>
      <ArtifactInspector artifactRecords={artifactRecords} selectedArtifactKey={selectedArtifactKey} onSelectArtifact={onSelectArtifact} />
    </section>
  );
}