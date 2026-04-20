import fs from "node:fs/promises";
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
            await fs.mkdir(path.dirname(filePath), { recursive: true });
            await fs.writeFile(filePath, JSON.stringify(payload, null, 2) + "\n", "utf-8");
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
          const stats = await fs.stat(filePath);
          if (stats.isDirectory()) {
            const entries = await fs.readdir(filePath, { withFileTypes: true });
            response.statusCode = 200;
            response.setHeader("Content-Type", "text/html; charset=utf-8");
            response.end(renderDirectoryListing(requestUrl.pathname, entries));
            return;
          }

          const fileContents = await fs.readFile(filePath);
          response.statusCode = 200;
          response.setHeader("Content-Type", contentTypeFor(filePath));
          response.end(fileContents);
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