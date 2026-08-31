// URL builders for the dev-server `/data` mount. Every segment is
// percent-encoded (song names contain spaces and " - ").

export function encodePath(parts: string[]): string {
  return "/" + parts.map((part) => encodeURIComponent(part)).join("/");
}

const analysis = (song: string, ...rest: string[]): string[] => [
  "data",
  "analysis",
  song,
  ...rest,
];

export const artifactPaths = {
  info: (song: string) => encodePath(analysis(song, "info.json")),
  beats: (song: string) => encodePath(analysis(song, "beats.json")),
  sectionsTopLevel: (song: string) => encodePath(analysis(song, "sections.json")),
  eventTimeline: (song: string) =>
    encodePath(analysis(song, "song_event_timeline.json")),
  humanHints: (song: string) =>
    encodePath(analysis(song, "reference", "human", "human_hints.json")),
  songFacts: (song: string) =>
    encodePath(analysis(song, "reference", "human", "song_facts.json")),
  sectionSegmentation: (song: string) =>
    encodePath(analysis(song, "artifacts", "section_segmentation", "sections.json")),
  fftBands: (song: string) =>
    encodePath(analysis(song, "artifacts", "essentia", "fft_bands.json")),
  rmsLoudness: (song: string) =>
    encodePath(analysis(song, "artifacts", "essentia", "rms_loudness.json")),
  loudnessEnvelope: (song: string) =>
    encodePath(analysis(song, "artifacts", "essentia", "loudness_envelope.json")),
  harmonicLayer: (song: string) =>
    encodePath(analysis(song, "artifacts", "layer_a_harmonic.json")),
  reviewQueue: (song: string) =>
    encodePath(analysis(song, "artifacts", "validation", "review_queue.json")),
  audio: (song: string) => encodePath(["data", "songs", `${song}.mp3`]),
} as const;

export const listingPaths = {
  analysis: () => encodePath(["data", "analysis"]) + "/",
  songs: () => encodePath(["data", "songs"]) + "/",
};
