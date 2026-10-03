// laneConfig.ts — the timeline's artifact-key list and the lane-id -> data
// lookups that drive empty-state detection. Split out of App.tsx (v3.9 item
// 7) with no behaviour change.

import type { CanvasLaneSource } from "./CanvasLane";

export const TIMELINE_KEYS = [
  "info",
  "beats",
  "sectionsTopLevel",
  // artifact-scoped detail (function / function_confidence / function_status /
  // same_label_as) joined into the Sections lane inspector by section_id.
  "sectionSegmentation",
  "fftBands",
  // per-stem 7-band spectra — one dense lane each, beside the mix FFT lane
  "fftBandsBass",
  "fftBandsDrums",
  "fftBandsHarmonic",
  "fftBandsVocals",
  "rmsLoudness",
  "loudnessEnvelope",
  "drums",
  "humanHints",
  // v3.7 item 10/11 — unreviewed MCP propose_hint queue
  // (reference/proposals/pending.json). Only pending entries get a block;
  // decided entries carry no timeline span.
  "pendingProposals",
  // v3.11 item 24 — hint verdicts + second pass (reference/pre-analysis/verdict.json);
  // the Verdict Checks lane's source. Optional: no file -> no lane.
  "verdictFile",
  // hand-authored section segmentation, editable via the same drag-to-edit /
  // double-click-to-create conventions as humanHints (reference/human, writable)
  "humanSections",
  // Moises.ai reference segmentation — read-only, one precedence tier below
  // humanSections (docs/reference/analysis.segments.md).
  "moisesSections",
  // external word-level sung lyrics (reference/moises)
  "moisesLyrics",
  // v3.4 item 5 — operator's per-token timing validations, overlaid on the
  // Moises Lyrics lane by token id (reference/human, writable, per-click)
  "lyricValidations",
  // v3.7 item 1 — operator's three-state verdict on a claim-bearing lane's
  // emitted block, joined by (lane_id, start) (reference/human, writable,
  // per-click).
  "blockReviews",
  // who-is-playing state changes from the published per-stem RMS
  // (top-level arrangement_state.json)
  "arrangementState",
  // wave-2 experiments (docs/experiments.md run orders 1-3, 6)
  "vocalPhrases",
  // allin1 posterior shadow labels (experiments/allin1_posterior)
  "allin1Posterior",
  // bass/drums-presence state machine sections (experiments/stem_presence_sections)
  "stemPresenceSections",
  // lyric-alignment line timing + call events, timing only (top-level vocal_cadence.json)
  "vocalCadence",
  // whisperX's VAD front-end (speech-domain), voiceness + phrase spans with
  // real sub-second onsets. Its own pipeline service since v3.6 item 2
  // (whisperx_vad/, promoted out of experiments/) — locally-bundled
  // non-gated checkpoint, no live token at analysis time; diarization not
  // attempted — no HF_TOKEN in this environment.
  "whisperxVad",
  // gesture phases + section transitions (plan v3.0 item 9) — the Gestures
  // lane's production data source.
  "eventTimeline",
  // texture / character blocks under review (experiments/clap)
  "character",
  // sung lyrics + timing under review (experiments/vocalparse, acestep_transcriber)
  "vocalTranscription",
  // v3.9 item 2 + the "crash over-fires" bug — per-hit drum-label accuracy
  // checks (experiments/clap_events, kick_check, crash_check).
  "clapEvents",
  "kickCheck",
  "crashCheck",
  "filterSweep",
  "phrases",
  "sectionNames",
] as const;

/** sparse lane id → the single artifact key that backs it (drives empty-state). */
export const SPARSE_LANE_ARTIFACT: Record<string, (typeof TIMELINE_KEYS)[number]> = {
  humanHints: "humanHints",
  llmPendingProposals: "pendingProposals",
  verdictChecks: "verdictFile",
  humanSections: "humanSections",
  moisesSections: "moisesSections",
  // The raw, pre-fusion analyzer artifact — same source already loaded for
  // the fused Sections lane's inspector join.
  allin1Sections: "sectionSegmentation",
  moisesLyrics: "moisesLyrics",
  arrangementState: "arrangementState",
  vocalPhrases: "vocalPhrases",
  allin1Posterior: "allin1Posterior",
  stemPresenceSections: "stemPresenceSections",
  vocalCadence: "vocalCadence",
  whisperxVad: "whisperxVad",
  gestures: "eventTimeline",
  character: "character",
  vocalTranscription: "vocalTranscription",
  sections: "sectionsTopLevel",
  clapEvents: "clapEvents",
  kickCheck: "kickCheck",
  crashCheck: "crashCheck",
  filterSweep: "filterSweep",
  phrases: "phrases",
  sectionNames: "sectionNames",
};

/** lane id → (artifact key, canvas renderer kind) for the item-5 data lanes. */
export const CANVAS_LANES: Record<
  string,
  { key: (typeof TIMELINE_KEYS)[number]; kind: CanvasLaneSource["kind"] }
> = {
  fftBands: { key: "fftBands", kind: "fft" },
  fftBandsBass: { key: "fftBandsBass", kind: "fft" },
  fftBandsDrums: { key: "fftBandsDrums", kind: "fft" },
  fftBandsHarmonic: { key: "fftBandsHarmonic", kind: "fft" },
  fftBandsVocals: { key: "fftBandsVocals", kind: "fft" },
  rmsLoudness: { key: "rmsLoudness", kind: "rms" },
  loudnessEnvelope: { key: "loudnessEnvelope", kind: "env" },
  drums: { key: "drums", kind: "drums" },
};

export function canvasLaneHasData(source: CanvasLaneSource): boolean {
  switch (source.kind) {
    case "fft":
      return !!source.data?.frames.length && !!source.data.bands.length;
    case "rms":
    case "env":
      return !!source.data?.frames.length && !!source.data.sources.length;
    case "drums":
      return !!source.data?.events.length;
  }
}
