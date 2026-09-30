// "Run analysis" header control (v3.8 item 2 / refinement item 1's UI half).
// Sits beside the song title in `.app-header__right` (App.tsx). Writes
// `artifacts/_run_request.json` (`requestRun`) and polls
// `artifacts/_run_progress.json` (`fetchRunProgress`) — both in
// `data/runAnalysis.ts`. Display/poll rules are pure functions in
// `app/runAnalysisState.ts`, unit-tested there; this file only wires them to
// timers and fetches.
//
// No automatic reload on `done` (it would drop unsaved editor state) — the
// operator reloads by hand once they see the message.

import { useCallback, useEffect, useState } from "react";

import { fetchRunProgress, requestRun, type RunProgress } from "./data/runAnalysis";
import {
  effectiveProgress,
  runDisplayStatus,
  shouldPollRunProgress,
} from "./app/runAnalysisState";

const POLL_INTERVAL_MS = 3000;
const NO_WATCHER_TIMEOUT_MS = 120_000;

export function RunAnalysisControl({ song }: { song: string }): React.JSX.Element {
  const [progress, setProgress] = useState<RunProgress | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [requestedAt, setRequestedAt] = useState<number | null>(null);
  const [noWatcherElapsed, setNoWatcherElapsed] = useState(false);
  const [sending, setSending] = useState(false);
  const [errorExpanded, setErrorExpanded] = useState(false);

  const refresh = useCallback(async () => {
    const result = await fetchRunProgress(song);
    if (result.kind === "idle") {
      setProgress(null);
      setLoadError(null);
    } else if (result.kind === "loaded") {
      setProgress(result.data);
      setLoadError(null);
    } else {
      setLoadError(result.message);
    }
  }, [song]);

  // A song switch drops this session's own request/no-watcher state and
  // checks the newly selected song's current file once (it may already be
  // queued/running/done from a prior session or an MCP `request_analysis`
  // call).
  useEffect(() => {
    setProgress(null);
    setLoadError(null);
    setRequestedAt(null);
    setNoWatcherElapsed(false);
    setErrorExpanded(false);
    void refresh();
    // `refresh` is rebuilt only when `song` changes, which is the intended
    // trigger here too.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [song]);

  const poll = shouldPollRunProgress(progress, requestedAt);

  useEffect(() => {
    if (!poll) return;
    const id = window.setInterval(() => void refresh(), POLL_INTERVAL_MS);
    return () => window.clearInterval(id);
  }, [poll, refresh]);

  // 2-minute "no watcher is running" honesty check (plan item 2 bullet 5).
  // Uses `effectiveProgress`, not the raw fetched value: a leftover
  // done/failed row from BEFORE this click (the normal case for a song
  // that's already been analysed once) must not suppress this timer, or a
  // re-run against a dead watcher would sit showing the *previous* run's
  // result forever instead of ever reaching "no watcher is running".
  useEffect(() => {
    if (requestedAt === null || effectiveProgress(progress, requestedAt) !== null) {
      setNoWatcherElapsed(false);
      return;
    }
    const id = window.setTimeout(() => setNoWatcherElapsed(true), NO_WATCHER_TIMEOUT_MS);
    return () => window.clearTimeout(id);
  }, [requestedAt, progress]);

  const status = runDisplayStatus(progress, requestedAt, noWatcherElapsed);
  const active = status.kind === "queued" || status.kind === "running";

  const onClick = useCallback(() => {
    setSending(true);
    setLoadError(null);
    void requestRun(song)
      .then(() => {
        setRequestedAt(Date.now());
        return refresh();
      })
      .catch((error: unknown) => {
        setLoadError(
          error instanceof Error ? error.message : "Unable to start analysis.",
        );
      })
      .finally(() => setSending(false));
  }, [song, refresh]);

  return (
    <div className="app-header__run" data-testid="run-analysis-control">
      <button
        type="button"
        className="btn btn-ghost btn-sm"
        data-testid="run-analysis-button"
        disabled={active || sending}
        onClick={onClick}
      >
        {sending ? "Requesting…" : "Run analysis"}
      </button>
      {loadError ? (
        <span className="app-header__run-status is-error" data-testid="run-analysis-status">
          {loadError}
        </span>
      ) : (
        status.kind !== "idle" && (
          <span className="app-header__run-status" data-testid="run-analysis-status">
            {status.kind === "requested" && "requested…"}
            {status.kind === "queued" && "queued"}
            {status.kind === "running" && `running · ${status.stage ?? "starting"}`}
            {status.kind === "done" &&
              `done${status.finishedAt ? ` ${status.finishedAt}` : ""} — reload to see new results`}
            {status.kind === "no-watcher" &&
              "no watcher is running — start ./analysis-watcher on the host"}
            {status.kind === "failed" && (
              <>
                {"failed "}
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  data-testid="run-analysis-error-toggle"
                  onClick={() => setErrorExpanded((expanded) => !expanded)}
                >
                  {errorExpanded ? "hide" : "details"}
                </button>
                {errorExpanded && (
                  <pre className="app-header__run-error" data-testid="run-analysis-error">
                    {status.error ?? "(no error recorded)"}
                  </pre>
                )}
              </>
            )}
          </span>
        )
      )}
    </div>
  );
}
