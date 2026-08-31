/// <reference types="vitest/config" />
import fs from "node:fs";
import fsp from "node:fs/promises";
import path from "node:path";
import type { IncomingMessage, ServerResponse } from "node:http";

import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";

// Target: Chrome 151 only (the operator's browser). No cross-browser fallbacks,
// polyfills or autoprefixer — build to esnext and use modern web APIs freely.
//
// The dev-server `/data` static mount + directory listing and the
// `PUT /api/human-hints/<song>` handler below are ported byte-for-byte (in
// behaviour) from ui.old/vite.config.js, plan item 2. The `PUT
// /api/song-facts/<song>` handler is added by plan item 7.

const dataRoot = "/data";
const analysisRoot = path.join(dataRoot, "analysis");

function contentTypeFor(filePath: string): string {
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

function normalizeDataPath(urlPath: string): string {
  const relativePath = decodeURIComponent(urlPath.replace(/^\/data\/?/, ""));
  return path.join(dataRoot, relativePath);
}

function renderDirectoryListing(urlPath: string, entries: fs.Dirent[]): string {
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

async function readJsonBody(request: IncomingMessage): Promise<unknown> {
  const chunks: Buffer[] = [];
  for await (const chunk of request) {
    chunks.push(chunk as Buffer);
  }
  const raw = Buffer.concat(chunks).toString("utf-8");
  return raw ? JSON.parse(raw) : {};
}

type NormalizedHint = {
  id: string;
  title: string;
  start_time: number;
  end_time: number;
  summary: string;
  lighting_hint: string;
};

function normalizeHumanHintPayload(payload: unknown): {
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
      return {
        id: String(h.id ?? `human-hint-${index + 1}`),
        title: String(h.title ?? h.label ?? `Hint ${index + 1}`),
        start_time: Number(h.start_time ?? h.start_s ?? h.start ?? 0),
        end_time: Number(h.end_time ?? h.end_s ?? h.end ?? 0),
        summary: typeof h.summary === "string" ? h.summary : "",
        lighting_hint: typeof h.lighting_hint === "string" ? h.lighting_hint : "",
      };
    }),
  };
}

// Path-escape guard: the resolved file must stay inside <analysisRoot>/<song>/.
function referenceHumanFilePath(song: unknown, fileName: string): string {
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

function humanHintsFilePath(song: unknown): string {
  return referenceHumanFilePath(song, "human_hints.json");
}

function parseByteRange(
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

function dataMountPlugin(): Plugin {
  return {
    name: "data-mount-plugin",
    configureServer(server) {
      server.middlewares.use(async (request, response, next) => {
        const requestUrl = request.url
          ? new URL(request.url, "http://localhost")
          : null;

        if (
          requestUrl &&
          request.method === "PUT" &&
          requestUrl.pathname.startsWith("/api/human-hints/")
        ) {
          try {
            const song = decodeURIComponent(
              requestUrl.pathname.replace("/api/human-hints/", ""),
            );
            const payload = normalizeHumanHintPayload(
              await readJsonBody(request),
            );
            const filePath = humanHintsFilePath(song);
            await fsp.mkdir(path.dirname(filePath), { recursive: true });
            await fsp.writeFile(
              filePath,
              JSON.stringify(payload, null, 2) + "\n",
              "utf-8",
            );
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
          return;
        }

        if (!requestUrl || !requestUrl.pathname.startsWith("/data")) {
          next();
          return;
        }

        try {
          const filePath = normalizeDataPath(requestUrl.pathname);
          const stats = await fsp.stat(filePath);
          if (stats.isDirectory()) {
            const entries = await fsp.readdir(filePath, { withFileTypes: true });
            response.statusCode = 200;
            response.setHeader("Content-Type", "text/html; charset=utf-8");
            if (request.method === "HEAD") {
              response.end();
              return;
            }
            response.end(renderDirectoryListing(requestUrl.pathname, entries));
            return;
          }

          const contentType = contentTypeFor(filePath);
          const range = parseByteRange(request.headers.range, stats.size);
          response.setHeader("Accept-Ranges", "bytes");
          response.setHeader("Content-Type", contentType);

          if (range) {
            const { start, end } = range;
            response.statusCode = 206;
            response.setHeader(
              "Content-Range",
              `bytes ${start}-${end}/${stats.size}`,
            );
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
          response.end(`Not found: ${requestUrl.pathname}`);
        }
      });
    },
  };
}

export default defineConfig({
  plugins: [react(), dataMountPlugin()],
  build: {
    target: "esnext",
  },
  server: {
    host: "0.0.0.0",
    port: 8080,
    strictPort: true,
    watch: {
      usePolling: true,
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["src/test/setup.ts"],
    css: true,
  },
});
