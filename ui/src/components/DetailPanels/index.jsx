import SelectionDetailCard from "../SelectionDetailCard/index.jsx";

import ArtifactInspector from "./ArtifactInspector.jsx";

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