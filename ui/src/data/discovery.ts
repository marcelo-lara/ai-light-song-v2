// Song discovery: the set of songs the UI can open is
//   (directories under data/analysis) ∩ (audio files under data/songs)
//
// The dev server renders a plain HTML `<ul><li><a>` directory index for any
// `/data/...` directory (see vite.config.ts). We parse those anchors — the same
// approach as ui.old/src/lib/data/fetch.js.

import { listingPaths } from "./paths";

export const AUDIO_EXTENSIONS = [".mp3", ".wav", ".flac", ".m4a", ".ogg"];

export interface DirEntry {
  name: string;
  isDirectory: boolean;
}

function decodeSegment(value: string): string {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

/** Extract `{ name, isDirectory }` for each real entry in an auto-index page. */
export function parseDirectoryIndex(html: string): DirEntry[] {
  const anchorPattern = /<a\s+href="([^"]+)"[^>]*>([^<]*)<\/a>/gi;
  const entries: DirEntry[] = [];
  for (const match of html.matchAll(anchorPattern)) {
    const href = String(match[1] ?? "").trim();
    if (!href || href === "../") continue;

    const cleanHref = (href.split("?")[0] ?? "").split("#")[0] ?? "";
    if (!cleanHref) continue;

    const segments = cleanHref.split("/").filter(Boolean).map(decodeSegment);
    const rawName =
      segments.at(-1) ?? decodeSegment(cleanHref.replace(/\/+$/, ""));
    const name = rawName.trim();
    if (!name || name === "." || name === "..") continue;

    entries.push({ name, isDirectory: cleanHref.endsWith("/") });
  }
  return entries;
}

/** Sorted, de-duplicated subdirectory names. */
export function listSubdirectories(html: string): string[] {
  const unique = new Set<string>();
  for (const entry of parseDirectoryIndex(html)) {
    if (entry.isDirectory) unique.add(entry.name);
  }
  return [...unique].sort((a, b) => a.localeCompare(b));
}

/** Sorted, de-duplicated file basenames (extension stripped) matching `exts`. */
export function listAudioBasenames(
  html: string,
  exts: string[] = AUDIO_EXTENSIONS,
): string[] {
  const normalized = exts.map((e) => e.toLowerCase());
  const unique = new Set<string>();
  for (const entry of parseDirectoryIndex(html)) {
    if (entry.isDirectory) continue;
    const lower = entry.name.toLowerCase();
    const ext = normalized.find((e) => lower.endsWith(e));
    if (!ext) continue;
    unique.add(entry.name.slice(0, -ext.length));
  }
  return [...unique].sort((a, b) => a.localeCompare(b));
}

/**
 * The selectable songs: analysis directories that also have an audio file,
 * sorted. Pure — takes the two raw index pages.
 */
export function intersectSongs(
  analysisIndexHtml: string,
  songsIndexHtml: string,
): string[] {
  const analysed = listSubdirectories(analysisIndexHtml);
  const audio = new Set(listAudioBasenames(songsIndexHtml));
  return analysed.filter((song) => audio.has(song));
}

export interface Discovery {
  /** analysis dir ∩ audio file — the songs the UI can fully open */
  songs: string[];
  /** every directory under data/analysis (may lack audio) */
  analysed: string[];
  /** every audio basename under data/songs (may lack analysis) */
  audio: string[];
}

export async function discoverSongs(
  fetchImpl: typeof fetch = fetch,
): Promise<Discovery> {
  const [analysisRes, songsRes] = await Promise.all([
    fetchImpl(listingPaths.analysis(), { cache: "no-store" }),
    fetchImpl(listingPaths.songs(), { cache: "no-store" }),
  ]);
  if (!analysisRes.ok) {
    throw new Error(
      `Failed to list data/analysis (${analysisRes.status}).`,
    );
  }
  if (!songsRes.ok) {
    throw new Error(`Failed to list data/songs (${songsRes.status}).`);
  }
  const [analysisHtml, songsHtml] = await Promise.all([
    analysisRes.text(),
    songsRes.text(),
  ]);
  return {
    songs: intersectSongs(analysisHtml, songsHtml),
    analysed: listSubdirectories(analysisHtml),
    audio: listAudioBasenames(songsHtml),
  };
}
