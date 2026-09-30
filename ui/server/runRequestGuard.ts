// v3.8 item 2 — the song-name guard for `PUT /api/run-request/<song>`
// (vite.config.ts). Kept in its own module, outside vite.config.ts itself,
// so it can be unit-tested without importing `vite` (and its bundled
// esbuild) into the jsdom test environment — that import breaks esbuild's
// own Node-environment sanity check under jsdom's globals.
//
// The song name becomes a directory component directly under `artifacts/`
// (no `reference/human/` nesting to collapse it against, unlike
// `referenceHumanFilePath` in vite.config.ts), so this guard is stricter: a
// `/`, `\` or `..` anywhere in the name is rejected outright (400) rather
// than silently stripped.
export function validateRunRequestSong(song: unknown): string {
  const name = String(song ?? "").trim();
  if (!name) {
    throw new Error("Song name is required.");
  }
  if (name.includes("/") || name.includes("\\") || name.includes("..")) {
    throw new Error('Song name must not contain "/", "\\" or "..".');
  }
  return name;
}
