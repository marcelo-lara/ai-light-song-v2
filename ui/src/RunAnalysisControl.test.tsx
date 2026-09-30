// RunAnalysisControl — v3.8 item 2. Display/poll rules are unit-tested in
// isolation in app/runAnalysisState.test.ts; these tests only cover the
// component's wiring: fetch → state → render, and the timers.

import { act, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { RunAnalysisControl } from "./RunAnalysisControl";

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
    text: async () => JSON.stringify(body),
  } as Response;
}

function notFound(): Response {
  return { ok: false, status: 404, text: async () => "" } as Response;
}

describe("RunAnalysisControl", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("renders idle with no status text on a 404 progress file", async () => {
    const fetchMock = vi.fn().mockResolvedValue(notFound());
    vi.stubGlobal("fetch", fetchMock);

    render(<RunAnalysisControl song="_test_song" />);

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    expect(screen.queryByTestId("run-analysis-status")).toBeNull();
    expect(screen.getByTestId("run-analysis-button")).not.toBeDisabled();
  });

  it("disables the button and shows the stage while running", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        jsonResponse({ song: "_test_song", status: "running", stage: "segment-sections" }),
      );
    vi.stubGlobal("fetch", fetchMock);

    render(<RunAnalysisControl song="_test_song" />);

    await waitFor(() =>
      expect(screen.getByTestId("run-analysis-status")).toHaveTextContent(
        "running · segment-sections",
      ),
    );
    expect(screen.getByTestId("run-analysis-button")).toBeDisabled();
  });

  it("stops polling once the file reaches done", async () => {
    vi.useFakeTimers();
    let call = 0;
    const fetchMock = vi.fn().mockImplementation(async () => {
      call += 1;
      if (call === 1) {
        return jsonResponse({ song: "_test_song", status: "running", stage: "beats" });
      }
      return jsonResponse({ song: "_test_song", status: "done", finished_at: "t" });
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<RunAnalysisControl song="_test_song" />);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(call).toBe(1);

    // one poll tick flips it to "done"
    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
    });
    expect(screen.getByTestId("run-analysis-status").textContent).toMatch(/^done/);
    const callsAtDone = call;

    // further ticks must not fire another fetch — polling stopped
    await act(async () => {
      await vi.advanceTimersByTimeAsync(9000);
    });
    expect(call).toBe(callsAtDone);
  });

  it("shows the no-watcher message 2 minutes after a request with no progress file yet", async () => {
    vi.useFakeTimers();
    const fetchMock = vi.fn().mockImplementation(async (_input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === "PUT") {
        return jsonResponse({ song: "_test_song", requested_at: "now" });
      }
      return notFound();
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<RunAnalysisControl song="_test_song" />);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    await act(async () => {
      screen.getByTestId("run-analysis-button").dispatchEvent(
        new MouseEvent("click", { bubbles: true }),
      );
      await vi.advanceTimersByTimeAsync(0);
    });

    expect(screen.getByTestId("run-analysis-status")).toHaveTextContent("requested…");

    await act(async () => {
      await vi.advanceTimersByTimeAsync(120_000);
    });

    expect(screen.getByTestId("run-analysis-status")).toHaveTextContent(
      "no watcher is running",
    );
  });

  // Bug fix: re-running a song whose _run_progress.json already says
  // done/failed from a PREVIOUS run — the normal case for every analysed
  // song after its first watcher run. Before the fix, `refresh()` right
  // after the click immediately re-read the OLD terminal file (the watcher
  // only rewrites it every ~2 s), so polling never started and the UI got
  // stuck showing the stale result forever.
  it("keeps polling — and shows requested, not the stale row — after a click against an already-done song", async () => {
    vi.useFakeTimers();
    const staleDone = jsonResponse({
      song: "_test_song",
      status: "done",
      finished_at: "2020-01-01T00:00:00Z",
    });
    let getCalls = 0;
    const fetchMock = vi.fn().mockImplementation(async (_input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === "PUT") {
        return jsonResponse({ song: "_test_song", requested_at: "now" });
      }
      getCalls += 1;
      return staleDone; // the watcher hasn't picked up the new request yet
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<RunAnalysisControl song="_test_song" />);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    // Before any click: the stale-but-only-known row is shown as-is (no
    // pending request from this session to compare it against).
    expect(screen.getByTestId("run-analysis-status")).toHaveTextContent(/^done/);

    await act(async () => {
      screen.getByTestId("run-analysis-button").dispatchEvent(
        new MouseEvent("click", { bubbles: true }),
      );
      await vi.advanceTimersByTimeAsync(0);
    });

    // The stale "done" must not resurface after the click.
    expect(screen.getByTestId("run-analysis-status")).toHaveTextContent("requested…");
    const callsAfterClick = getCalls;

    // Polling must still be running — a further tick issues another GET.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(3000);
    });
    expect(getCalls).toBeGreaterThan(callsAfterClick);
    expect(screen.getByTestId("run-analysis-status")).toHaveTextContent("requested…");
  });

  it("still reaches no-watcher after a click against a song whose file is a stale failed row", async () => {
    vi.useFakeTimers();
    const staleFailed = jsonResponse({
      song: "_test_song",
      status: "failed",
      error: "old failure",
      finished_at: "2020-01-01T00:00:00Z",
    });
    const fetchMock = vi.fn().mockImplementation(async (_input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.method === "PUT") {
        return jsonResponse({ song: "_test_song", requested_at: "now" });
      }
      return staleFailed;
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<RunAnalysisControl song="_test_song" />);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });

    await act(async () => {
      screen.getByTestId("run-analysis-button").dispatchEvent(
        new MouseEvent("click", { bubbles: true }),
      );
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(screen.getByTestId("run-analysis-status")).toHaveTextContent("requested…");

    // Without the fix, a non-null (but stale) progress value suppressed the
    // no-watcher timer entirely, so this would never appear.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(120_000);
    });
    expect(screen.getByTestId("run-analysis-status")).toHaveTextContent(
      "no watcher is running",
    );
  });
});
