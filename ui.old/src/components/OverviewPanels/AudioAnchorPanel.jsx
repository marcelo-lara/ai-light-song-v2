export default function AudioAnchorPanel({ waveformStatus, audioStatus, audioRef, onAudioTimeUpdate, onAudioPlay, onAudioPause, onAudioLoadedMetadata }) {
  return (
    <article className="panel">
      <div className="panel-header compact-header">
        <h2>Audio Anchor</h2>
        <span className="hint">{waveformStatus}</span>
      </div>
      <audio ref={audioRef} controls preload="metadata" onTimeUpdate={onAudioTimeUpdate} onPlay={onAudioPlay} onPause={onAudioPause} onLoadedMetadata={onAudioLoadedMetadata}></audio>
      <p className="hint">{audioStatus}</p>
    </article>
  );
}