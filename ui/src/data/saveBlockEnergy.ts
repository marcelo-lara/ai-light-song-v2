// Client for `PUT /api/block-energy/<song>` — mirrors saveHumanHints.ts.
//
// v3.4 item 4: `reference/human/block_energy.json` rates each `human_hints.json`
// block on two independent 1-5 integer axes — `energy` and `tension` — joined
// to the hints by `hint_id` at read time. The operator is the only producer;
// nothing in `src/` or `mcp/` reads the file, and there is no
// `field_sources` / `source` attribution machinery (the
// `human-hints-file-stays-simple` rule; `ui-definition.md` "The write rule").
//
// Save cadence follows the hints pattern: an explicit panel-level Save, never
// per-click. `Cancel` / closing the panel must not write.

import { artifactPaths } from "./paths";
import type { BlockEnergyFile, BlockEnergyRating } from "./types";

export const BLOCK_ENERGY_MIN = 1;
export const BLOCK_ENERGY_MAX = 5;

/** One block's in-progress rating. `null` on an axis means "unrated". */
export interface BlockEnergyDraft {
  hint_id: string;
  energy: number | null;
  tension: number | null;
}

function validAxis(value: number): boolean {
  return (
    Number.isInteger(value) &&
    value >= BLOCK_ENERGY_MIN &&
    value <= BLOCK_ENERGY_MAX
  );
}

/**
 * Validate + normalise draft ratings into the on-disk payload shape.
 *
 * - A block with both axes `null` is unrated and dropped from `ratings`.
 * - An axis that is set must be an integer 1-5, or this throws (rejected in the
 *   client, and again in the dev-server handler).
 * - A partially-rated block (one axis set, one `null`) is kept, carrying only
 *   the axis that is set — no defaulted value (no silent fallbacks). It counts
 *   as fully rated only once both axes are present.
 */
export function buildBlockEnergyPayload(
  songName: string,
  drafts: BlockEnergyDraft[],
): BlockEnergyFile {
  const ratings: BlockEnergyRating[] = [];
  for (const draft of drafts) {
    const hintId = String(draft.hint_id || "").trim();
    if (!hintId) {
      throw new Error("Each block-energy rating must reference a hint_id.");
    }
    const { energy, tension } = draft;
    if (energy == null && tension == null) continue;
    if (energy != null && !validAxis(energy)) {
      throw new Error(`Block "${hintId}" energy must be an integer 1-5.`);
    }
    if (tension != null && !validAxis(tension)) {
      throw new Error(`Block "${hintId}" tension must be an integer 1-5.`);
    }
    ratings.push({
      hint_id: hintId,
      ...(energy != null ? { energy } : {}),
      ...(tension != null ? { tension } : {}),
    });
  }
  return {
    schema_version: "1.0",
    song_name: String(songName || ""),
    ratings,
  };
}

/**
 * PUT the payload. Resolves with the server-normalised file (the new source of
 * truth); rejects with the server's error text on a non-2xx response.
 */
export async function saveBlockEnergy(
  song: string,
  payload: BlockEnergyFile,
  fetchImpl: typeof fetch = fetch,
): Promise<BlockEnergyFile> {
  const response = await fetchImpl(
    `/api/block-energy/${encodeURIComponent(song)}`,
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
        `Failed to save ${artifactPaths.blockEnergy(song)} (${response.status}).`,
    );
  }

  return (await response.json()) as BlockEnergyFile;
}
