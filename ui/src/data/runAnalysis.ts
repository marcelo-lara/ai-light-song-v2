// Client for the run-request/run-progress pair (v3.8 items 1-3): the
// debugger's "Run analysis" button (this file) and mcp/runs.py's
// `request_analysis` both write the same `artifacts/_run_request.json`; the
// host-side `./analysis-watcher` (item 1, not in this repo's containers)
// reads it, runs `./analyze`, and writes `artifacts/_run_progress.json` as
// it goes. Neither file is `reference/human/` material or a delivery
// artifact — see `docs/ui-definition.md`'s write-rule section and
// `docs/mcp-definition.md`'s D3.1 exception.

import { ShapeError, asObject, asString, stringOrNull } from "./parse";
import { artifactPaths } from "./paths";

export type RunStatus = "queued" | "running" | "done" | "failed";

const RUN_STATUSES: readonly RunStatus[] = ["queued", "running", "done", "failed"];

export interface RunProgress {
  song: string;
  status: RunStatus;
  stage: string | null;
  requested_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  error: string | null;
}

export function parseRunProgress(raw: unknown): RunProgress {
  const o = asObject(raw, "artifacts/_run_progress.json");
  const status = asString(o.status, "artifacts/_run_progress.json.status");
  if (!(RUN_STATUSES as string[]).includes(status)) {
    throw new ShapeError(
      `artifacts/_run_progress.json.status: expected one of ${RUN_STATUSES.join(", ")}, got "${status}"`,
    );
  }
  return {
    song: stringOrNull(o.song, "artifacts/_run_progress.json.song") ?? "",
    status: status as RunStatus,
    stage: stringOrNull(o.stage, "artifacts/_run_progress.json.stage"),
    requested_at: stringOrNull(
      o.requested_at,
      "artifacts/_run_progress.json.requested_at",
    ),
    started_at: stringOrNull(
      o.started_at,
      "artifacts/_run_progress.json.started_at",
    ),
    finished_at: stringOrNull(
      o.finished_at,
      "artifacts/_run_progress.json.finished_at",
    ),
    error: stringOrNull(o.error, "artifacts/_run_progress.json.error"),
  };
}

export type RunProgressResult =
  // No `_run_progress.json` yet — the expected idle state (no run requested,
  // or the watcher has not picked the request up yet). Never logged as an
  // error.
  | { kind: "idle" }
  | { kind: "loaded"; data: RunProgress }
  | { kind: "error"; message: string };

/** `GET` `_run_progress.json`. A 404 is idle, not an error — never console-logged. */
export async function fetchRunProgress(
  song: string,
  fetchImpl: typeof fetch = fetch,
): Promise<RunProgressResult> {
  let response: Response;
  try {
    response = await fetchImpl(artifactPaths.runProgress(song), {
      cache: "no-store",
    });
  } catch (error) {
    return {
      kind: "error",
      message: error instanceof Error ? error.message : "Failed to reach the progress file.",
    };
  }
  if (response.status === 404) {
    return { kind: "idle" };
  }
  if (!response.ok) {
    const detail = await response.text().catch(() => "");
    return {
      kind: "error",
      message: detail.trim() || `Progress read failed (${response.status}).`,
    };
  }
  try {
    const raw = await response.json();
    return { kind: "loaded", data: parseRunProgress(raw) };
  } catch (error) {
    return {
      kind: "error",
      message:
        error instanceof ShapeError || error instanceof Error
          ? error.message
          : "Invalid progress file.",
    };
  }
}

/** `PUT /api/run-request/<song>` — starts (or re-queues) a full analysis run. */
export async function requestRun(
  song: string,
  fetchImpl: typeof fetch = fetch,
): Promise<{ song: string; requested_at: string }> {
  const response = await fetchImpl(`/api/run-request/${encodeURIComponent(song)}`, {
    method: "PUT",
  });
  if (!response.ok) {
    const message = await response.text().catch(() => "");
    throw new Error(
      message.trim() || `Failed to request an analysis run (${response.status}).`,
    );
  }
  return (await response.json()) as { song: string; requested_at: string };
}
