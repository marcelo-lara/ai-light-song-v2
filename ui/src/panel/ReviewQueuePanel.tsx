// ReviewQueuePanel.tsx — right-panel third mode: the review-queue editor
// (item 7 / Story 8.10).
//
// Renders `artifacts/validation/review_queue.json` as ranked questions. The
// whole-song questions (`form_family`, `form_family_vs_genre`) are answerable
// via a `<select>` of the analyzer's candidates; on an explicit Save they are
// PUT to `/api/song-facts/<song>` and land in `reference/human/song_facts.json`
// stamped `provenance: "human-confirmed"`. Per-section / drop questions are
// shown read-only for context (answered by editing human hints).
//
// Empty state: a song with no `review_queue.json` (not analysed under v1.1)
// gets a message, not an error.

import { useCallback, useEffect, useMemo, useState } from "react";

import { loadReviewQueue, loadSongFacts } from "../data/loaders";
import {
  buildSongFactsPayload,
  saveSongFacts,
  type SongFactsDraft,
} from "../data/saveSongFacts";
import type { ReviewQueue, ReviewQuestion, SongFactsFile } from "../data/types";

import { RightPanel } from "./RightPanel";
import { partitionReviewQueue, questionOptions } from "./reviewQueue";

interface ReviewQueuePanelProps {
  song: string;
  onClose: () => void;
}

type QueueState =
  | { status: "loading" }
  | { status: "empty" }
  | { status: "error"; message: string }
  | { status: "ready"; queue: ReviewQueue };

type SaveState =
  | { status: "idle" }
  | { status: "saving" }
  | { status: "error"; message: string }
  | { status: "success" };

function factLabel(file: SongFactsFile | null, field: string): string | null {
  const fact = file?.facts?.[field];
  if (!fact || fact.value === null || fact.value === undefined) return null;
  const provenance = fact.provenance ? ` · ${fact.provenance}` : "";
  return `${String(fact.value)}${provenance}`;
}

export function ReviewQueuePanel({
  song,
  onClose,
}: ReviewQueuePanelProps): React.JSX.Element {
  const [queueState, setQueueState] = useState<QueueState>({ status: "loading" });
  const [factsFile, setFactsFile] = useState<SongFactsFile | null>(null);
  const [draft, setDraft] = useState<SongFactsDraft>({});
  const [save, setSave] = useState<SaveState>({ status: "idle" });

  useEffect(() => {
    let cancelled = false;
    setQueueState({ status: "loading" });
    setFactsFile(null);
    setDraft({});
    setSave({ status: "idle" });

    void Promise.all([loadReviewQueue(song), loadSongFacts(song)]).then(
      ([queueResult, factsResult]) => {
        if (cancelled) return;
        if (factsResult.ok) setFactsFile(factsResult.data);
        if (queueResult.ok) {
          setQueueState({ status: "ready", queue: queueResult.data });
        } else if (
          queueResult.error.kind === "http" &&
          queueResult.error.status === 404
        ) {
          setQueueState({ status: "empty" });
        } else {
          setQueueState({ status: "error", message: queueResult.error.message });
        }
      },
    );

    return () => {
      cancelled = true;
    };
  }, [song]);

  const partitioned = useMemo(
    () =>
      queueState.status === "ready"
        ? partitionReviewQueue(queueState.queue)
        : { wholeSong: [], context: [] },
    [queueState],
  );

  const setAnswer = useCallback((field: string, value: string) => {
    setDraft((current) => ({ ...current, [field]: value }));
    setSave({ status: "idle" });
  }, []);

  const dirty = Object.values(draft).some((value) => value.trim() !== "");

  const doSave = useCallback(async () => {
    setSave({ status: "saving" });
    try {
      const payload = buildSongFactsPayload(
        factsFile?.song_name || song,
        draft,
      );
      const written = await saveSongFacts(song, payload);
      setFactsFile(written);
      setDraft({});
      setSave({ status: "success" });
    } catch (error) {
      setSave({
        status: "error",
        message:
          error instanceof Error ? error.message : "Unable to save song facts.",
      });
    }
  }, [draft, factsFile?.song_name, song]);

  const header = <span className="app-rightpanel__kicker">Review queue</span>;

  const footer =
    queueState.status === "ready" ? (
      <>
        {save.status === "error" && (
          <p className="hint-editor__status is-error">{save.message}</p>
        )}
        {save.status === "success" && (
          <p className="hint-editor__status is-ok">Saved to song_facts.json.</p>
        )}
        <div className="hint-editor__actions">
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            className="btn btn-primary"
            disabled={!dirty || save.status === "saving"}
            onClick={() => void doSave()}
          >
            {save.status === "saving" ? "Saving…" : "Save"}
          </button>
        </div>
      </>
    ) : undefined;

  return (
    <RightPanel
      open
      onClose={onClose}
      header={header}
      footer={footer}
      aria-label="Review queue editor"
    >
      {queueState.status === "loading" && (
        <p className="hint-editor__empty">Loading the review queue…</p>
      )}

      {queueState.status === "empty" && (
        <p className="hint-editor__empty">
          This song has no review queue — it has not been analysed under v1.1
          yet. Re-run the analysis pipeline to generate open questions.
        </p>
      )}

      {queueState.status === "error" && (
        <p className="hint-editor__empty">
          Could not load the review queue: {queueState.message}
        </p>
      )}

      {queueState.status === "ready" && (
        <div className="review-queue">
          {queueState.queue.direction_of_flow && (
            <p className="review-queue__flow card-body">
              {queueState.queue.direction_of_flow}
            </p>
          )}

          <section className="review-queue__group">
            <h3 className="review-queue__group-title">
              Whole-song questions
              <span className="review-queue__count">
                {partitioned.wholeSong.length}
              </span>
            </h3>
            {partitioned.wholeSong.length === 0 ? (
              <p className="hint-editor__empty">
                No open whole-song questions for this run.
              </p>
            ) : (
              partitioned.wholeSong.map((question) => {
                const options = questionOptions(question);
                const answered = factLabel(factsFile, question.field);
                const value =
                  draft[question.field] ??
                  (typeof factsFile?.facts?.[question.field]?.value === "string"
                    ? (factsFile.facts[question.field]!.value as string)
                    : "");
                return (
                  <div key={question.field} className="field review-queue__q">
                    <label htmlFor={`rq-${question.field}`}>
                      {question.field}
                    </label>
                    {question.reason_low_confidence && (
                      <p className="review-queue__reason">
                        {question.reason_low_confidence}
                      </p>
                    )}
                    {question.evidence_timestamps.length > 0 && (
                      <p className="review-queue__evidence">
                        evidence:{" "}
                        {question.evidence_timestamps
                          .map((t) => `${t.toFixed(2)}s`)
                          .join(", ")}
                      </p>
                    )}
                    <select
                      id={`rq-${question.field}`}
                      className="input"
                      value={value}
                      onChange={(event) =>
                        setAnswer(question.field, event.target.value)
                      }
                    >
                      <option value="">— choose an answer —</option>
                      {options.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.value} ({option.score.toFixed(2)})
                        </option>
                      ))}
                    </select>
                    {answered && (
                      <p className="review-queue__answered">
                        on disk: {answered}
                      </p>
                    )}
                  </div>
                );
              })
            )}
          </section>

          <section className="review-queue__group">
            <h3 className="review-queue__group-title">
              For context (edit via human hints)
              <span className="review-queue__count">
                {partitioned.context.length}
              </span>
            </h3>
            {partitioned.context.length === 0 ? (
              <p className="hint-editor__empty">No per-section questions.</p>
            ) : (
              <ul className="review-queue__context">
                {partitioned.context.map((question: ReviewQuestion) => (
                  <li key={question.field} className="review-queue__context-item">
                    <div className="review-queue__context-field">
                      {question.field}
                    </div>
                    {question.reason_low_confidence && (
                      <div className="review-queue__reason">
                        {question.reason_low_confidence}
                      </div>
                    )}
                    <div className="review-queue__evidence">
                      candidates:{" "}
                      {questionOptions(question)
                        .map((o) => `${o.value} (${o.score.toFixed(2)})`)
                        .join(", ") || "—"}
                      {question.evidence_timestamps.length > 0 &&
                        ` · @ ${question.evidence_timestamps
                          .map((t) => `${t.toFixed(2)}s`)
                          .join(", ")}`}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      )}
    </RightPanel>
  );
}
