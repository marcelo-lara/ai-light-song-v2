import fs from "node:fs";
import fsp from "node:fs/promises";
import path from "node:path";

import { defineConfig } from "vite";
import preact from "@preact/preset-vite";

const dataRoot = "/data";
const referenceRoot = path.join(dataRoot, "reference");

function contentTypeFor(filePath) {
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

function normalizeDataPath(urlPath) {
  const relativePath = decodeURIComponent(urlPath.replace(/^\/data\/?/, ""));
  return path.join(dataRoot, relativePath);
}

function renderDirectoryListing(urlPath, entries) {
  const normalizedUrl = urlPath.endsWith("/") ? urlPath : `${urlPath}/`;
  const parentPath = normalizedUrl === "/data/"
    ? null
    : normalizedUrl.replace(/[^/]+\/$/, "");
  const items = [];
  if (parentPath) {
    items.push(`<li><a href="../">../</a></li>`);
  }
  for (const entry of entries.sort((left, right) => left.name.localeCompare(right.name))) {
    const suffix = entry.isDirectory() ? "/" : "";
    items.push(`<li><a href="${encodeURIComponent(entry.name)}${suffix}">${entry.name}${suffix}</a></li>`);
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

async function readJsonBody(request) {
  const chunks = [];
  for await (const chunk of request) {
    chunks.push(chunk);
  }
  const raw = Buffer.concat(chunks).toString("utf-8");
  return raw ? JSON.parse(raw) : {};
}

function normalizeHumanHintPayload(payload) {
  if (!payload || typeof payload !== "object") {
    throw new Error("Human hints payload must be a JSON object.");
  }

  const humanHints = Array.isArray(payload.human_hints) ? payload.human_hints : null;
  if (!humanHints) {
    throw new Error("Human hints payload must include a human_hints array.");
  }

  return {
    song_name: String(payload.song_name || ""),
    human_hints: humanHints.map((hint, index) => ({
      id: String(hint?.id ?? `human-hint-${index + 1}`),
      title: String(hint?.title ?? hint?.label ?? `Hint ${index + 1}`),
      start_time: Number(hint?.start_time ?? hint?.start_s ?? hint?.start ?? 0),
      end_time: Number(hint?.end_time ?? hint?.end_s ?? hint?.end ?? 0),
      summary: typeof hint?.summary === "string" ? hint.summary : "",
      lighting_hint: typeof hint?.lighting_hint === "string" ? hint.lighting_hint : "",
    })),
  };
}

function humanHintsFilePath(song) {
  const safeSong = path.basename(String(song || "").trim());
  if (!safeSong) {
    throw new Error("Song name is required.");
  }
  const filePath = path.join(referenceRoot, safeSong, "human", "human_hints.json");
  const relativePath = path.relative(referenceRoot, filePath);
  if (relativePath.startsWith("..") || path.isAbsolute(relativePath)) {
    throw new Error("Song path is outside the reference data root.");
  }
  return filePath;
}

function parseByteRange(rangeHeader, fileSize) {
  if (!rangeHeader || !rangeHeader.startsWith("bytes=")) {
    return null;
  }

  const [rangeSpec] = rangeHeader.replace("bytes=", "").split(",");
  const [startText, endText] = rangeSpec.split("-");
  const hasStart = startText !== undefined && startText !== "";
  const hasEnd = endText !== undefined && endText !== "";

  if (!hasStart && !hasEnd) {
    return null;
  }

  let start = hasStart ? Number.parseInt(startText, 10) : NaN;
  let end = hasEnd ? Number.parseInt(endText, 10) : NaN;

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

function pipeFile(response, filePath, start, end) {
  return new Promise((resolve, reject) => {
    const stream = fs.createReadStream(filePath, { start, end });
    stream.on("error", reject);
    stream.on("end", resolve);
    stream.pipe(response);
  });
}

function dataMountPlugin() {
  return {
    name: "data-mount-plugin",
    configureServer(server) {
      server.middlewares.use(async (request, response, next) => {
        const requestUrl = request.url ? new URL(request.url, "http://localhost") : null;
        if (requestUrl && request.method === "PUT" && requestUrl.pathname.startsWith("/api/human-hints/")) {
          try {
            const song = decodeURIComponent(requestUrl.pathname.replace("/api/human-hints/", ""));
            const payload = normalizeHumanHintPayload(await readJsonBody(request));
            const filePath = humanHintsFilePath(song);
            await fsp.mkdir(path.dirname(filePath), { recursive: true });
            await fsp.writeFile(filePath, JSON.stringify(payload, null, 2) + "\n", "utf-8");
            response.statusCode = 200;
            response.setHeader("Content-Type", "application/json; charset=utf-8");
            response.end(JSON.stringify(payload));
          } catch (error) {
            response.statusCode = 400;
            response.setHeader("Content-Type", "text/plain; charset=utf-8");
            response.end(error instanceof Error ? error.message : "Unable to save human hints.");
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
        } catch (error) {
          response.statusCode = 404;
          response.setHeader("Content-Type", "text/plain; charset=utf-8");
          response.end(`Not found: ${requestUrl.pathname}`);
        }
      });
    },
  };
}

export default defineConfig({
  plugins: [preact(), dataMountPlugin()],
  server: {
    allowedHosts: ["s2.local"],
    host: "0.0.0.0",
    port: 8080,
    strictPort: true,
    watch: {
      usePolling: true,
    },
  },
});