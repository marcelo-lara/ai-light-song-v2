import { laneDefinitions } from "../lib/config.js";

export default function Sidebar({
  availableSongs,
  selectedSong,
  isDiscovering,
  onSongChange,
  onLoadSong,
  onRefreshSongs,
  timelineLoaded,
  laneVisibility,
  onLaneToggle,
  currentTimeLabel,
  transportBeatLabel,
  followPlayhead,
  onFollowPlayheadChange,
  onPlayPause,
  onJumpStart,
  isPlaying,
  fileStatuses,
}) {
  return (
    <aside className="sidebar">
      <div>
        <p className="eyebrow">AI Light Song v2</p>
        <h1>Artifact Debugger</h1>
        <p className="lede">Read-only inspection for generated inference surfaces, timing alignment, and regression drift under <code>data/artifacts</code>.</p>
      </div>

      <form className="panel controls" onSubmit={onLoadSong}>
        <label htmlFor="song-select">Song Directory</label>
        <select id="song-select" name="song" value={selectedSong} onChange={onSongChange} disabled={isDiscovering && availableSongs.length === 0}>
          {availableSongs.length === 0 ? (
            <option value="">{isDiscovering ? "Discovering artifact directories..." : "No artifact directories found"}</option>
          ) : (
            <>
              <option value="">Select a song directory</option>
              {availableSongs.map((song) => <option value={song} key={song}>{song}</option>)}
            </>
          )}
        </select>
        <div className="button-row">
          <button type="submit">Load Artifacts</button>
          <button type="button" className="secondary-button" onClick={onRefreshSongs}>Refresh List</button>
        </div>
        <p className="hint">The debugger discovers per-song directories from <code>data/artifacts</code>. It never writes to <code>data/artifacts</code> or <code>data/output</code>.</p>
      </form>

      <section className="panel controls">
        <h2>Playback</h2>
        <div className="transport-controls">
          <button type="button" onClick={onPlayPause}>{isPlaying ? "Pause" : "Play"}</button>
          <button type="button" className="secondary-button" onClick={onJumpStart}>Jump to Start</button>
        </div>
        <label className="checkbox-row" htmlFor="follow-playhead">
          <input id="follow-playhead" type="checkbox" checked={followPlayhead} onChange={onFollowPlayheadChange} />
          <span>Follow playhead</span>
        </label>
        <div className="transport-readout">
          <div>
            <span className="stat-label">Now</span>
            <strong>{currentTimeLabel}</strong>
          </div>
          <div>
            <span className="stat-label">Bar / Beat</span>
            <strong>{transportBeatLabel}</strong>
          </div>
        </div>
        <p className="hint">Audio playback time is the shared timeline source of truth.</p>
      </section>

      <section className="panel controls">
        <div className="panel-header compact-header">
          <h2>Lane Toggles</h2>
          <span className="hint">Local only</span>
        </div>
        {timelineLoaded ? (
          <div className="lane-toggle-list">
            {laneDefinitions.map((lane) => (
              <label className="lane-toggle" htmlFor={`lane-toggle-${lane.id}`}>
                <input
                  id={`lane-toggle-${lane.id}`}
                  type="checkbox"
                  checked={Boolean(laneVisibility[lane.id])}
                  onChange={(event) => onLaneToggle(lane.id, event.currentTarget.checked)}
                />
                <span>
                  <strong>{lane.label}</strong>
                  <span>{lane.description}</span>
                </span>
              </label>
            ))}
          </div>
        ) : (
          <div className="lane-toggle-list empty">Load a song to enable lane visibility controls.</div>
        )}
      </section>

      <section className="panel controls">
        <h2>Available Paths</h2>
        <ul className="path-list">
          <li><code>/data/artifacts/&lt;Song - Artist&gt;/</code></li>
          <li><code>/data/output/&lt;Song - Artist&gt;/</code></li>
          <li><code>/data/songs/&lt;Song - Artist&gt;.mp3</code></li>
        </ul>
      </section>

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
                    <div className="status-row">
                      <span className={`status-pill ${cssClass}`}>{status.label}</span>
                      <span>{stateText}</span>
                    </div>
                    <div className="status-path">{status.path}</div>
                  </li>
                );
              })}
            </ul>
          </div>
        ) : (
          <div className="file-status empty">Load a song directory to inspect artifact availability.</div>
        )}
      </section>
    </aside>
  );
}