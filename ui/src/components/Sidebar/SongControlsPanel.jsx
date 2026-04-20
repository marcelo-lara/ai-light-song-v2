export default function SongControlsPanel({ availableSongs, selectedSong, isDiscovering, onSongChange, onLoadSong, onRefreshSongs }) {
  return (
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
  );
}