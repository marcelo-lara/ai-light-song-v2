import { describe, expect, it } from "vitest";

import { fileKind, groupByDir, walkDataDir } from "./walk";

// A fake `/data` listing endpoint: URL → directory-index HTML, in the exact
// `<ul><li><a>` shape vite.config.ts renders (dirs end with "/").
function fakeIndex(entries: string[]): string {
  const items = entries
    .map((name) => `<li><a href="${encodeURIComponent(name.replace(/\/$/, ""))}${name.endsWith("/") ? "/" : ""}">${name}</a></li>`)
    .join("\n");
  return `<!doctype html><html><body><ul>\n<li><a href="../">../</a></li>\n${items}\n</ul></body></html>`;
}

function makeFetch(tree: Record<string, string[]>): typeof fetch {
  return (async (input: RequestInfo | URL) => {
    const url = String(input);
    const entries = tree[url];
    if (!entries) {
      return { ok: false, status: 404, text: async () => "" } as Response;
    }
    return { ok: true, status: 200, text: async () => fakeIndex(entries) } as Response;
  }) as typeof fetch;
}

const SONG = "Hideaway - Kiesza";
const root = "/data/analysis/Hideaway%20-%20Kiesza";

const tree: Record<string, string[]> = {
  [`${root}/`]: ["info.json", "beats.json", "artifacts/", "reference/"],
  [`${root}/artifacts/`]: ["genre.json", "essentia/", "validation/"],
  [`${root}/artifacts/essentia/`]: ["fft_bands.json", "rms_loudness.json"],
  [`${root}/artifacts/validation/`]: ["review_queue.json", "phase_1_report.md"],
  [`${root}/reference/`]: ["human/"],
  [`${root}/reference/human/`]: ["human_hints.json"],
};

describe("walkDataDir", () => {
  it("recursively lists every file, sorted by relative path", async () => {
    const files = await walkDataDir(["data", "analysis", SONG], makeFetch(tree));
    expect(files.map((f) => f.relativePath)).toEqual([
      "artifacts/essentia/fft_bands.json",
      "artifacts/essentia/rms_loudness.json",
      "artifacts/genre.json",
      "artifacts/validation/phase_1_report.md",
      "artifacts/validation/review_queue.json",
      "beats.json",
      "info.json",
      "reference/human/human_hints.json",
    ]);
  });

  it("builds percent-encoded absolute /data URLs and split dir/name", async () => {
    const files = await walkDataDir(["data", "analysis", SONG], makeFetch(tree));
    const fft = files.find((f) => f.name === "fft_bands.json");
    expect(fft?.url).toBe(`${root}/artifacts/essentia/fft_bands.json`);
    expect(fft?.dir).toBe("artifacts/essentia");
    expect(files.find((f) => f.name === "info.json")?.dir).toBe("");
  });

  it("throws when a directory listing 404s", async () => {
    await expect(
      walkDataDir(["data", "analysis", "missing song"], makeFetch(tree)),
    ).rejects.toThrow(/Failed to list/);
  });
});

describe("groupByDir", () => {
  it("groups files by directory in locale order", async () => {
    const files = await walkDataDir(["data", "analysis", SONG], makeFetch(tree));
    const groups = groupByDir(files);
    expect(groups.map((g) => g.dir)).toEqual([
      "",
      "artifacts",
      "artifacts/essentia",
      "artifacts/validation",
      "reference/human",
    ]);
    expect(groups[1]?.files.map((f) => f.name)).toEqual(["genre.json"]);
  });
});

describe("fileKind", () => {
  it("classifies by extension", () => {
    expect(fileKind("fft_bands.json")).toBe("json");
    expect(fileKind("phase_1_report.md")).toBe("text");
    expect(fileKind("drums.mid")).toBe("binary");
    expect(fileKind("bass.wav")).toBe("binary");
  });
});
