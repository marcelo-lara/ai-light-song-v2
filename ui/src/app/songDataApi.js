import { artifactDefinitions } from "../lib/config.js";
import { fetchDirectoryFiles, fetchDirectoryListing, fetchJson } from "../lib/data.js";
import { encodePath } from "../lib/utils.js";

export function humanHintsPath(song) {
  return encodePath(["data", "reference", song, "human", "human_hints.json"]);
}

export async function discoverAvailableSongs() {
  const [availableSongs, availableAudioSongs] = await Promise.all([
    fetchDirectoryListing(["data", "artifacts"]),
    fetchDirectoryFiles(["data", "songs"], [".mp3", ".wav", ".flac", ".m4a", ".ogg"]),
  ]);
  return { availableSongs, availableAudioSongs };
}

export async function loadArtifactRecords(song) {
  const records = await Promise.all(artifactDefinitions.map(async (definition) => {
    const parts = definition.path(song);
    const path = encodePath(parts);
    try {
      return { key: definition.key, label: definition.label, path, ok: true, data: await fetchJson(parts) };
    } catch (error) {
      return { key: definition.key, label: definition.label, path, ok: false, error: error.message, data: null };
    }
  }));
  return records.sort((left, right) => left.label.localeCompare(right.label));
}

export async function saveHumanHintsFile(song, payload) {
  const response = await fetch(`/api/human-hints/${encodeURIComponent(song)}`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Failed to save ${humanHintsPath(song)}.`);
  }

  return response.json();
}