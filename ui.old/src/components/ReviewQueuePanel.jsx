import { useReviewQueueEditor } from "../app/useReviewQueueEditor.js";

// v1.1 Story 5.2 — renders artifacts/validation/review_queue.json as answerable
// questions. Whole-song answers save into reference/human/song_facts.json on an
// explicit Save only.
export default function ReviewQueuePanel({ selectedSong }) {
  const { questions, answerable, answers, existingFacts, loadError, saveState, setAnswer, handleSave } =
    useReviewQueueEditor(selectedSong);

  if (!selectedSong) {
    return null;
  }

  return (
    <section className="review-queue-panel">
      <div className="sidebar-title-row">
        <div>
          <p className="eyebrow">Machine Review Queue</p>
          <h3>Open questions</h3>
          <p className="hint">Answers save only to data/analysis/{selectedSong}/reference/human/song_facts.json.</p>
        </div>
      </div>

      {loadError ? <p className="no-selection-hint">{loadError}</p> : null}

      {questions.length === 0 && !loadError ? (
        <p className="no-selection-hint">No open questions for this run.</p>
      ) : null}

      <ol className="review-queue-list">
        {questions.map((question) => {
          const isAnswerable = answerable.includes(question);
          const factKey = question.field === "form_family_vs_genre" ? "genre" : question.field;
          const existing = existingFacts?.[factKey]?.value;
          return (
            <li key={question.field} className={`review-queue-item ${isAnswerable ? "" : "context-only"}`}>
              <div className="review-queue-field">{question.field}</div>
              <div className="review-queue-reason">{question.reason_low_confidence}</div>
              {question.evidence_timestamps?.length ? (
                <div className="review-queue-evidence">evidence @ {question.evidence_timestamps.join(", ")} s</div>
              ) : null}
              {isAnswerable ? (
                <select
                  value={answers[question.field] ?? ""}
                  onChange={(event) => setAnswer(question.field, event.currentTarget.value)}
                >
                  <option value="">— choose —</option>
                  {(question.candidates || []).map((candidate) => (
                    <option key={String(candidate.value)} value={String(candidate.value)}>
                      {String(candidate.value)} ({candidate.score})
                    </option>
                  ))}
                </select>
              ) : (
                <div className="review-queue-context-note">
                  Answer by editing human_hints.json (Story 8.8).
                </div>
              )}
              {existing !== undefined ? (
                <div className="review-queue-existing">saved: {String(existing)}</div>
              ) : null}
            </li>
          );
        })}
      </ol>

      {answerable.length ? (
        <div className="human-hints-editor-actions">
          <button className="human-hints-compact-button" type="button" onClick={handleSave}>
            Save answers
          </button>
        </div>
      ) : null}
      {saveState.status !== "idle" ? (
        <p className={`save-status ${saveState.status}`}>{saveState.message}</p>
      ) : null}
    </section>
  );
}
