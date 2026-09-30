// dataMount.ts — the `/data` static mount (byte-for-byte port of the previous
// app's vite.config.js, plan item 2): directory listing, content-type
// sniffing and range-request support. Split out of vite.config.ts (v3.9 item
// 7) with no behaviour change.

import fs from "node:fs";
import fsp from "node:fs/promises";
import path from "node:path";
import type { IncomingMessage, ServerResponse } from "node:http";

import { dataRoot } from "./shared";

export function contentTypeFor(filePath: string): string {
  const extension = path.extname(filePath).toLowerCase();
  switch (extension) {
    case ".json":
      return "application/json; charset=utf-8";
    case ".mp3":
      return "audio/mpeg";
    case ".wav":
      return "audio/wav";
    case ".html":
      return "text/html; charset=utf-8";
    case ".css":
      return "text/css; charset=utf-8";
    case ".js":
      return "text/javascript; charset=utf-8";
    default:
      return "application/octet-stream";
  }
}

export function normalizeDataPath(urlPath: string): string {
  const relativePath = decodeURIComponent(urlPath.replace(/^\/data\/?/, ""));
  return path.join(dataRoot, relativePath);
}

export function renderDirectoryListing(urlPath: string, entries: fs.Dirent[]): string {
  const normalizedUrl = urlPath.endsWith("/") ? urlPath : `${urlPath}/`;
  const parentPath =
    normalizedUrl === "/data/" ? null : normalizedUrl.replace(/[^/]+\/$/, "");
  const items: string[] = [];
  if (parentPath) {
    items.push(`<li><a href="../">../</a></li>`);
  }
  for (const entry of entries.sort((left, right) =>
    left.name.localeCompare(right.name),
  )) {
    const suffix = entry.isDirectory() ? "/" : "";
    items.push(
      `<li><a href="${encodeURIComponent(entry.name)}${suffix}">${entry.name}${suffix}</a></li>`,
    );
  }
  return `<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>Index of ${normalizedUrl}</title>
  </head>
  <body>
    <h1>Index of ${normalizedUrl}</h1>
    <ul>
      ${items.join("\n")}
    </ul>
  </body>
</html>`;
}

export function parseByteRange(
  rangeHeader: string | undefined,
  fileSize: number,
): { start: number; end: number } | null {
  if (!rangeHeader || !rangeHeader.startsWith("bytes=")) {
    return null;
  }

  const [rangeSpec] = rangeHeader.replace("bytes=", "").split(",");
  const [startText, endText] = (rangeSpec ?? "").split("-");
  const hasStart = startText !== undefined && startText !== "";
  const hasEnd = endText !== undefined && endText !== "";

  if (!hasStart && !hasEnd) {
    return null;
  }

  let start = hasStart ? Number.parseInt(startText as string, 10) : NaN;
  let end = hasEnd ? Number.parseInt(endText as string, 10) : NaN;

  if (!hasStart) {
    const suffixLength = Number.isNaN(end) ? 0 : end;
    if (suffixLength <= 0) {
      return null;
    }
    start = Math.max(fileSize - suffixLength, 0);
    end = fileSize - 1;
  } else {
    if (Number.isNaN(start) || start < 0 || start >= fileSize) {
      return null;
    }
    if (Number.isNaN(end) || end >= fileSize) {
      end = fileSize - 1;
    }
  }

  if (Number.isNaN(start) || Number.isNaN(end) || start > end) {
    return null;
  }

  return { start, end };
}

function pipeFile(
  response: ServerResponse,
  filePath: string,
  start: number,
  end: number,
): Promise<void> {
  return new Promise((resolve, reject) => {
    const stream = fs.createReadStream(filePath, { start, end });
    stream.on("error", reject);
    stream.on("end", () => resolve());
    stream.pipe(response);
  });
}

/** Serves `GET`/`HEAD` under `/data/**`: directory listing or ranged file. */
export async function handleDataMount(
  request: IncomingMessage,
  response: ServerResponse,
  pathname: string,
): Promise<void> {
  try {
    const filePath = normalizeDataPath(pathname);
    const stats = await fsp.stat(filePath);
    if (stats.isDirectory()) {
      const entries = await fsp.readdir(filePath, { withFileTypes: true });
      response.statusCode = 200;
      response.setHeader("Content-Type", "text/html; charset=utf-8");
      if (request.method === "HEAD") {
        response.end();
        return;
      }
      response.end(renderDirectoryListing(pathname, entries));
      return;
    }

    const contentType = contentTypeFor(filePath);
    const range = parseByteRange(request.headers.range, stats.size);
    response.setHeader("Accept-Ranges", "bytes");
    response.setHeader("Content-Type", contentType);

    if (range) {
      const { start, end } = range;
      response.statusCode = 206;
      response.setHeader("Content-Range", `bytes ${start}-${end}/${stats.size}`);
      response.setHeader("Content-Length", String(end - start + 1));
      if (request.method === "HEAD") {
        response.end();
        return;
      }
      await pipeFile(response, filePath, start, end);
      return;
    }

    response.statusCode = 200;
    response.setHeader("Content-Length", String(stats.size));
    if (request.method === "HEAD") {
      response.end();
      return;
    }
    await pipeFile(response, filePath, 0, stats.size - 1);
  } catch {
    response.statusCode = 404;
    response.setHeader("Content-Type", "text/plain; charset=utf-8");
    response.end(`Not found: ${pathname}`);
  }
}
