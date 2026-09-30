// PUT /api/run-request/<song>'s song-name guard. The mkdir/write path
// itself is covered by a host end-to-end run of the Run analysis button
// against ./analysis-watcher (not importable here — see
// runRequestGuard.ts's header comment for why this stays out of
// vite.config.ts's own module for testing).

import { describe, expect, it } from "vitest";

import { validateRunRequestSong } from "./runRequestGuard";

describe("validateRunRequestSong", () => {
  it("accepts a plain song name", () => {
    expect(validateRunRequestSong("Cinderella - Ella Lee")).toBe(
      "Cinderella - Ella Lee",
    );
  });

  it("rejects a forward slash", () => {
    expect(() => validateRunRequestSong("a/b")).toThrow();
  });

  it("rejects a backslash", () => {
    expect(() => validateRunRequestSong("a\\b")).toThrow();
  });

  it("rejects a parent-directory escape", () => {
    expect(() => validateRunRequestSong("../etc")).toThrow();
  });

  it("rejects an empty or whitespace-only name", () => {
    expect(() => validateRunRequestSong("")).toThrow();
    expect(() => validateRunRequestSong("   ")).toThrow();
  });
});
