// lyricValidations.ts — `PUT /api/lyric-validations/<song>`, writing
// reference/human/lyric_validations.json. Split out of vite.config.ts (v3.9
// item 7) with no behaviour change.

import type { IncomingMessage, ServerResponse } from "node:http";

import { readJsonBody, referenceHumanFilePath, writeJsonFile } from "./shared";

// v3.4 item 5 — lyric_validations.json is written PER-CLICK by the Moises
// Lyrics events panel's ✔ button (D5.1 / D6). This diverges from the
// explicit-Save pattern the other reference/human/ writers (human hints, song
// facts) use: a rapid token-by-token verification pass should not
// need a Save button. Each toggle PUTs the FULL `validated_ids` array and this
// handler replaces the file. Overlay only — nothing here touches
// reference/moises/lyrics.json, which stays read-only. Dev-only (production
// Nginx has no handler). Nothing in src/ or mcp/ reads the file.
export function lyricValidationsFilePath(song: unknown): string {
  return referenceHumanFilePath(song, "lyric_validations.json");
}

export function normalizeLyricValidationsPayload(payload: unknown): {
  schema_version: string;
  song_name: string;
  validated_ids: number[];
} {
  if (!payload || typeof payload !== "object") {
    throw new Error("Lyric validations payload must be a JSON object.");
  }
  const record = payload as Record<string, unknown>;
  const idsIn = Array.isArray(record.validated_ids) ? record.validated_ids : null;
  if (!idsIn) {
    throw new Error(
      "Lyric validations payload must include a validated_ids array.",
    );
  }
  const seen = new Set<number>();
  for (const value of idsIn) {
    if (typeof value !== "number" || !Number.isInteger(value)) {
      throw new Error("Each validated_id must be an integer.");
    }
    seen.add(value);
  }
  return {
    schema_version: "1.0",
    song_name: String(record.song_name || ""),
    validated_ids: [...seen].sort((a, b) => a - b),
  };
}

export async function handleLyricValidations(
  song: string,
  request: IncomingMessage,
  response: ServerResponse,
): Promise<void> {
  try {
    const payload = normalizeLyricValidationsPayload(await readJsonBody(request));
    await writeJsonFile(lyricValidationsFilePath(song), payload);
    response.statusCode = 200;
    response.setHeader("Content-Type", "application/json; charset=utf-8");
    response.end(JSON.stringify(payload));
  } catch (error) {
    response.statusCode = 400;
    response.setHeader("Content-Type", "text/plain; charset=utf-8");
    response.end(
      error instanceof Error ? error.message : "Unable to save lyric validations.",
    );
  }
}
