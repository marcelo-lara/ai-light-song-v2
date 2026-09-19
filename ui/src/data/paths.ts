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
  // v3.6 item 4 — unreviewed rule-based drafts (experiments/segment_seeds),
  // same spans as segments.json. Read-only to the UI: never written here,
  // shown only as a draft fallback in the segment editor per field.
  humanSectionsSeed: (song: string) =>
    encodePath(analysis(song, "reference", "human", "segments.seed.json")),
  songFacts: (song: string) =>
    encodePath(analysis(song, "reference", "human", "song_facts.json")),
  // v3.4 item 4 — operator's 1-5 energy/tension rating per human_hints.json
  // block, joined by hint_id. Writable (debugger only), reference/human/
  // material; nothing in src/ or mcp/ reads it.
  blockEnergy: (song: string) =>
    encodePath(analysis(song, "reference", "human", "block_energy.json")),
  // v3.4 item 5 — ids of the Moises lyric tokens the operator has hand-verified.
  // An overlay on reference/moises/lyrics.json (never an edit to it). Writable
  // (debugger only, per-click), reference/human/ material; nothing in src/ or
  // mcp/ reads it.
  lyricValidations: (song: string) =>
    encodePath(analysis(song, "reference", "human", "lyric_validations.json")),
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
  // Top-level published `arrangement_state.json` (phase-4 publish of the
  // `detect-arrangement-state` stage). Who-is-playing state-change blocks
  // derived from the published per-stem RMS series — no audio, no model.
  arrangementState: (song: string) =>
    encodePath(analysis(song, "arrangement_state.json")),
  // Written by experiments/rhythm_drum_ioi (`run export`). item 5/6a:
  // rhythm.drums subdivision + confidence from drum_events.json IOI.
  rhythmDrumIoi: (song: string) =>
    encodePath(analysis(song, "reference", "proposals", "rhythm_drum_ioi.json")),
  // Written by experiments/rhythm_stem_autocorr (`run export`). item 5/6b:
  // rhythm.{drums,bass,harmonic,vocals} from per-stem sub-beat autocorrelation.
  rhythmStemAutocorr: (song: string) =>
    encodePath(analysis(song, "reference", "proposals", "rhythm_stem_autocorr.json")),
  // Written by experiments/rhythm_vocal_onsets (`run export`, ACE-Step
  // sandbox `compute`). item 5/6c: rhythm.vocals + onsets_per_beat from
  // whisper word-onset intervals.
  rhythmVocalOnsets: (song: string) =>
    encodePath(analysis(song, "reference", "proposals", "rhythm_vocal_onsets.json")),
  // Written by experiments/energy_level (`run export`). item 5/6: candidate
  // `energy` (1-5) from segment loudness level + stems-playing fraction.
  energyLevel: (song: string) =>
    encodePath(analysis(song, "reference", "proposals", "energy_level.json")),
  // Written by experiments/tension_shape (`run export`). item 5/6: candidate
  // `tension` (1-5) from energy slope + gesture/regime overlap.
  tensionShape: (song: string) =>
    encodePath(analysis(song, "reference", "proposals", "tension_shape.json")),
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
