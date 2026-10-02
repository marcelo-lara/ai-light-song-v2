// proposalDecision.ts — `PUT /api/proposal-decision/<song>`, flipping one
// `reference/proposals/pending.json` entry's status by id and (on approve)
// writing the corresponding reference/human/*.json file itself, inside
// `withSongLock` (v3.9 item 6). Split out of vite.config.ts (v3.9 item 7)
// with no behaviour change.

import fsp from "node:fs/promises";
import path from "node:path";
import type { IncomingMessage, ServerResponse } from "node:http";

import { analysisRoot, readJsonBody } from "./shared";
import {
  buildApprovedHintEntry,
  hintAlreadyCaptured,
  withSongLock,
} from "./proposalDecisionMerge";
import {
  humanHintsFilePath,
  normalizeHumanHintPayload,
  type NormalizedHint,
} from "./humanHints";

// v3.7 item 11 — reference/proposals/pending.json is written by TWO
// producers: mcp/proposals.py appends new entries (v3.7 item 10, over stdio,
// never through this dev server), and the handler below flips one existing
// entry's `status` by `id`. Nothing here ever appends a NEW proposal — only
// mcp/server.py's tools do that.
// Mirrors `referenceHumanFilePath`'s escape guard exactly, but against
// `reference/proposals/` instead of `reference/human/` — the two producers
// above never write into the operator's own directory.
function pendingProposalsFilePath(song: unknown): string {
  const safeSong = path.basename(String(song || "").trim());
  if (!safeSong) {
    throw new Error("Song name is required.");
  }
  const songDir = path.join(analysisRoot, safeSong);
  const filePath = path.join(songDir, "reference", "proposals", "pending.json");
  const relativePath = path.relative(songDir, filePath);
  if (relativePath.startsWith("..") || path.isAbsolute(relativePath)) {
    throw new Error("Song path is outside the reference data root.");
  }
  return filePath;
}

interface PendingProposalRecord {
  id: string;
  type?: "hint";
  status: "pending" | "approved" | "rejected";
  created_at: string;
  rejection_reason: string | null;
  evidence: string;
  hint?: { start: number; end: number; title: string; summary?: string };
  [key: string]: unknown;
}

interface PendingProposalsFile {
  schema_version: string;
  song_name: string;
  proposals: PendingProposalRecord[];
}

async function readPendingProposals(song: string): Promise<PendingProposalsFile> {
  const filePath = pendingProposalsFilePath(song);
  try {
    const raw = await fsp.readFile(filePath, "utf-8");
    return JSON.parse(raw) as PendingProposalsFile;
  } catch (error) {
    if ((error as NodeJS.ErrnoException)?.code === "ENOENT") {
      throw new Error(`No proposals queued for "${song}" yet.`);
    }
    throw error;
  }
}

async function writePendingProposals(
  song: string,
  file: PendingProposalsFile,
): Promise<void> {
  const filePath = pendingProposalsFilePath(song);
  await fsp.mkdir(path.dirname(filePath), { recursive: true });
  await fsp.writeFile(filePath, JSON.stringify(file, null, 2) + "\n", "utf-8");
}

// `PUT /api/proposal-decision/<song>` body: `{id, status, rejection_reason?}`.
// The handler below does the operator's own reference/human/*.json write
// ITSELF on an approve (v3.9 item 6 — see the comment near this module's
// top), from its own fresh read, and only flips the queue entry's status
// once that write has succeeded; a reject never touches reference/human/. A
// reject requires a non-empty reason; only a currently "pending" entry may
// be decided, so a decided entry can never be silently re-queued or
// overwritten.
export function normalizeProposalDecisionPayload(payload: unknown): {
  id: string;
  status: "approved" | "rejected";
  rejection_reason: string | null;
  /** Operator-corrected start/end for a hint approve — only ever set when
   *  `status === "approved"`; a reject carrying this is a 400 (see below). */
  approved_times: { start: number; end: number } | null;
} {
  if (!payload || typeof payload !== "object") {
    throw new Error("Proposal decision payload must be a JSON object.");
  }
  const record = payload as Record<string, unknown>;
  const id = String(record.id ?? "").trim();
  if (!id) {
    throw new Error("Proposal decision payload must include an id.");
  }
  const status = record.status;
  if (status !== "approved" && status !== "rejected") {
    throw new Error('Proposal decision "status" must be "approved" or "rejected".');
  }
  const rejection_reason =
    typeof record.rejection_reason === "string" ? record.rejection_reason.trim() : "";
  if (status === "rejected" && !rejection_reason) {
    throw new Error('Rejecting a proposal requires a non-empty "rejection_reason".');
  }

  let approved_times: { start: number; end: number } | null = null;
  if (record.approved_times !== undefined) {
    if (status !== "approved") {
      throw new Error('"approved_times" is only valid when approving a proposal.');
    }
    const t =
      record.approved_times && typeof record.approved_times === "object"
        ? (record.approved_times as Record<string, unknown>)
        : null;
    const start = t?.start;
    const end = t?.end;
    if (
      typeof start !== "number" ||
      typeof end !== "number" ||
      !Number.isFinite(start) ||
      !Number.isFinite(end) ||
      start < 0 ||
      end <= start
    ) {
      throw new Error(
        '"approved_times" requires finite numbers with 0 <= start < end.',
      );
    }
    approved_times = { start, end };
  }

  return {
    id,
    status,
    rejection_reason: status === "rejected" ? rejection_reason : null,
    approved_times,
  };
}

export async function handleProposalDecision(
  song: string,
  request: IncomingMessage,
  response: ServerResponse,
): Promise<void> {
  try {
    const decision = normalizeProposalDecisionPayload(await readJsonBody(request));
    const file = await withSongLock(song, async () => {
      const file = await readPendingProposals(song);
      const index = file.proposals.findIndex((p) => p.id === decision.id);
      if (index === -1) {
        throw new Error(`No pending proposal with id "${decision.id}".`);
      }
      const current = file.proposals[index]!;
      if (current.status !== "pending") {
        throw new Error(
          `Proposal "${decision.id}" is already ${current.status} — it cannot be re-decided.`,
        );
      }
      if (decision.approved_times && current.type !== "hint") {
        throw new Error(
          `Proposal "${decision.id}" is not a hint proposal — "approved_times" is only valid for type "hint".`,
        );
      }

      // The human-file write happens FIRST, from a read taken this instant
      // (never a value handed up by the browser), and inside the same lock
      // as the status flip below — so the two can never diverge, and a
      // second concurrent approve for this song can never see a stale
      // snapshot of either file.
      if (decision.status === "approved") {
        if (current.type === "hint") {
          const hintsPath = humanHintsFilePath(song);
          let hintsFile: { song_name: string; human_hints: NormalizedHint[] };
          try {
            hintsFile = normalizeHumanHintPayload(
              JSON.parse(await fsp.readFile(hintsPath, "utf-8")),
            );
          } catch (error) {
            if ((error as NodeJS.ErrnoException)?.code === "ENOENT") {
              hintsFile = { song_name: song, human_hints: [] };
            } else {
              throw error;
            }
          }
          // Idempotent: a retry after a partial failure (hint written,
          // status flip failed below) must not double-append.
          if (!hintAlreadyCaptured(hintsFile.human_hints, current.id)) {
            const entry = buildApprovedHintEntry(
              current,
              hintsFile.human_hints,
              decision.approved_times,
            );
            hintsFile.human_hints = [...hintsFile.human_hints, entry].sort(
              (a, b) => a.start_time - b.start_time,
            );
            await fsp.mkdir(path.dirname(hintsPath), { recursive: true });
            await fsp.writeFile(
              hintsPath,
              JSON.stringify(hintsFile, null, 2) + "\n",
              "utf-8",
            );
          }
        } else {
          throw new Error(`Proposal "${decision.id}" has an unknown type.`);
        }
      }

      file.proposals[index] = {
        ...current,
        status: decision.status,
        rejection_reason: decision.rejection_reason,
        // The operator's corrected start/end, kept beside the original
        // `hint` — never overwrites it. Absent on an unedited approve
        // (approved as proposed) or a reject.
        ...(decision.approved_times ? { approved_hint: decision.approved_times } : {}),
      };
      await writePendingProposals(song, file);
      return file;
    });
    response.statusCode = 200;
    response.setHeader("Content-Type", "application/json; charset=utf-8");
    response.end(JSON.stringify(file));
  } catch (error) {
    response.statusCode = 400;
    response.setHeader("Content-Type", "text/plain; charset=utf-8");
    response.end(
      error instanceof Error ? error.message : "Unable to save the proposal decision.",
    );
  }
}
