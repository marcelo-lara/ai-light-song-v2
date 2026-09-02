import { describe, expect, it, vi } from "vitest";

import { loadJson, loadInfo } from "./loaders";
import { loadDropProposals } from "./sparseArtifacts";
import { parseInfo } from "./parsers";

import infoFixture from "./__fixtures__/info.json";

function fetchReturning(body: unknown, init: Partial<Response> = {}): typeof fetch {
  return vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => body,
    text: async () => JSON.stringify(body),
    ...init,
  }) as unknown as typeof fetch;
}

describe("loadJson", () => {
  it("returns { ok: true, data } for a valid document", async () => {
    const res = await loadInfo("_test_song", fetchReturning(infoFixture));
    expect(res.ok).toBe(true);
    if (res.ok) expect(res.data.song_name).toBe("_test_song");
  });

  it("maps a 404 to a typed http error", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: false,
      status: 404,
      text: async () => "Not found: /data/x",
    } as Response) as unknown as typeof fetch;
    const res = await loadJson("/data/x", parseInfo, fetchImpl);
    expect(res.ok).toBe(false);
    if (!res.ok) {
      expect(res.error.kind).toBe("http");
      expect(res.error.status).toBe(404);
    }
  });

  it("maps invalid JSON to a parse error", async () => {
    const fetchImpl = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => {
        throw new SyntaxError("bad");
      },
    } as unknown as Response) as unknown as typeof fetch;
    const res = await loadJson("/data/x", parseInfo, fetchImpl);
    expect(res.ok).toBe(false);
    if (!res.ok) expect(res.error.kind).toBe("parse");
  });

  it("maps a contract mismatch to a shape error", async () => {
    const res = await loadJson(
      "/data/x",
      parseInfo,
      fetchReturning({ nope: true }),
    );
    expect(res.ok).toBe(false);
    if (!res.ok) expect(res.error.kind).toBe("shape");
  });

  it("maps a network failure to a network error", async () => {
    const fetchImpl = vi
      .fn()
      .mockRejectedValue(new TypeError("Failed to fetch")) as unknown as typeof fetch;
    const res = await loadJson("/data/x", parseInfo, fetchImpl);
    expect(res.ok).toBe(false);
    if (!res.ok) expect(res.error.kind).toBe("network");
  });
});

describe("loadDropProposals", () => {
  it("treats a missing proposals file as an empty lane, not an error", async () => {
    const fetchImpl = (async () =>
      new Response("Not found", { status: 404 })) as unknown as typeof fetch;
    const result = await loadDropProposals("Nothing Exported", fetchImpl);
    expect(result.ok).toBe(true);
    if (result.ok) expect(result.data.proposals).toEqual([]);
  });

  it("still reports a real failure", async () => {
    const fetchImpl = (async () =>
      new Response("boom", { status: 500 })) as unknown as typeof fetch;
    const result = await loadDropProposals("Broken", fetchImpl);
    expect(result.ok).toBe(false);
  });
});
