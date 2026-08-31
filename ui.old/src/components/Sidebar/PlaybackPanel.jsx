export default function PlaybackPanel({ currentTimeLabel, transportBeatLabel, followPlayhead, onFollowPlayheadChange, onPlayPause, onJumpStart, isPlaying }) {
  return (
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
        <div><span className="stat-label">Now</span><strong>{currentTimeLabel}</strong></div>
        <div><span className="stat-label">Bar / Beat</span><strong>{transportBeatLabel}</strong></div>
      </div>
      <p className="hint">Audio playback time is the shared timeline source of truth.</p>
    </section>
  );
}