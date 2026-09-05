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
  // Written by experiments/drop_detection (`run export`), never by the pipeline
  // and never by a human. Kept out of `reference/human/` so the drop-impact
  // ground truth stays a purely hand-authored file.
  dropProposals: (song: string) =>
    encodePath(analysis(song, "reference", "proposals", "drop_impacts.json")),
  // Written by experiments/allin1 (`run export`), never by the pipeline. Same
  // rule as the drop proposals above: an experiment's output is a proposal, so
  // it stays out of `artifacts/` and out of `reference/human/`.
  allin1: (song: string) =>
    encodePath(analysis(song, "reference", "proposals", "allin1.json")),
  // Written by experiments/clap (`run character`). Texture blocks — what a
  // passage is *like* — merged from the stems, CLAP's calm axis, and allin1's
  // frame-level shadow labels.
  character: (song: string) =>
    encodePath(analysis(song, "reference", "proposals", "character.json")),
  // Written by experiments/vocalparse and experiments/acestep_transcriber
  // (`run export`). Sung lyrics with timing — one file, a `sources` list keyed
  // by model, plus the shared whisper baseline row.
  vocalTranscription: (song: string) =>
    encodePath(analysis(song, "reference", "proposals", "vocal_transcription.json")),
  // Written by experiments/vocal_phrases (`run export`). Vocal-activity
  // phrase/gap/sustained-note blocks over the vocal stem — Part A of the
  // "vocal phrase blocks" wave-2 entry.
  vocalPhrases: (song: string) =>
    encodePath(analysis(song, "reference", "proposals", "vocal_phrases.json")),
  // Written by experiments/reactive_bands (`run export`). Locally auto-gained
  // FFT band accents (the discrete list only — the dense per-beat stream is
  // not rendered as its own lane, see the experiment's README).
  reactiveBands: (song: string) =>
    encodePath(analysis(song, "reference", "proposals", "reactive_bands.json")),
  // Written by experiments/grid_consensus (`run export`). The resolved
  // downbeat phase + derived phrase grid.
  grid: (song: string) =>
    encodePath(analysis(song, "reference", "proposals", "grid.json")),
  // Moises' word-level sung-lyric export, delivered as external reference. A
  // flat list of word tokens with `line_id`, `start`, `end`; `<SOL>` / `<EOL>`
  // rows mark line boundaries. Read-only ground truth, never written by the
  // pipeline.
  moisesLyrics: (song: string) =>
    encodePath(analysis(song, "reference", "moises", "lyrics.json")),
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
  drumEvents: (song: string) =>
    encodePath(analysis(song, "artifacts", "symbolic_transcription", "drum_events.json")),
  energyLayer: (song: string) =>
    encodePath(analysis(song, "artifacts", "layer_c_energy.json")),
  reviewQueue: (song: string) =>
    encodePath(analysis(song, "artifacts", "validation", "review_queue.json")),
  audio: (song: string) => encodePath(["data", "songs", `${song}.mp3`]),
} as const;

export const listingPaths = {
  analysis: () => encodePath(["data", "analysis"]) + "/",
  songs: () => encodePath(["data", "songs"]) + "/",
};
