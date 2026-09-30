import { describe, expect, it } from "vitest";

import type { RunProgress } from "../data/runAnalysis";
import {
  effectiveProgress,
  isRunActive,
  runDisplayStatus,
  shouldPollRunProgress,
} from "./runAnalysisState";

const progress = (over: Partial<RunProgress> = {}): RunProgress => ({
  song: "_test_song",
  status: "queued",
  stage: null,
  requested_at: null,
  started_at: null,
  finished_at: null,
  error: null,
  ...over,
});

describe("effectiveProgress", () => {
  it("passes a non-terminal (queued/running) row through unchanged, regardless of requestedAt", () => {
    const running = progress({ status: "running", stage: "beats" });
    expect(effectiveProgress(running, Date.now())).toBe(running);
  });

  it("passes a terminal row through unchanged when this session never requested a run", () => {
    const done = progress({ status: "done", finished_at: "2020-01-01T00:00:00Z" });
    expect(effectiveProgress(done, null)).toBe(done);
  });

  it("treats a terminal row from BEFORE requestedAt as stale — the normal re-run case", () => {
    const requestedAt = Date.now();
    const staleDone = progress({
      status: "done",
      finished_at: new Date(requestedAt - 60_000).toISOString(),
    });
    expect(effectiveProgress(staleDone, requestedAt)).toBeNull();

    const staleFailed = progress({
      status: "failed",
      error: "old failure",
      finished_at: new Date(requestedAt - 60_000).toISOString(),
    });
    expect(effectiveProgress(staleFailed, requestedAt)).toBeNull();
  });

  it("treats a terminal row with no (or unparsable) finished_at as stale — cannot prove it's fresh", () => {
    const requestedAt = Date.now();
    expect(
      effectiveProgress(progress({ status: "done", finished_at: null }), requestedAt),
    ).toBeNull();
    expect(
      effectiveProgress(
        progress({ status: "failed", finished_at: "not-a-date" }),
        requestedAt,
      ),
    ).toBeNull();
  });

  it("keeps a terminal row whose finished_at is AFTER requestedAt — a genuinely fresh result", () => {
    const requestedAt = Date.now();
    const freshDone = progress({
      status: "done",
      finished_at: new Date(requestedAt + 1000).toISOString(),
    });
    expect(effectiveProgress(freshDone, requestedAt)).toBe(freshDone);
  });

  it("passes null through unchanged", () => {
    expect(effectiveProgress(null, Date.now())).toBeNull();
  });
});

describe("runDisplayStatus", () => {
  it("is idle with no progress file and no pending request", () => {
    expect(runDisplayStatus(null, null, false)).toEqual({ kind: "idle" });
  });

  it("is requested right after a click, before the watcher writes anything or the timeout elapses", () => {
    expect(runDisplayStatus(null, Date.now(), false)).toEqual({ kind: "requested" });
  });

  it("is no-watcher once the 2-minute flag is set with still no fresh progress file", () => {
    expect(runDisplayStatus(null, Date.now(), true)).toEqual({ kind: "no-watcher" });
  });

  it("reports queued/running/done/failed from a progress file with no pending request", () => {
    expect(runDisplayStatus(progress({ status: "queued" }), null, false)).toEqual({
      kind: "queued",
    });
    expect(
      runDisplayStatus(progress({ status: "running", stage: "beats" }), null, false),
    ).toEqual({ kind: "running", stage: "beats" });
    expect(
      runDisplayStatus(progress({ status: "done", finished_at: "t" }), null, false),
    ).toEqual({ kind: "done", finishedAt: "t" });
    expect(
      runDisplayStatus(progress({ status: "failed", error: "boom" }), null, false),
    ).toEqual({ kind: "failed", error: "boom" });
  });

  it("shows requested, not the stale terminal row, for a re-run against a song already done/failed", () => {
    const requestedAt = Date.now();
    const stale = progress({
      status: "done",
      finished_at: new Date(requestedAt - 60_000).toISOString(),
    });
    expect(runDisplayStatus(stale, requestedAt, false)).toEqual({ kind: "requested" });
  });

  it("shows the real done/failed once the file postdates the request", () => {
    const requestedAt = Date.now();
    const fresh = progress({
      status: "failed",
      error: "boom",
      finished_at: new Date(requestedAt + 1000).toISOString(),
    });
    expect(runDisplayStatus(fresh, requestedAt, false)).toEqual({
      kind: "failed",
      error: "boom",
    });
  });
});

describe("isRunActive / shouldPollRunProgress", () => {
  it("is active only for queued/running", () => {
    expect(isRunActive(progress({ status: "queued" }))).toBe(true);
    expect(isRunActive(progress({ status: "running" }))).toBe(true);
    expect(isRunActive(progress({ status: "done" }))).toBe(false);
    expect(isRunActive(progress({ status: "failed" }))).toBe(false);
    expect(isRunActive(null)).toBe(false);
  });

  it("polls while active", () => {
    expect(shouldPollRunProgress(progress({ status: "running" }), null)).toBe(true);
  });

  it("polls after a fresh request even before any progress file exists", () => {
    expect(shouldPollRunProgress(null, Date.now())).toBe(true);
  });

  it("stops polling once a FRESH file reaches a terminal state (finished_at after requestedAt)", () => {
    const requestedAt = Date.now();
    const afterRequest = new Date(requestedAt + 1000).toISOString();
    expect(
      shouldPollRunProgress(progress({ status: "done", finished_at: afterRequest }), requestedAt),
    ).toBe(false);
    expect(
      shouldPollRunProgress(
        progress({ status: "failed", finished_at: afterRequest }),
        requestedAt,
      ),
    ).toBe(false);
  });

  it("keeps polling a STALE done/failed row left over from a previous run — the re-run bug", () => {
    const requestedAt = Date.now();
    const beforeRequest = new Date(requestedAt - 60_000).toISOString();
    expect(
      shouldPollRunProgress(
        progress({ status: "done", finished_at: beforeRequest }),
        requestedAt,
      ),
    ).toBe(true);
    expect(
      shouldPollRunProgress(
        progress({ status: "failed", finished_at: beforeRequest }),
        requestedAt,
      ),
    ).toBe(true);
  });

  it("does not poll idle with no pending request", () => {
    expect(shouldPollRunProgress(null, null)).toBe(false);
  });
});
