import { artifactDefinitions } from "../lib/config.js";
import { fetchDirectoryFiles, fetchDirectoryListing, fetchJson } from "../lib/data.js";
import { encodePath } from "../lib/utils.js";

export function humanHintsPath(song) {
  return encodePath(["data", "analysis", song, "reference", "human", "human_hints.json"]);
}

export function songFactsPath(song) {
  return encodePath(["data", "analysis", song, "reference", "human", "song_facts.json"]);
}

export function reviewQueuePath(song) {
  return encodePath(["data", "analysis", song, "artifacts", "validation", "review_queue.json"]);
}

export async function discoverAvailableSongs() {
  const [availableSongs, availableAudioSongs] = await Promise.all([
    fetchDirectoryListing(["data", "analysis"]),
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

// v1.1 Story 5.2 — answers to review_queue.json questions are saved into
// song_facts.json on an explicit human save only.
export async function saveSongFactsFile(song, payload) {
  const response = await fetch(`/api/song-facts/${encodeURIComponent(song)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Failed to save ${songFactsPath(song)}.`);
  }

  return response.json();
}