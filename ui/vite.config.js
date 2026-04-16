import fs from "node:fs/promises";
import path from "node:path";

import { defineConfig } from "vite";
import preact from "@preact/preset-vite";

const dataRoot = "/data";

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

function dataMountPlugin() {
  return {
    name: "data-mount-plugin",
    configureServer(server) {
      server.middlewares.use(async (request, response, next) => {
        const requestUrl = request.url ? new URL(request.url, "http://localhost") : null;
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