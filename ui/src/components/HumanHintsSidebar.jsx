import { formatDuration } from "../lib/utils.js";

export default function HumanHintsSidebar({
  selectedSong,
  currentTime,
  isOpen,
  activeHint,
  saveState,
  handleAddHint,
  handleCancel,
  handleChangeActiveHint,
  handleDeleteActiveHint,
  handleSave,
  handleSetStartTime,
  handleSetEndTime,
}) {
  if (!isOpen || !selectedSong) {
    return null;
  }

  return (
    <aside className="editor-sidebar human-hints-sidebar">
      <div className="sidebar-title-row human-hints-sidebar-header">
        <div>
          <p className="eyebrow">Human Hint Editor</p>
          <h2>Reference Human Hints</h2>
          <p className="hint">Save updates only data/reference/{selectedSong}/human/human_hints.json.</p>
        </div>
        <button className="secondary-button human-hints-compact-button" type="button" onClick={handleAddHint}>New Hint</button>
      </div>

      <div className="human-hints-meta">
        <div>
          <span className="stat-label">Song</span>
          <strong>{selectedSong}</strong>
        </div>
        <div>
          <span className="stat-label">Cursor</span>
          <strong>{formatDuration(currentTime)}</strong>
        </div>
      </div>

      {activeHint ? (
        <div className="human-hints-editor-panel">
          <div className="human-hint-selected-summary">
            <strong>{activeHint.title || activeHint.id}</strong>
            <span>{formatDuration(activeHint.start_time)}-{formatDuration(activeHint.end_time)}</span>
          </div>

          <div className="field-grid">
            <label>
              <span className="stat-label">Id</span>
              <input type="text" value={activeHint.id} onInput={(event) => handleChangeActiveHint("id", event.currentTarget.value)} />
            </label>
            <label>
              <span className="stat-label">Title</span>
              <input type="text" value={activeHint.title} onInput={(event) => handleChangeActiveHint("title", event.currentTarget.value)} />
            </label>
            <div className="time-field-row">
              <button className="secondary-button human-hints-compact-button" type="button" onClick={handleSetStartTime}>Set</button>
              <label>
                <span className="stat-label">Start Time</span>
                <input type="number" step="0.1" value={activeHint.start_time} onInput={(event) => handleChangeActiveHint("start_time", event.currentTarget.value)} />
              </label>
            </div>
            <div className="time-field-row">
              <button className="secondary-button human-hints-compact-button" type="button" onClick={handleSetEndTime}>Set</button>
              <label>
                <span className="stat-label">End Time</span>
                <input type="number" step="0.1" value={activeHint.end_time} onInput={(event) => handleChangeActiveHint("end_time", event.currentTarget.value)} />
              </label>
            </div>
            <label>
              <span className="stat-label">Summary</span>
              <textarea rows="4" value={activeHint.summary} onInput={(event) => handleChangeActiveHint("summary", event.currentTarget.value)} />
            </label>
            <label>
              <span className="stat-label">Lighting Hint</span>
              <textarea rows="4" value={activeHint.lighting_hint} onInput={(event) => handleChangeActiveHint("lighting_hint", event.currentTarget.value)} />
            </label>
          </div>

          <div className="human-hints-editor-actions">
            <button className="secondary-button human-hints-compact-button" type="button" onClick={handleCancel}>Cancel</button>
            <button className="secondary-button danger-button human-hints-compact-button" type="button" onClick={handleDeleteActiveHint}>Delete</button>
            <button className="human-hints-compact-button" type="button" onClick={handleSave}>Save</button>
          </div>

          {saveState.status !== "idle" ? <p className={`save-status ${saveState.status}`}>{saveState.message}</p> : null}
        </div>
      ) : (
        <div className="human-hints-editor-panel">
          <p className="no-selection-hint">No hint selected. Click a hint on the timeline or add a new hint.</p>
          <div className="human-hints-editor-actions">
            <button className="secondary-button human-hints-compact-button" type="button" onClick={handleCancel}>Cancel</button>
            <button className="human-hints-compact-button" type="button" onClick={handleSave}>Save Changes</button>
          </div>
          {saveState.status !== "idle" ? <p className={`save-status ${saveState.status}`}>{saveState.message}</p> : null}
        </div>
      )}
    </aside>
  );
}