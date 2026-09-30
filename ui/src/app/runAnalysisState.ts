// Pure state derivation for the "Run analysis" header control (v3.8 item 2,
// RunAnalysisControl.tsx). Kept React-free so the display/poll rules are
// unit-testable without mounting a component.

import type { RunProgress } from "../data/runAnalysis";

export type RunDisplayStatus =
  | { kind: "idle" }
  | { kind: "requested" }
  | { kind: "queued" }
  | { kind: "running"; stage: string | null }
  | { kind: "done"; finishedAt: string | null }
  | { kind: "failed"; error: string | null }
  | { kind: "no-watcher" };

/**
 * A terminal (`done`/`failed`) progress file from BEFORE this session's own
 * `requestedAt` is a stale leftover from a previous run — the normal case for
 * every analysed song after its first watcher run, since the watcher only
 * rewrites the file every ~2 s after it takes a new job. Treated as if no
 * file existed at all (`null`) for polling, the no-watcher timer, and
 * display, so a re-run click never gets stuck showing the *previous* run's
 * result. A `queued`/`running` file is never stale by this definition (a
 * still-in-flight run is real regardless of when it started); a missing or
 * unparsable `finished_at` on a terminal row is treated as stale too — we
 * cannot prove it postdates this click, and an honest "unknown, so assume
 * stale" beats trusting a row we can't date (no-silent-fallbacks).
 */
export function effectiveProgress(
  progress: RunProgress | null,
  requestedAt: number | null,
): RunProgress | null {
  if (progress === null || requestedAt === null) return progress;
  if (progress.status !== "done" && progress.status !== "failed") return progress;
  const finishedAtMs = progress.finished_at ? Date.parse(progress.finished_at) : NaN;
  const isStale = Number.isNaN(finishedAtMs) || finishedAtMs < requestedAt;
  return isStale ? null : progress;
}

/**
 * `progress` is the last-fetched `_run_progress.json` (`null` for a 404 — no
 * run requested, or the watcher hasn't picked the request up yet).
 * `requestedAt` is this browser session's own last `PUT`
 * (`Date.now()`), or `null` if this session hasn't clicked the button.
 * `noWatcherElapsed` is true once 2 minutes have passed since `requestedAt`
 * with the *effective* progress still `null` — the caller owns the timer;
 * this function only decides what to show given the flag (honesty rule, plan
 * item 2 bullet 5: "no watcher is running" beats an indefinite silent wait).
 */
export function runDisplayStatus(
  progress: RunProgress | null,
  requestedAt: number | null,
  noWatcherElapsed: boolean,
): RunDisplayStatus {
  const effective = effectiveProgress(progress, requestedAt);
  if (effective === null) {
    if (requestedAt === null) return { kind: "idle" };
    return noWatcherElapsed ? { kind: "no-watcher" } : { kind: "requested" };
  }
  switch (effective.status) {
    case "queued":
      return { kind: "queued" };
    case "running":
      return { kind: "running", stage: effective.stage };
    case "done":
      return { kind: "done", finishedAt: effective.finished_at };
    case "failed":
      return { kind: "failed", error: effective.error };
  }
}

export function isRunActive(progress: RunProgress | null): boolean {
  return progress?.status === "queued" || progress?.status === "running";
}

/**
 * Poll while a run is in flight, or while waiting to find out whether the
 * watcher noticed a just-sent request (before any progress file exists yet,
 * or while the only file on record is a stale leftover from a previous run —
 * see `effectiveProgress`). Stops once the file shows a *fresh* terminal
 * state (`done`/`failed`).
 */
export function shouldPollRunProgress(
  progress: RunProgress | null,
  requestedAt: number | null,
): boolean {
  const effective = effectiveProgress(progress, requestedAt);
  return isRunActive(effective) || (requestedAt !== null && effective === null);
}
