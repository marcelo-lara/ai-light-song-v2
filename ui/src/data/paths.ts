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
  // v3.6 item 8 — the display-only fields (label/description)
  // split out of the trimmed top-level sections.json. Read by the UI only,
  // to re-merge into the full `SectionRow` shape (see `mergeSectionDisplay`).
  sectionsDisplay: (song: string) =>
    encodePath(analysis(song, "artifacts", "section_segmentation", "sections_display.json")),
  // v3.6 item 8 trimmed `section_name` / `summary` / `evidence_summary` /
  // `provenance` / `generated_from` off the top-level song_event_timeline.json
  // (unread by any consumer). The debugger's Gestures lane still needs them
  // for operator review, so it reads the full pre-trim artifact instead —
  // written first, byte-for-byte the same events plus those fields
  // (src/analyzer/stages/gestures.py).
  eventTimeline: (song: string) =>
    encodePath(analysis(song, "artifacts", "gestures", "song_event_timeline.json")),
  humanHints: (song: string) =>
    encodePath(analysis(song, "reference", "human", "human_hints.json")),
  // Editable, hand-authored section segmentation — same reference/human/
  // writable-lane conventions as humanHints (drag-to-edit, double-click to
  // create, explicit Save), but a bare-array, simpler schema
  // ({start, end, label} only, no id/type/summary).
  humanSections: (song: string) =>
    encodePath(analysis(song, "reference", "human", "segments.json")),
  songFacts: (song: string) =>
    encodePath(analysis(song, "reference", "human", "song_facts.json")),
  // v3.4 item 5 — ids of the Moises lyric tokens the operator has hand-verified.
  // An overlay on reference/moises/lyrics.json (never an edit to it). Writable
  // (debugger only, per-click), reference/human/ material; nothing in src/ or
  // mcp/ reads it.
  lyricValidations: (song: string) =>
    encodePath(analysis(song, "reference", "human", "lyric_validations.json")),
  // v3.7 item 1 — the operator's three-state verdict (correct/wrong/misplaced)
  // on each block of a claim-bearing lane, joined by (lane_id, start).
  // Writable (debugger only, per-click), reference/human/ material; nothing
  // in src/ or mcp/ reads it.
  blockReviews: (song: string) =>
    encodePath(analysis(song, "reference", "human", "block_reviews.json")),
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
  // Written by experiments/allin1_posterior (`run export`). Shadow-label
  // spans — a non-argmax allin1 label sustaining a share of the frame
  // posterior the published 8-bar argmax discards (e.g. Armin's `break`).
  allin1Posterior: (song: string) =>
    encodePath(analysis(song, "reference", "proposals", "allin1_posterior.json")),
  // Written by experiments/stem_presence_sections (`run export`). Bass
  // on/off + drums full/sparse/off state-machine sections, boundaries moved
  // to the nearest physical stem onset.
  stemPresenceSections: (song: string) =>
    encodePath(analysis(song, "reference", "proposals", "stem_presence_sections.json")),
  // Top-level published `vocal_cadence.json` (v3.9 item 1, promoted out of
  // experiments/vocal_cadence). Per-line bar timing + call events from the
  // operator's lyric alignment. Timing only — no lyric text.
  vocalCadence: (song: string) =>
    encodePath(analysis(song, "vocal_cadence.json")),
  // Top-level published `arrangement_state.json` (phase-4 publish of the
  // `detect-arrangement-state` stage). Who-is-playing state-change blocks
  // derived from the published per-stem RMS series — no audio, no model.
  arrangementState: (song: string) =>
    encodePath(analysis(song, "arrangement_state.json")),
  // Written by the `whisperx` Compose service (whisperx_vad/, promoted out of
  // experiments/ in v3.6 item 2). Per-50ms-frame voiceness curve (no
  // `channel` — single producer, vocal stem only) plus `Binarize`d
  // vocal_phrase spans, from whisperX's VAD front-end (speech-domain) rather
  // than DSP cues or a perceptual-audio model. `interval_ms: 50` — VAD's own
  // sub-second onsets are real, so its `vocal_phrase` boundaries are
  // genuinely scoreable, not just reported. Diarization was not attempted (no
  // HF_TOKEN in this environment) — VAD-only.
  whisperxVad: (song: string) =>
    encodePath(analysis(song, "artifacts", "whisperx-vad", "whisperx_vad.json")),
  // Moises' word-level sung-lyric export, delivered as external reference. A
  // flat list of word tokens with `line_id`, `start`, `end`; `<SOL>` / `<EOL>`
  // rows mark line boundaries. Read-only ground truth, never written by the
  // pipeline.
  moisesLyrics: (song: string) =>
    encodePath(analysis(song, "reference", "moises", "lyrics.json")),
  // Moises.ai reference segmentation — read-only, one precedence tier below
  // reference/human/segments.json (docs/reference/analysis.segments.md).
  moisesSections: (song: string) =>
    encodePath(analysis(song, "reference", "moises", "segments.json")),
  sectionSegmentation: (song: string) =>
    encodePath(analysis(song, "artifacts", "section_segmentation", "sections.json")),
  fftBands: (song: string) =>
    encodePath(analysis(song, "artifacts", "essentia", "fft_bands.json")),
  // Per-stem 7-band spectra (analyzer stages/fft_bands.py). Same schema as the
  // mix file; each normalised against its own stem's percentiles. Inherits
  // Demucs separation error — reviewed by eye in its own dense lane.
  fftBandsBass: (song: string) =>
    encodePath(analysis(song, "artifacts", "essentia", "fft_bands.bass.json")),
  fftBandsDrums: (song: string) =>
    encodePath(analysis(song, "artifacts", "essentia", "fft_bands.drums.json")),
  fftBandsHarmonic: (song: string) =>
    encodePath(analysis(song, "artifacts", "essentia", "fft_bands.harmonic.json")),
  fftBandsVocals: (song: string) =>
    encodePath(analysis(song, "artifacts", "essentia", "fft_bands.vocals.json")),
  rmsLoudness: (song: string) =>
    encodePath(analysis(song, "artifacts", "essentia", "rms_loudness.json")),
  loudnessEnvelope: (song: string) =>
    encodePath(analysis(song, "artifacts", "essentia", "loudness_envelope.json")),
  drumEvents: (song: string) =>
    encodePath(analysis(song, "artifacts", "symbolic_transcription", "drum_events.json")),
  reviewQueue: (song: string) =>
    encodePath(analysis(song, "artifacts", "validation", "review_queue.json")),
  // v3.7 item 10/11 — the MCP correction-proposals queue. Read here via the
  // static `/data` mount, same convention as every other reference/ file
  // (`humanHints` etc. above); writes go through the dedicated
  // `/api/proposal-decision/<song>` endpoint, never a direct PUT of this path.
  pendingProposals: (song: string) =>
    encodePath(analysis(song, "reference", "proposals", "pending.json")),
  // v3.11 items 21-24 — hint verdicts + second pass. Optional (absent until
  // the version-check / hint-verdict stages have run on a song with a hint);
  // read-only for the Verdict Checks lane. Its one write is the `operator`
  // answer, through `/api/proposal-decision/<song>`, never a direct PUT.
  verdictFile: (song: string) =>
    encodePath(analysis(song, "reference", "pre-analysis", "verdict.json")),
  audio: (song: string) => encodePath(["data", "songs", `${song}.mp3`]),
  // v3.8 item 2/3 — request/progress pair for the host-side
  // ./analysis-watcher (item 1). `runRequest` is written by this UI's `PUT
  // /api/run-request/<song>` and by mcp/runs.py's `request_analysis` — one
  // mechanism, two callers. `runProgress` is read-only here (the watcher's
  // own write); a 404 is the expected idle case, not an error. Neither file
  // is `reference/human/` material or a delivery artifact.
  runRequest: (song: string) =>
    encodePath(analysis(song, "artifacts", "_run_request.json")),
  runProgress: (song: string) =>
    encodePath(analysis(song, "artifacts", "_run_progress.json")),
  // Written by experiments/clap_events (`run export`). v3.9 item 2: claps
  // detected from the drums stem by per-hit spectral shape.
  clapEvents: (song: string) =>
    encodePath(analysis(song, "reference", "proposals", "clap_events.json")),
  // Written by experiments/kick_check (`run export`). v3.9 item 2 (kick-check
  // sibling): every omnizart `kick` kept/rejected by per-hit spectral shape.
  kickCheck: (song: string) =>
    encodePath(analysis(song, "reference", "proposals", "kick_check.json")),
  // Written by experiments/crash_check (`run export`). The "crash over-fires
  // on bright hats/rides" bug: every omnizart `crash` kept/rejected by
  // stream-period + decay-shape.
  crashCheck: (song: string) =>
    encodePath(analysis(song, "reference", "proposals", "crash_check.json")),
  // Written by experiments/filter_sweep (`run export`). v3.10 item 14: a stem's
  // brightness (spectral centroid) moving near-monotonically over 2-16 bars
  // while its loudness stays level.
  filterSweep: (song: string) =>
    encodePath(analysis(song, "reference", "proposals", "filter_sweep.json")),
  // Written by experiments/bar_features (`run export`). v3.12 item 1: one row
  // per bar fusing loudness, bands, brightness, transients, drum counts,
  // arrangement, sweeps and gestures.
  barFeatures: (song: string) =>
    encodePath(analysis(song, "reference", "proposals", "bar_features.json")),
  // Written by experiments/light_changes (`run export`). v3.12 item 2: light
  // change points with a role, detected on the bar-features table.
  lightChanges: (song: string) =>
    encodePath(analysis(song, "reference", "proposals", "light_changes.json")),
  // Written by experiments/phrases (`run export`). v3.10 item 15: the song cut
  // where the audio changes, one block per phrase with presence / density
  // features. Never bar-counted.
  phrases: (song: string) =>
    encodePath(analysis(song, "reference", "proposals", "phrases.json")),
  // Written by experiments/section_names (`run export`). v3.10 item 17: every
  // phrase named in the typical EDM sequence (Intro ... Build-Up ... Drop ...),
  // or the current labels kept and attributed when no build->drop unit is found.
  sectionNames: (song: string) =>
    encodePath(analysis(song, "reference", "proposals", "section_names.json")),
} as const;

export const listingPaths = {
  analysis: () => encodePath(["data", "analysis"]) + "/",
  songs: () => encodePath(["data", "songs"]) + "/",
};
