import { encodePath } from "../utils.js";

function decodeSegment(value) {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

function extractAutoIndexEntries(html) {
  const anchorPattern = /<a\s+href="([^"]+)"[^>]*>([^<]*)<\/a>/gi;
  const entries = [];
  for (const match of html.matchAll(anchorPattern)) {
    const href = String(match[1] || "").trim();
    if (!href || href === "../") {
      continue;
    }

    const cleanHref = href.split("?")[0].split("#")[0];
    if (!cleanHref) {
      continue;
    }

    const segments = cleanHref.split("/").filter(Boolean).map(decodeSegment);
    const rawName = segments.at(-1) || decodeSegment(cleanHref.replace(/\/+$/, ""));
    const name = rawName.trim();
    if (!name || name === "." || name === "..") {
      continue;
    }

    entries.push({
      name,
      isDirectory: cleanHref.endsWith("/"),
    });
  }
  return entries;
}

async function fetchText(pathParts) {
  const response = await fetch(encodePath(pathParts), { cache: "no-store" });
  if (!response.ok) {
    const detail = await response.text().catch(() => "");
    throw new Error(detail || `Failed to load ${encodePath(pathParts)} (${response.status}).`);
  }
  return response.text();
}

export async function fetchJson(pathParts) {
  const path = encodePath(pathParts);
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) {
    const detail = await response.text().catch(() => "");
    throw new Error(detail || `Failed to load ${path} (${response.status}).`);
  }

  try {
    return await response.json();
  } catch {
    throw new Error(`Invalid JSON in ${path}.`);
  }
}

export async function fetchDirectoryListing(pathParts) {
  const html = await fetchText(pathParts);
  const unique = new Set();
  for (const entry of extractAutoIndexEntries(html)) {
    if (entry.isDirectory) {
      unique.add(entry.name);
    }
  }
  return [...unique].sort((left, right) => left.localeCompare(right));
}

export async function fetchDirectoryFiles(pathParts, extensions = []) {
  const html = await fetchText(pathParts);
  const normalizedExtensions = extensions.map((value) => String(value).toLowerCase());

  const unique = new Set();
  for (const entry of extractAutoIndexEntries(html)) {
    if (entry.isDirectory) {
      continue;
    }
    const lowerName = entry.name.toLowerCase();
    const matchingExtension = normalizedExtensions.find((extension) => lowerName.endsWith(extension));
    if (!matchingExtension) {
      continue;
    }
    unique.add(entry.name.slice(0, -matchingExtension.length));
  }

  return [...unique].sort((left, right) => left.localeCompare(right));
}
