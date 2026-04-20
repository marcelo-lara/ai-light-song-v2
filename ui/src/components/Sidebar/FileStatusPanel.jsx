export default function FileStatusPanel({ fileStatuses }) {
  return (
    <section className="panel controls">
      <h2>Files</h2>
      {fileStatuses.length ? (
        <div className="file-status">
          <ul className="file-status-list">
            {fileStatuses.map((status) => {
              const cssClass = status.ok ? "status-ok" : status.error ? "status-error" : "status-missing";
              const stateText = status.ok ? "loaded" : status.error ? status.error : "missing";
              return (
                <li key={status.key}>
                  <div className="status-row"><span className={`status-pill ${cssClass}`}>{status.label}</span><span>{stateText}</span></div>
                  <div className="status-path">{status.path}</div>
                </li>
              );
            })}
          </ul>
        </div>
      ) : <div className="file-status empty">Load a song directory to inspect artifact availability.</div>}
    </section>
  );
}