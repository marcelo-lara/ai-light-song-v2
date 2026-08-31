// loadStates.ts — pure state-selection logic for the non-happy-path UI
// (plan item 10 / refinement §10).
//
// Two selectors, both pure and unit-tested (`src/app/loadStates.test.ts`):
//
//  - `selectSongListState`  — the drawer song picker: idle / loading / error /
//    empty / ready, from the discovery hook's raw fields.
//  - `selectSongLoadState`  — a selected song: whether the timeline can render
//    at all (needs `info.json` + a beat grid), and which lanes are missing
//    their backing artifact so the shell can surface a summary.

export type SongListState =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "empty" }
  | { kind: "ready"; songs: string[] };

export interface SongListInput {
  /** discovery has returned at least once (success or the songs array is set) */
  loaded: boolean;
  error: string | null;
  songs: readonly string[];
}

export function selectSongListState(input: SongListInput): SongListState {
  if (input.error) return { kind: "error", message: input.error };
  if (!input.loaded) return { kind: "loading" };
  if (input.songs.length === 0) return { kind: "empty" };
  return { kind: "ready", songs: [...input.songs] };
}

// ---------------------------------------------------------------------------

export type ArtifactLoadStatus = "idle" | "loading" | "ready" | "error";

export type SongLoadState =
  | { kind: "loading" }
  /** `info.json` failed — no clock, no coordinate grid: the timeline can't render */
  | { kind: "fatal"; message: string }
  /** timeline renders; some lanes are missing / errored their artifact */
  | { kind: "degraded"; missing: string[] }
  | { kind: "ready" };

export interface SongLoadInput {
  infoStatus: ArtifactLoadStatus;
  infoError?: string | null;
  /** beats.json produced a usable beat list */
  hasBeats: boolean;
  /** lane label → its backing-artifact load status (only the lanes that matter) */
  laneArtifactStatus: Readonly<Record<string, ArtifactLoadStatus>>;
}

export function selectSongLoadState(input: SongLoadInput): SongLoadState {
  if (input.infoStatus === "loading" || input.infoStatus === "idle") {
    return { kind: "loading" };
  }
  if (input.infoStatus === "error") {
    return {
      kind: "fatal",
      message: input.infoError || "Could not load info.json for this song.",
    };
  }
  if (!input.hasBeats) {
    return {
      kind: "fatal",
      message: "This song has no beats.json — the timeline needs a beat grid.",
    };
  }

  const missing = Object.entries(input.laneArtifactStatus)
    .filter(([, status]) => status === "error")
    .map(([label]) => label)
    .sort();

  return missing.length > 0 ? { kind: "degraded", missing } : { kind: "ready" };
}
