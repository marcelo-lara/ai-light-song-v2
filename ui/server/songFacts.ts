// songFacts.ts — `PUT /api/song-facts/<song>`, writing
// reference/human/song_facts.json. Split out of vite.config.ts (v3.9 item 7)
// with no behaviour change.

import fsp from "node:fs/promises";
import type { IncomingMessage, ServerResponse } from "node:http";

import { readJsonBody, referenceHumanFilePath, writeJsonFile } from "./shared";

// v1.1 Story 8.10 — song_facts.json is written ONLY by an explicit human Save
// (the same rule Story 8.8 applies to human hints); the analyzer never writes
// `reference/`. Only the whole-song review-queue answers land here.
export function songFactsFilePath(song: unknown): string {
  return referenceHumanFilePath(song, "song_facts.json");
}

// Whole-song review-queue fields that disposition into song_facts.json.
const SONG_FACT_KEYS = new Set(["form_family"]);

export async function normalizeSongFactsPayload(
  payload: unknown,
  song: string,
): Promise<{
  schema_version: string;
  song_name: string;
  facts: Record<string, Record<string, unknown>>;
}> {
  if (!payload || typeof payload !== "object") {
    throw new Error("Song facts payload must be a JSON object.");
  }
  const record = payload as Record<string, unknown>;
  const factsIn =
    record.facts && typeof record.facts === "object"
      ? (record.facts as Record<string, unknown>)
      : {};

  // Merge onto whatever a prior human Save already wrote, so answering one
  // question does not drop the others.
  let existingFacts: Record<string, Record<string, unknown>> = {};
  try {
    const current = JSON.parse(
      await fsp.readFile(songFactsFilePath(song), "utf-8"),
    ) as Record<string, unknown>;
    if (current.facts && typeof current.facts === "object") {
      existingFacts = current.facts as Record<string, Record<string, unknown>>;
    }
  } catch {
    // no prior file — start clean
  }

  const normalizedFacts: Record<string, Record<string, unknown>> = {
    ...existingFacts,
  };
  const confirmedOn = new Date().toISOString().slice(0, 10);
  for (const [key, entry] of Object.entries(factsIn)) {
    if (!SONG_FACT_KEYS.has(key)) {
      continue;
    }
    const value =
      entry && typeof entry === "object"
        ? (entry as Record<string, unknown>).value
        : entry;
    if (value === undefined || value === null || value === "") {
      continue;
    }
    normalizedFacts[key] = {
      value,
      provenance: "human-confirmed",
      confirmed_on: confirmedOn,
    };
  }

  return {
    schema_version: "1.1",
    song_name: String(record.song_name || song || ""),
    facts: normalizedFacts,
  };
}

export async function handleSongFacts(
  song: string,
  request: IncomingMessage,
  response: ServerResponse,
): Promise<void> {
  try {
    const payload = await normalizeSongFactsPayload(await readJsonBody(request), song);
    await writeJsonFile(songFactsFilePath(song), payload);
    response.statusCode = 200;
    response.setHeader("Content-Type", "application/json; charset=utf-8");
    response.end(JSON.stringify(payload));
  } catch (error) {
    response.statusCode = 400;
    response.setHeader("Content-Type", "text/plain; charset=utf-8");
    response.end(
      error instanceof Error ? error.message : "Unable to save song facts.",
    );
  }
}
