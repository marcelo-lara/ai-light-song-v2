// Client for `PUT /api/human-hints/<song>`.
//
// The validation here is the exact set ui.old's hint editor enforced
// (ui.old/src/app/useHumanHintsEditor.js `buildSavePayload`): id + title
// required, start/end must be finite numbers, end >= start. Times may arrive as
// strings from text inputs; they are coerced with `Number(...)`.

import { artifactPaths } from "./paths";
import type { HumanHint, HumanHintsFile } from "./types";

export interface HintDraft {
  id: string;
  title: string;
  start_time: string | number;
  end_time: string | number;
  summary?: string;
  lighting_hint?: string;
}

/**
 * Validate + normalise draft hints into the on-disk payload shape.
 * Throws `Error` with the same messages the old editor showed.
 */
export function buildHumanHintsPayload(
  songName: string,
  drafts: HintDraft[],
): HumanHintsFile {
  const human_hints: HumanHint[] = drafts.map((hint) => {
    const startTime = Number(hint.start_time);
    const endTime = Number(hint.end_time);
    if (!hint.id.trim()) {
      throw new Error("Each human hint must include an id before saving.");
    }
    if (!hint.title.trim()) {
      throw new Error("Each human hint must include a title before saving.");
    }
    if (!Number.isFinite(startTime) || !Number.isFinite(endTime)) {
      throw new Error("Human hint start and end times must be valid numbers.");
    }
    if (endTime < startTime) {
      throw new Error(
        "Human hint end time must be greater than or equal to start time.",
      );
    }
    return {
      id: hint.id.trim(),
      title: hint.title.trim(),
      start_time: startTime,
      end_time: endTime,
      summary: (hint.summary ?? "").trim(),
      lighting_hint: (hint.lighting_hint ?? "").trim(),
    };
  });

  return { song_name: String(songName || ""), human_hints };
}

/**
 * PUT the payload. Resolves with the server-normalised file (which the UI
 * should treat as the new source of truth). Rejects with the server's error
 * text on a non-2xx response.
 */
export async function saveHumanHints(
  song: string,
  payload: HumanHintsFile,
  fetchImpl: typeof fetch = fetch,
): Promise<HumanHintsFile> {
  const response = await fetchImpl(
    `/api/human-hints/${encodeURIComponent(song)}`,
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
        `Failed to save ${artifactPaths.humanHints(song)} (${response.status}).`,
    );
  }

  return (await response.json()) as HumanHintsFile;
}
