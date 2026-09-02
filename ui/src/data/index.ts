// Typed artifact-access layer for the debugger UI. See README.HELPER_UI.md.

export * from "./types";
export * from "./loaders";
export * from "./sparseArtifacts";
export * from "./discovery";
export { useSong } from "./useSong";
export type {
  ArtifactState,
  ArtifactStatus,
  SongArtifacts,
  UseSongResult,
} from "./useSong";
export { buildHumanHintsPayload, saveHumanHints } from "./saveHumanHints";
export type { HintDraft } from "./saveHumanHints";
export {
  buildSongFactsPayload,
  saveSongFacts,
  WHOLE_SONG_FACT_FIELDS,
} from "./saveSongFacts";
export type {
  SongFactsDraft,
  SongFactsPayload,
  WholeSongFactField,
} from "./saveSongFacts";
export { artifactPaths, listingPaths, encodePath } from "./paths";
