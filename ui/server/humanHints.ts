// humanHints.ts — `PUT /api/human-hints/<song>`, writing
// reference/human/human_hints.json. Ported byte-for-byte (in behaviour) from
// the previous app's vite.config.js, plan item 2. Split out of vite.config.ts
// (v3.9 item 7) with no behaviour change.

import type { IncomingMessage, ServerResponse } from "node:http";

import { readJsonBody, referenceHumanFilePath, writeJsonFile } from "./shared";

export type NormalizedHint = {
  id: string;
  title: string;
  start_time: number;
  end_time: number;
  summary: string;
  lighting_hint: string;
  captured_from?: string;
  type?: "hint" | "review" | "vocal";
};

export function normalizeHumanHintPayload(payload: unknown): {
  song_name: string;
  human_hints: NormalizedHint[];
} {
  if (!payload || typeof payload !== "object") {
    throw new Error("Human hints payload must be a JSON object.");
  }
  const record = payload as Record<string, unknown>;
  const humanHints = Array.isArray(record.human_hints) ? record.human_hints : null;
  if (!humanHints) {
    throw new Error("Human hints payload must include a human_hints array.");
  }

  return {
    song_name: String(record.song_name || ""),
    human_hints: humanHints.map((hint: unknown, index: number) => {
      const h = (hint && typeof hint === "object" ? hint : {}) as Record<
        string,
        unknown
      >;
      const capturedFrom =
        typeof h.captured_from === "string" ? h.captured_from.trim() : "";
      const hintType =
        h.type === "hint" || h.type === "review" || h.type === "vocal"
          ? h.type
          : undefined;
      return {
        id: String(h.id ?? `human-hint-${index + 1}`),
        title: String(h.title ?? h.label ?? `Hint ${index + 1}`),
        start_time: Number(h.start_time ?? h.start_s ?? h.start ?? 0),
        end_time: Number(h.end_time ?? h.end_s ?? h.end ?? 0),
        summary: typeof h.summary === "string" ? h.summary : "",
        lighting_hint: typeof h.lighting_hint === "string" ? h.lighting_hint : "",
        // Informative note (plan v1.5 D11) — pass through only when non-empty.
        ...(capturedFrom ? { captured_from: capturedFrom } : {}),
        // Keep explicit non-default types (e.g. "review", "vocal") on save;
        // omit "hint" for canonical parity with the editor payload.
        ...(hintType && hintType !== "hint" ? { type: hintType } : {}),
      };
    }),
  };
}

export function humanHintsFilePath(song: unknown): string {
  return referenceHumanFilePath(song, "human_hints.json");
}

export async function handleHumanHints(
  song: string,
  request: IncomingMessage,
  response: ServerResponse,
): Promise<void> {
  try {
    const payload = normalizeHumanHintPayload(await readJsonBody(request));
    await writeJsonFile(humanHintsFilePath(song), payload);
    response.statusCode = 200;
    response.setHeader("Content-Type", "application/json; charset=utf-8");
    response.end(JSON.stringify(payload));
  } catch (error) {
    response.statusCode = 400;
    response.setHeader("Content-Type", "text/plain; charset=utf-8");
    response.end(
      error instanceof Error ? error.message : "Unable to save human hints.",
    );
  }
}
