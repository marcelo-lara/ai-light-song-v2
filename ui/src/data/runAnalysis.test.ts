import { describe, expect, it, vi } from "vitest";

import { fetchRunProgress, parseRunProgress, requestRun } from "./runAnalysis";

function fetchReturning(init: Partial<Response>): typeof fetch {
  return vi.fn().mockResolvedValue(init as Response) as unknown as typeof fetch;
}

describe("parseRunProgress", () => {
  it("parses a full progress row", () => {
    const parsed = parseRunProgress({
      song: "_test_song",
      status: "running",
      stage: "segment-sections",
      requested_at: "2026-09-23T00:00:00Z",
      started_at: "2026-09-23T00:00:05Z",
      finished_at: null,
      error: null,
    });
    expect(parsed.status).toBe("running");
    expect(parsed.stage).toBe("segment-sections");
    expect(parsed.finished_at).toBeNull();
  });

  it("rejects an unknown status", () => {
    expect(() => parseRunProgress({ status: "bogus" })).toThrow();
  });

  it("defaults nullable fields to null when absent", () => {
    const parsed = parseRunProgress({ song: "s", status: "queued" });
    expect(parsed.stage).toBeNull();
    expect(parsed.error).toBeNull();
  });
});

describe("fetchRunProgress", () => {
  it("is idle on a 404 — the expected no-run-requested state", async () => {
    const result = await fetchRunProgress(
      "_test_song",
      fetchReturning({ ok: false, status: 404, text: async () => "" }),
    );
    expect(result.kind).toBe("idle");
  });

  it("loads a valid progress file", async () => {
    const result = await fetchRunProgress(
      "_test_song",
      fetchReturning({
        ok: true,
        status: 200,
        json: async () => ({ song: "_test_song", status: "done" }),
      }),
    );
    expect(result.kind).toBe("loaded");
    if (result.kind === "loaded") expect(result.data.status).toBe("done");
  });

  it("reports a non-404 HTTP failure as an error, not idle", async () => {
    const result = await fetchRunProgress(
      "_test_song",
      fetchReturning({ ok: false, status: 500, text: async () => "boom" }),
    );
    expect(result.kind).toBe("error");
  });
});

describe("requestRun", () => {
  it("PUTs to /api/run-request/<song> and returns the written payload", async () => {
    const fetchImpl = fetchReturning({
      ok: true,
      json: async () => ({ song: "_test_song", requested_at: "2026-09-23T00:00:00Z" }),
    });
    const result = await requestRun("_test_song", fetchImpl);
    expect(fetchImpl).toHaveBeenCalledWith(
      "/api/run-request/_test_song",
      expect.objectContaining({ method: "PUT" }),
    );
    expect(result.song).toBe("_test_song");
  });

  it("throws with the server's message on failure", async () => {
    const fetchImpl = fetchReturning({
      ok: false,
      status: 400,
      text: async () => "Song name is required.",
    });
    await expect(requestRun("", fetchImpl)).rejects.toThrow(/Song name is required/);
  });
});
