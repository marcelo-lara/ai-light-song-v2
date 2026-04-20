import { formatPercent } from "../../lib/utils.js";

export default function ValidationSnapshotPanel({ report, timeline }) {
  if (!report || typeof report !== "object") {
    return <article className="panel"><h2>Validation Snapshot</h2><div className="empty">No validation report loaded.</div></article>;
  }

  const targets = Object.entries(report.validation || {});
  const beatsStatus = report.validation?.beats || {};
  const comparisonCounts = (timeline?.eventComparisons || []).reduce((accumulator, row) => ({ ...accumulator, [row.status]: (accumulator[row.status] || 0) + 1 }), {});

  return (
    <article className="panel">
      <h2>Validation Snapshot</h2>
      <div>
        <p><strong>Status:</strong> {report.status || "unknown"}</p>
        <p><strong>Command:</strong> {report.command || "-"}</p>
        <p><strong>Beat Match Ratio:</strong> {formatPercent(beatsStatus.match_ratio)}</p>
        <p><strong>Event Comparison:</strong> exact={comparisonCounts.exact || 0} shifted={comparisonCounts.shifted || 0} not_exported={comparisonCounts.not_exported || 0} output_only={comparisonCounts.output_only || 0}</p>
        <ul className="preview-list">{targets.length ? targets.map(([key, value]) => <li key={key}><strong>{key}</strong>: {value.status || "present"}</li>) : <li>No per-target validation details.</li>}</ul>
      </div>
    </article>
  );
}