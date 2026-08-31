// Recursive directory walk over the dev-server `/data` listing endpoint.
//
// The dev server renders a plain `<ul><li><a>` directory index for any
// `/data/...` directory (see vite.config.ts `renderDirectoryListing`). We reuse
// the same anchor parser the song-discovery code uses and recurse into every
// subdirectory to produce a flat, sorted file list for the artifact inspector.
//
// Read-only: this module only ever issues GETs against the listing endpoint.

import { parseDirectoryIndex } from "../data/discovery";
import { encodePath } from "../data/paths";

export interface WalkedFile {
  /** Path segments relative to the walk root, e.g. ["essentia", "fft_bands.json"]. */
  segments: string[];
  /** "/"-joined relative path, e.g. "essentia/fft_bands.json". */
  relativePath: string;
  /** Directory portion of `relativePath` ("" for a file at the root). */
  dir: string;
  /** File basename. */
  name: string;
  /** Absolute, percent-encoded `/data/...` URL to fetch the file. */
  url: string;
}

const byName = (a: { name: string }, b: { name: string }): number =>
  a.name.localeCompare(b.name);

/**
 * Recursively list every file under `rootSegments` (an absolute `/data`-rooted
 * segment array, e.g. `["data", "analysis", song, "artifacts"]`).
 *
 * Pure except for `fetchImpl`; tests pass a fake backed by a URL→HTML map.
 * Directories are visited depth-first in locale order; the returned list is
 * sorted by `relativePath`.
 */
export async function walkDataDir(
  rootSegments: string[],
  fetchImpl: typeof fetch = fetch,
): Promise<WalkedFile[]> {
  const files: WalkedFile[] = [];

  async function recurse(
    segments: string[],
    relative: string[],
  ): Promise<void> {
    const listingUrl = encodePath(segments) + "/";
    const response = await fetchImpl(listingUrl, { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`Failed to list ${listingUrl} (${response.status}).`);
    }
    const entries = parseDirectoryIndex(await response.text());
    const dirs = entries.filter((entry) => entry.isDirectory).sort(byName);
    const plainFiles = entries.filter((entry) => !entry.isDirectory).sort(byName);

    for (const file of plainFiles) {
      const relSegments = [...relative, file.name];
      files.push({
        segments: relSegments,
        relativePath: relSegments.join("/"),
        dir: relative.join("/"),
        name: file.name,
        url: encodePath([...segments, file.name]),
      });
    }
    for (const dir of dirs) {
      await recurse([...segments, dir.name], [...relative, dir.name]);
    }
  }

  await recurse(rootSegments, []);
  files.sort((a, b) => a.relativePath.localeCompare(b.relativePath));
  return files;
}

export interface FileGroup {
  /** "/"-joined directory path relative to the walk root ("" = root). */
  dir: string;
  files: WalkedFile[];
}

/** Group a flat walk result by directory, groups and files each in locale order. */
export function groupByDir(files: WalkedFile[]): FileGroup[] {
  const groups = new Map<string, WalkedFile[]>();
  for (const file of files) {
    const bucket = groups.get(file.dir);
    if (bucket) bucket.push(file);
    else groups.set(file.dir, [file]);
  }
  return [...groups.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([dir, groupFiles]) => ({
      dir,
      files: [...groupFiles].sort((a, b) => a.name.localeCompare(b.name)),
    }));
}

const JSON_EXT = /\.json$/i;
const TEXT_EXT = /\.(md|txt|csv|log)$/i;

export type FileKind = "json" | "text" | "binary";

export function fileKind(name: string): FileKind {
  if (JSON_EXT.test(name)) return "json";
  if (TEXT_EXT.test(name)) return "text";
  return "binary";
}
