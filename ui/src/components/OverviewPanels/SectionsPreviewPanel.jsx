import { formatRange } from "../../lib/utils.js";

export default function SectionsPreviewPanel({ timeline }) {
  return (
    <article className="panel">
      <h2>Sections</h2>
      {!timeline?.sections?.length ? <div className="empty">No section artifact loaded.</div> : (
        <ul className="preview-list">
          {timeline.sections.slice(0, 8).map((section) => <li key={section.id}><strong>{section.label}</strong><span>{formatRange(section.start_s, section.end_s)}</span></li>)}
        </ul>
      )}
    </article>
  );
}