// One loader per artifact the UI reads. Each fetches its file from the `/data`
// mount, parses it against the v1.1 contract, and returns either
// `{ ok: true, data }` or `{ ok: false, error }` — never throws.

import { ShapeError } from "./parse";
import { artifactPaths } from "./paths";
import {
  loadAllin1,
  loadCharacter,
  loadVocalTranscription,
  loadDropProposals,
  loadMoisesLyrics,
  loadVocalPhrases,
  loadReactiveBands,
  loadGrid,
} from "./sparseArtifacts";
import {
  parseBeats,
  parseDrumEvents,
  parseEnergyLayer,
  parseEventTimeline,
  parseFftBands,
  parseHarmonicLayer,
  parseHumanHints,
  parseInfo,
  parseLoudnessEnvelope,
  parseReviewQueue,
  parseSongFacts,
  parseRmsLoudness,
  parseSectionSegmentation,
  parseSectionsTopLevel,
} from "./parsers";
import type {
  Beats,
  DrumEventsFile,
  EnergyLayer,
  EventTimeline,
  FftBands,
  HarmonicLayer,
  HumanHintsFile,
  LoudnessEnvelope,
  ReviewQueue,
  RmsLoudness,
  SectionSegmentation,
  SectionsTopLevel,
  SongFactsFile,
  SongInfo,
} from "./types";

export type LoadErrorKind = "network" | "http" | "parse" | "shape";

export interface LoadError {
  kind: LoadErrorKind;
  message: string;
  path: string;
  /** HTTP status when `kind === "http"` */
  status?: number;
}

export type LoadResult<T> =
  | { ok: true; data: T }
  | { ok: false; error: LoadError };

/** Fetch a JSON document and validate it with `parse`. */
export async function loadJson<T>(
  path: string,
  parse: (raw: unknown) => T,
  fetchImpl: typeof fetch = fetch,
): Promise<LoadResult<T>> {
  let response: Response;
  try {
    response = await fetchImpl(path, { cache: "no-store" });
  } catch (error) {
    return {
      ok: false,
      error: {
        kind: "network",
        path,
        message:
          error instanceof Error ? error.message : `Failed to reach ${path}.`,
      },
    };
  }

  if (!response.ok) {
    const detail = await response.text().catch(() => "");
    return {
      ok: false,
      error: {
        kind: "http",
        path,
        status: response.status,
        message: detail.trim() || `${path} returned ${response.status}.`,
      },
    };
  }

  let raw: unknown;
  try {
    raw = await response.json();
  } catch {
    return {
      ok: false,
      error: { kind: "parse", path, message: `Invalid JSON in ${path}.` },
    };
  }

  try {
    return { ok: true, data: parse(raw) };
  } catch (error) {
    return {
      ok: false,
      error: {
        kind: "shape",
        path,
        message:
          error instanceof ShapeError || error instanceof Error
            ? error.message
            : `${path} did not match the expected shape.`,
      },
    };
  }
}

// -- per-artifact loaders --------------------------------------------------

export const loadInfo = (song: string, f?: typeof fetch) =>
  loadJson<SongInfo>(artifactPaths.info(song), parseInfo, f);

export const loadBeats = (song: string, f?: typeof fetch) =>
  loadJson<Beats>(artifactPaths.beats(song), parseBeats, f);

export const loadSectionsTopLevel = (song: string, f?: typeof fetch) =>
  loadJson<SectionsTopLevel>(
    artifactPaths.sectionsTopLevel(song),
    parseSectionsTopLevel,
    f,
  );

export const loadSectionSegmentation = (song: string, f?: typeof fetch) =>
  loadJson<SectionSegmentation>(
    artifactPaths.sectionSegmentation(song),
    parseSectionSegmentation,
    f,
  );

export const loadFftBands = (song: string, f?: typeof fetch) =>
  loadJson<FftBands>(artifactPaths.fftBands(song), parseFftBands, f);

export const loadRmsLoudness = (song: string, f?: typeof fetch) =>
  loadJson<RmsLoudness>(artifactPaths.rmsLoudness(song), parseRmsLoudness, f);

export const loadLoudnessEnvelope = (song: string, f?: typeof fetch) =>
  loadJson<LoudnessEnvelope>(
    artifactPaths.loudnessEnvelope(song),
    parseLoudnessEnvelope,
    f,
  );

export const loadHarmonicLayer = (song: string, f?: typeof fetch) =>
  loadJson<HarmonicLayer>(
    artifactPaths.harmonicLayer(song),
    parseHarmonicLayer,
    f,
  );

export const loadDrumEvents = (song: string, f?: typeof fetch) =>
  loadJson<DrumEventsFile>(artifactPaths.drumEvents(song), parseDrumEvents, f);

export const loadEnergyLayer = (song: string, f?: typeof fetch) =>
  loadJson<EnergyLayer>(artifactPaths.energyLayer(song), parseEnergyLayer, f);

export const loadHumanHints = (song: string, f?: typeof fetch) =>
  loadJson<HumanHintsFile>(artifactPaths.humanHints(song), parseHumanHints, f);

export const loadEventTimeline = (song: string, f?: typeof fetch) =>
  loadJson<EventTimeline>(
    artifactPaths.eventTimeline(song),
    parseEventTimeline,
    f,
  );

export const loadReviewQueue = (song: string, f?: typeof fetch) =>
  loadJson<ReviewQueue>(artifactPaths.reviewQueue(song), parseReviewQueue, f);

export const loadSongFacts = (song: string, f?: typeof fetch) =>
  loadJson<SongFactsFile>(artifactPaths.songFacts(song), parseSongFacts, f);

// -- registry (keyed access for useSong) --------------------------------------

export const artifactLoaders = {
  info: loadInfo,
  dropProposals: loadDropProposals,
  vocalPhrases: loadVocalPhrases,
  reactiveBands: loadReactiveBands,
  grid: loadGrid,
  allin1: loadAllin1,
  character: loadCharacter,
  vocalTranscription: loadVocalTranscription,
  beats: loadBeats,
  sectionsTopLevel: loadSectionsTopLevel,
  sectionSegmentation: loadSectionSegmentation,
  fftBands: loadFftBands,
  rmsLoudness: loadRmsLoudness,
  loudnessEnvelope: loadLoudnessEnvelope,
  harmonicLayer: loadHarmonicLayer,
  drums: loadDrumEvents,
  energy: loadEnergyLayer,
  humanHints: loadHumanHints,
  moisesLyrics: loadMoisesLyrics,
  eventTimeline: loadEventTimeline,
  reviewQueue: loadReviewQueue,
  songFacts: loadSongFacts,
} as const;

export type ArtifactKey = keyof typeof artifactLoaders;

/** The typed payload a given artifact key resolves to. */
export type ArtifactData<K extends ArtifactKey> = Extract<
  Awaited<ReturnType<(typeof artifactLoaders)[K]>>,
  { ok: true }
>["data"];
