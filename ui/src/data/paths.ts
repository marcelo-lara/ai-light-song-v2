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
  // Written by experiments/drop_detection (`run export`), never by the pipeline
  // and never by a human. Kept out of `reference/human/` so the drop-impact
  // ground truth stays a purely hand-authored file.
  dropProposals: (song: string) =>
    encodePath(analysis(song, "reference", "proposals", "drop_impacts.json")),
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
  // Written by experiments/texture_novelty (`run export`). Segments between
  // self-similarity-novelty texture boundaries. A proposal to audition against
  // Human Hints — failed its kill condition, kept for one review pass.
  textureNovelty: (song: string) =>
    encodePath(analysis(song, "reference", "proposals", "texture_novelty.json")),
  // Written by experiments/phrase_periodicity (`run export`). One block per
  // operator hint, each carrying a repetition `regime` + `period` (bars, or
  // null → "no phrase structure detected"). A proposal to audition against
  // Human Hints — passed its kill condition.
  phrasePeriodicity: (song: string) =>
    encodePath(analysis(song, "reference", "proposals", "phrase_periodicity.json")),
  // Written by experiments/structural_vs_micro (`run export`). One block per
  // operator hint, each carrying `kind` ("structural" | "micro", by 4-bar
  // phrase-grid fit) + `grid_fit_bars` (the fit error in bars). A proposal to
  // audition against Human Hints — failed its kill condition, kept for one
  // review pass.
  structuralVsMicro: (song: string) =>
    encodePath(analysis(song, "reference", "proposals", "structural_vs_micro.json")),
  // Written by experiments/vocal_voiceness (`run export`). A shared
  // voiceness_common.schema proposal: per-50ms-frame voiceness score
  // (vibrato + portamento + sibilance, noisy-OR combined) plus bridged
  // vocal_phrase spans. A proposal to audition against Human Hints — kill
  // condition unevaluable until item 1's `type: "vocal"` ground truth exists.
  vocalVoiceness: (song: string) =>
    encodePath(analysis(song, "reference", "proposals", "vocal_voiceness.json")),
  // Written by experiments/clap_voiceness (`run export`). The same shared
  // voiceness_common.schema proposal shape as vocalVoiceness, but from a
  // CLAP audio-text contrastive differential ("a person singing" vs "a
  // flute, a synth lead") instead of DSP cues — an independent second
  // opinion on the frame-level call, not a boundary competitor (its 5s
  // window is too coarse to time an edge; interval_ms reflects that, at
  // 1000, not 50). Kill condition unevaluable until item 1's `type: "vocal"`
  // ground truth exists.
  clapVoiceness: (song: string) =>
    encodePath(analysis(song, "reference", "proposals", "clap_voiceness.json")),
  // Written by experiments/svd_tagger (`run export`). PANNs' `Singing` class
  // head (AudioSet-527, index 27) run on BOTH the vocal stem and the mix —
  // every row carries `channel: "stem" | "mix"` (the only voiceness
  // candidate that fuses two producers into one file). `interval_ms: 1000`,
  // same PANNs-window-grid honesty as clapVoiceness. Kill condition
  // unevaluable until item 1's `type: "vocal"` ground truth exists.
  svdTagger: (song: string) =>
    encodePath(analysis(song, "reference", "proposals", "svd_tagger.json")),
  // Written by experiments/whisperx_vad (`run export`). The same shared
  // voiceness_common.schema proposal shape as vocalVoiceness/clapVoiceness
  // (no `channel` — single producer, vocal stem only), but from whisperX's
  // VAD front-end (speech-domain) instead of DSP cues or a perceptual-audio
  // model. `interval_ms: 50` — VAD's own sub-second onsets are real, unlike
  // clapVoiceness/svdTagger's 1000ms clip windows, so its `vocal_phrase`
  // boundaries are genuinely scoreable, not just reported. Diarization was
  // not attempted (no HF_TOKEN in this environment) — VAD-only.
  whisperxVad: (song: string) =>
    encodePath(analysis(song, "reference", "proposals", "whisperx_vad.json")),
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
