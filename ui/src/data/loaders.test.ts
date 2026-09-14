import { describe, expect, it, vi } from "vitest";

import {
  loadJson,
  loadInfo,
  loadBlockEnergy,
  loadLyricValidations,
} from "./loaders";
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

describe("loadBlockEnergy", () => {
  it("maps a 404 to an empty ratings file (v3.4 item 4)", async () => {
    const fetchImpl = (async () =>
      new Response("Not found", { status: 404 })) as unknown as typeof fetch;
    const result = await loadBlockEnergy("Unrated Song", fetchImpl);
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.data).toEqual({
        schema_version: "",
        song_name: "Unrated Song",
        ratings: [],
      });
    }
  });

  it("still reports a real failure", async () => {
    const fetchImpl = (async () =>
      new Response("boom", { status: 500 })) as unknown as typeof fetch;
    expect((await loadBlockEnergy("Broken", fetchImpl)).ok).toBe(false);
  });

  it("parses a real ratings file", async () => {
    const fetchImpl = fetchReturning({
      schema_version: "1.0",
      song_name: "s",
      ratings: [{ hint_id: "hint-001", energy: 5, tension: 4 }],
    });
    const result = await loadBlockEnergy("s", fetchImpl);
    expect(result.ok).toBe(true);
    if (result.ok) expect(result.data.ratings).toHaveLength(1);
  });
});

describe("loadLyricValidations", () => {
  it("maps a 404 to an empty file (v3.4 item 5)", async () => {
    const fetchImpl = (async () =>
      new Response("Not found", { status: 404 })) as unknown as typeof fetch;
    const result = await loadLyricValidations("Unvalidated", fetchImpl);
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.data).toEqual({
        schema_version: "",
        song_name: "Unvalidated",
        validated_ids: [],
      });
    }
  });

  it("still reports a real failure", async () => {
    const fetchImpl = (async () =>
      new Response("boom", { status: 500 })) as unknown as typeof fetch;
    expect((await loadLyricValidations("Broken", fetchImpl)).ok).toBe(false);
  });

  it("parses a real overlay file", async () => {
    const fetchImpl = fetchReturning({
      schema_version: "1.0",
      song_name: "s",
      validated_ids: [2, 3],
    });
    const result = await loadLyricValidations("s", fetchImpl);
    expect(result.ok).toBe(true);
    if (result.ok) expect(result.data.validated_ids).toEqual([2, 3]);
  });
});
