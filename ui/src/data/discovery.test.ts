import { describe, expect, it } from "vitest";

import {
  intersectSongs,
  listAudioBasenames,
  listSubdirectories,
  parseDirectoryIndex,
} from "./discovery";

// The dev server renders this exact `<ul><li><a>` shape (vite.config.ts
// renderDirectoryListing). Song names carry spaces and " - ".
const analysisIndex = `<!doctype html><html><body><h1>Index of /data/analysis/</h1><ul>
  <li><a href="../">../</a></li>
  <li><a href="Hideaway%20-%20Kiesza/">Hideaway - Kiesza/</a></li>
  <li><a href="_test_song/">_test_song/</a></li>
  <li><a href="Only%20Analysed%20No%20Audio/">Only Analysed No Audio/</a></li>
  <li><a href="notes.txt">notes.txt</a></li>
</ul></body></html>`;

const songsIndex = `<!doctype html><html><body><h1>Index of /data/songs/</h1><ul>
  <li><a href="../">../</a></li>
  <li><a href="Hideaway%20-%20Kiesza.mp3">Hideaway - Kiesza.mp3</a></li>
  <li><a href="_test_song.mp3">_test_song.mp3</a></li>
  <li><a href="No%20Analysis%20Yet.wav">No Analysis Yet.wav</a></li>
  <li><a href="cover.jpg">cover.jpg</a></li>
</ul></body></html>`;

describe("parseDirectoryIndex", () => {
  it("skips ../ and decodes names", () => {
    const entries = parseDirectoryIndex(analysisIndex);
    expect(entries).toContainEqual({ name: "Hideaway - Kiesza", isDirectory: true });
    expect(entries).toContainEqual({ name: "notes.txt", isDirectory: false });
    expect(entries.some((e) => e.name === "..")).toBe(false);
  });
});

describe("listSubdirectories", () => {
  it("returns only directories, sorted", () => {
    // sorted by String#localeCompare, matching the previous app's fetch.js
    expect(listSubdirectories(analysisIndex)).toEqual([
      "_test_song",
      "Hideaway - Kiesza",
      "Only Analysed No Audio",
    ]);
  });
});

describe("listAudioBasenames", () => {
  it("strips known audio extensions and ignores other files", () => {
    expect(listAudioBasenames(songsIndex)).toEqual([
      "_test_song",
      "Hideaway - Kiesza",
      "No Analysis Yet",
    ]);
  });
});

describe("intersectSongs", () => {
  it("is analysis dirs ∩ audio basenames", () => {
    expect(intersectSongs(analysisIndex, songsIndex)).toEqual([
      "_test_song",
      "Hideaway - Kiesza",
    ]);
  });

  it("drops an analysed song with no audio and audio with no analysis", () => {
    const songs = intersectSongs(analysisIndex, songsIndex);
    expect(songs).not.toContain("Only Analysed No Audio");
    expect(songs).not.toContain("No Analysis Yet");
  });
});
