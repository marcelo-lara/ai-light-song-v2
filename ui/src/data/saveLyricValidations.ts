// Client for `PUT /api/lyric-validations/<song>` — mirrors saveBlockEnergy.ts,
// with one deliberate divergence: this writer is **per-click**, not
// explicit-Save (v3.4 item 5 / D5.1 / D6). Each ✔ toggle sends the FULL
// `validated_ids` array and the dev-server handler replaces the file — a rapid
// token-by-token verification pass should not need a Save button.
//
// v3.4 item 5: `reference/human/lyric_validations.json` is an overlay on
// `reference/moises/lyrics.json` — the ids of the Moises word tokens whose
// timing the operator has hand-verified. The Moises Lyrics lane substitutes
// confidence `1` for a listed token at read time; the source file is never
// edited. The operator is the only producer; nothing in `src/` or `mcp/` reads
// the file, and there is no `field_sources` / `source` machinery
// (ui-definition.md "The write rule"; the human-hints-file-stays-simple rule).

import { artifactPaths } from "./paths";
import type { LyricValidationsFile } from "./types";

/** Normalise a set of token ids into the on-disk payload shape (sorted, unique,
 *  integer). Invalid ids are dropped rather than defaulted (no silent
 *  fallbacks). */
export function buildLyricValidationsPayload(
  songName: string,
  ids: readonly number[],
): LyricValidationsFile {
  const seen = new Set<number>();
  for (const raw of ids) {
    const n = typeof raw === "number" ? raw : Number(raw);
    if (Number.isInteger(n) && Number.isFinite(n)) seen.add(n);
  }
  return {
    schema_version: "1.0",
    song_name: String(songName || ""),
    validated_ids: [...seen].sort((a, b) => a - b),
  };
}

/**
 * PUT the full validated-id list. Resolves with the server-normalised file (the
 * new source of truth); rejects with the server's error text on a non-2xx
 * response.
 */
export async function saveLyricValidations(
  song: string,
  payload: LyricValidationsFile,
  fetchImpl: typeof fetch = fetch,
): Promise<LyricValidationsFile> {
  const response = await fetchImpl(
    `/api/lyric-validations/${encodeURIComponent(song)}`,
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
        `Failed to save ${artifactPaths.lyricValidations(song)} (${response.status}).`,
    );
  }

  return (await response.json()) as LyricValidationsFile;
}
