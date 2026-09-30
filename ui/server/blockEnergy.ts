// blockEnergy.ts — `PUT /api/block-energy/<song>`, writing
// reference/human/block_energy.json. Split out of vite.config.ts (v3.9 item
// 7) with no behaviour change.

import type { IncomingMessage, ServerResponse } from "node:http";

import { readJsonBody, referenceHumanFilePath, writeJsonFile } from "./shared";

// v3.4 item 4 — block_energy.json is written ONLY by an explicit human Save in
// the Human Hints events panel (the same rule human hints / song facts follow);
// the analyzer never writes `reference/`. One producer (the operator), so there
// is no `field_sources` / `source` attribution here. Nothing in `src/` or
// `mcp/` reads it. Production Nginx has no handler — the rating UI is dev-only,
// exactly like the hint editor.
export function blockEnergyFilePath(song: unknown): string {
  return referenceHumanFilePath(song, "block_energy.json");
}

// Each axis, when present, is an integer 1-5 (D4.2); a missing axis is omitted,
// never defaulted. An out-of-range or non-integer axis is rejected (400).
function normalizeBlockEnergyAxis(
  value: unknown,
  axis: string,
  hintId: string,
): number | undefined {
  if (value === undefined || value === null) return undefined;
  if (
    typeof value !== "number" ||
    !Number.isInteger(value) ||
    value < 1 ||
    value > 5
  ) {
    throw new Error(`Block "${hintId}" ${axis} must be an integer 1-5.`);
  }
  return value;
}

export function normalizeBlockEnergyPayload(payload: unknown): {
  schema_version: string;
  song_name: string;
  ratings: Array<{ hint_id: string; energy?: number; tension?: number }>;
} {
  if (!payload || typeof payload !== "object") {
    throw new Error("Block energy payload must be a JSON object.");
  }
  const record = payload as Record<string, unknown>;
  const ratingsIn = Array.isArray(record.ratings) ? record.ratings : null;
  if (!ratingsIn) {
    throw new Error("Block energy payload must include a ratings array.");
  }
  const ratings: Array<{ hint_id: string; energy?: number; tension?: number }> =
    [];
  for (const entry of ratingsIn) {
    const e = (entry && typeof entry === "object" ? entry : {}) as Record<
      string,
      unknown
    >;
    const hintId = String(e.hint_id ?? "").trim();
    if (!hintId) {
      throw new Error("Each block-energy rating must include a hint_id.");
    }
    const energy = normalizeBlockEnergyAxis(e.energy, "energy", hintId);
    const tension = normalizeBlockEnergyAxis(e.tension, "tension", hintId);
    if (energy === undefined && tension === undefined) continue;
    ratings.push({
      hint_id: hintId,
      ...(energy !== undefined ? { energy } : {}),
      ...(tension !== undefined ? { tension } : {}),
    });
  }
  return {
    schema_version: "1.0",
    song_name: String(record.song_name || ""),
    ratings,
  };
}

export async function handleBlockEnergy(
  song: string,
  request: IncomingMessage,
  response: ServerResponse,
): Promise<void> {
  try {
    const payload = normalizeBlockEnergyPayload(await readJsonBody(request));
    await writeJsonFile(blockEnergyFilePath(song), payload);
    response.statusCode = 200;
    response.setHeader("Content-Type", "application/json; charset=utf-8");
    response.end(JSON.stringify(payload));
  } catch (error) {
    response.statusCode = 400;
    response.setHeader("Content-Type", "text/plain; charset=utf-8");
    response.end(
      error instanceof Error ? error.message : "Unable to save block energy.",
    );
  }
}
