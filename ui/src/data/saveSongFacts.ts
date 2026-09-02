// Client for `PUT /api/song-facts/<song>` — mirrors saveHumanHints.ts.
//
// Story 8.10: only the whole-song review-queue answers (`form_family`,
// `form_family_vs_genre`) are dispositioned into `reference/human/song_facts.json`,
// and only on an explicit human Save. Each answer is stamped
// `provenance: "human-confirmed"` here; the dev-server handler re-stamps it and
// merges onto any facts already on disk. Per-section / drop questions are NOT
// written by this path — they are answered by editing `human_hints.json`.

import { artifactPaths } from "./paths";
import type { SongFactsFile } from "./types";

/** The review-queue fields that disposition into song_facts.json. */
export const WHOLE_SONG_FACT_FIELDS = [
  "form_family",
  "form_family_vs_genre",
] as const;

export type WholeSongFactField = (typeof WHOLE_SONG_FACT_FIELDS)[number];

/** Draft answers keyed by review-queue `field`; values come from `<select>`s. */
export type SongFactsDraft = Record<string, string>;

export interface SongFactsPayloadEntry {
  value: string;
  provenance: "human-confirmed";
}

export interface SongFactsPayload {
  song_name: string;
  facts: Record<string, SongFactsPayloadEntry>;
}

/**
 * Build the PUT payload from draft answers. Keeps ONLY the whole-song keys,
 * drops blank answers, trims, and stamps `provenance: "human-confirmed"`.
 */
export function buildSongFactsPayload(
  songName: string,
  draft: SongFactsDraft,
): SongFactsPayload {
  const facts: Record<string, SongFactsPayloadEntry> = {};
  for (const field of WHOLE_SONG_FACT_FIELDS) {
    const value = (draft[field] ?? "").trim();
    if (!value) continue;
    facts[field] = { value, provenance: "human-confirmed" };
  }
  return { song_name: String(songName || ""), facts };
}

/**
 * PUT the payload. Resolves with the server-normalised file (the new source of
 * truth); rejects with the server's error text on a non-2xx response.
 */
export async function saveSongFacts(
  song: string,
  payload: SongFactsPayload,
  fetchImpl: typeof fetch = fetch,
): Promise<SongFactsFile> {
  const response = await fetchImpl(
    `/api/song-facts/${encodeURIComponent(song)}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    },
  );

  if (!response.ok) {
    const message = await response.text().catch(() => "");
    throw new Error(
      message.trim() ||
        `Failed to save ${artifactPaths.songFacts(song)} (${response.status}).`,
    );
  }

  return (await response.json()) as SongFactsFile;
}
