// shared.ts — the bits every dev-server endpoint module needs: the data
// roots, request-body reading and the reference/human/ path-escape guard.
// Split out of vite.config.ts (v3.9 item 7) with no behaviour change.

import fsp from "node:fs/promises";
import path from "node:path";
import type { IncomingMessage } from "node:http";

export const dataRoot = "/data";
export const analysisRoot = path.join(dataRoot, "analysis");

export async function readJsonBody(request: IncomingMessage): Promise<unknown> {
  const chunks: Buffer[] = [];
  for await (const chunk of request) {
    chunks.push(chunk as Buffer);
  }
  const raw = Buffer.concat(chunks).toString("utf-8");
  return raw ? JSON.parse(raw) : {};
}

// Path-escape guard: the resolved file must stay inside <analysisRoot>/<song>/.
export function referenceHumanFilePath(song: unknown, fileName: string): string {
  const safeSong = path.basename(String(song || "").trim());
  if (!safeSong) {
    throw new Error("Song name is required.");
  }
  const songDir = path.join(analysisRoot, safeSong);
  const filePath = path.join(songDir, "reference", "human", fileName);
  const relativePath = path.relative(songDir, filePath);
  if (relativePath.startsWith("..") || path.isAbsolute(relativePath)) {
    throw new Error("Song path is outside the reference data root.");
  }
  return filePath;
}

export async function writeJsonFile(filePath: string, payload: unknown): Promise<void> {
  await fsp.mkdir(path.dirname(filePath), { recursive: true });
  await fsp.writeFile(filePath, JSON.stringify(payload, null, 2) + "\n", "utf-8");
}
