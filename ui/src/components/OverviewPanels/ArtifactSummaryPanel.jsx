import { coreArtifactKeys } from "../../lib/config.js";

import SummaryGrid from "./SummaryGrid.jsx";

export default function ArtifactSummaryPanel({ artifactRecords, timeline }) {
  const missingCore = artifactRecords.filter((status) => coreArtifactKeys.includes(status.key) && !status.ok);

  return (
    <article className="panel">
      <h2>Artifact Summary</h2>
      {missingCore.length > 0 ? (
        <div className="empty-state-card" aria-live="polite">
          <strong>Core artifacts are incomplete for this song.</strong>
          <span>The debugger stays read-only and loads what it can, but some lanes and overlays will remain partial.</span>
          <ul>{missingCore.map((status) => <li key={status.key}><strong>{status.label}</strong> <span>{status.error || "missing"}</span></li>)}</ul>
        </div>
      ) : null}
      <SummaryGrid timeline={timeline} />
    </article>
  );
}