// TS types for every artifact the UI reads.
//
// These mirror the artifact contracts documented in `docs/data_folder_reference.md`
// and `docs/reference/analysis-input-guide.md`, grounded against the real
// artifact shapes under `data/analysis/_test_song/`.
//
// `sections.json` and `artifacts/section_segmentation/sections.json` carry the
// v3.0 allin1 named-segmentation shape (plan v3.0 item 7): a `function` from
// allin1's Harmonix vocabulary, its confidence, a `function_status` that reads
// `"unknown"` when the song is outside allin1's training distribution, and
// `same_label_as` linking repeated occurrences of the same function. The old
// `section_character` / `energy_character` / `repetition_group` / `form_role`
// fields are gone — see `docs/contract-change-v3.0.md`.

// ---------------------------------------------------------------------------
// info.json  (top-level UI contract)
// ---------------------------------------------------------------------------

export interface SongInfo {
  schema_version: string;
  song_name: string;
  bpm: number;
  duration: number;
  song_path: string;
  /** absolute `/data/...` paths to producer artifacts, keyed by short name */
  artifacts: Record<string, string>;
  /** absolute `/data/...` paths to the top-level UI outputs */
  outputs: Record<string, string> | null;
  generated_from: Record<string, unknown> | null;
  debug: Record<string, unknown> | null;
}

// ---------------------------------------------------------------------------
// beats.json  (top-level UI contract — compact row shape)
// ---------------------------------------------------------------------------

export type BeatType = "downbeat" | "beat" | (string & {});

export interface BeatRow {
  time: number;
  beat: number;
  bar: number;
  bass: string | null;
  chord: string | null;
  type: BeatType;
  confidence: number | null;
}

export type Beats = BeatRow[];

// ---------------------------------------------------------------------------
// sections.json  (top-level UI projection)
// ---------------------------------------------------------------------------

export interface SectionRow {
  section_id: string;
  start: number;
  end: number;
  /** e.g. "003 Chorus (0.80)" */
  label: string;
  description: string | null;
  confidence: number | null;
}

export type SectionsTopLevel = SectionRow[];

// ---------------------------------------------------------------------------
// artifacts/section_segmentation/sections.json  (v3.0 — allin1 named
// segmentation, replacing the old dance/song-form + mood-vocabulary shape)
// ---------------------------------------------------------------------------

export interface SegmentationSection {
  section_id: string;
  start: number;
  end: number;
  /** allin1's Harmonix-vocabulary functional label, e.g. "chorus"; null when unresolved */
  function: string | null;
  /** 1 - normalised entropy of allin1's frame-level label posterior over the span */
  function_confidence: number | null;
  /** "unknown" when the song is outside allin1's training distribution — the boundary may still be right */
  function_status: string | null;
  /** section_id of the first earlier section sharing this `function`, else null */
  same_label_as: string | null;
  confidence: number | null;
}

export interface SectionSegmentation {
  schema_version: string;
  song_name: string;
  generated_from: Record<string, unknown> | null;
  sections: SegmentationSection[];
}

// ---------------------------------------------------------------------------
// artifacts/essentia/fft_bands.json
// ---------------------------------------------------------------------------

export interface FftBand {
  id: string;
  label: string;
  start_hz: number;
  end_hz: number;
}

export interface FftFrame {
  frame_index: number;
  time: number;
  /** one level per band, index-aligned with `bands` */
  levels: number[];
  brightness_ratio: number | null;
  transient_strength: number | null;
  dropout_strength: number | null;
}

export interface FftBands {
  schema_version: string;
  song_name: string;
  bands: FftBand[];
  frames: FftFrame[];
  metadata: Record<string, unknown> | null;
}

// ---------------------------------------------------------------------------
// artifacts/essentia/rms_loudness.json + loudness_envelope.json  (same shape)
// ---------------------------------------------------------------------------

export interface LoudnessSource {
  id: string;
  label: string;
  path: string;
  kind: "mix" | "stem" | (string & {});
}

export interface LoudnessHistory {
  mean_2s: number[];
  peak_2s: number[];
  mean_5s: number[];
  peak_5s: number[];
}

export interface LoudnessFrame {
  frame_index: number;
  time: number;
  start_s: number | null;
  end_s: number | null;
  /** one value per source, index-aligned with `sources` */
  values: number[];
  normalized_values: number[];
  history: LoudnessHistory | null;
}

export interface LoudnessSeries {
  schema_version: string;
  song_name: string;
  sources: LoudnessSource[];
  frames: LoudnessFrame[];
  metadata: Record<string, unknown> | null;
}

export type RmsLoudness = LoudnessSeries;
export type LoudnessEnvelope = LoudnessSeries;

// ---------------------------------------------------------------------------
// artifacts/layer_a_harmonic.json
// ---------------------------------------------------------------------------

export interface HarmonicGlobalKey {
  label: string | null;
  confidence: number | null;
  source: string | null;
}

export interface HarmonicChord {
  time: number;
  end_s: number;
  bar: number | null;
  beat: number | null;
  chord: string;
  confidence: number | null;
}

export interface HarmonicLayer {
  schema_version: string;
  song_name: string;
  global_key: HarmonicGlobalKey | null;
  chords: HarmonicChord[];
  chord_probabilities: unknown;
}

// ---------------------------------------------------------------------------
// artifacts/symbolic_transcription/drum_events.json
// ---------------------------------------------------------------------------

export interface DrumEvent {
  id: string;
  time: number;
  end_s: number;
  event_type: string;
}

export interface DrumEventsFile {
  schema_version: string;
  song_name: string;
  events: DrumEvent[];
}

// ---------------------------------------------------------------------------
// artifacts/layer_c_energy.json  (beat-aligned energy + accent candidates)
// ---------------------------------------------------------------------------

export interface EnergyBeat {
  time: number;
  energy_score: number;
  bar: number | null;
  beat: number | null;
}

export interface EnergyAccent {
  id: string;
  time: number;
  intensity: number;
  kind: string;
}

export interface EnergyLayer {
  schema_version: string;
  song_name: string;
  beat_energy: EnergyBeat[];
  accent_candidates: EnergyAccent[];
}

// ---------------------------------------------------------------------------
// reference/human/human_hints.json  (editable hint store)
// ---------------------------------------------------------------------------

export interface HumanHint {
  id: string;
  title: string;
  start_time: number;
  end_time: number;
  summary: string;
  lighting_hint: string;
  /**
   * Where this hint was captured from, e.g. "allin1 Sections ·
   * experiments/allin1". Informative only — nothing reads it. Absent on
   * hand-authored hints (plan v1.5 D11).
   */
  captured_from?: string;
}

export interface HumanHintsFile {
  song_name: string;
  human_hints: HumanHint[];
}

// ---------------------------------------------------------------------------
// reference/human/song_facts.json  (v1.1 — whole-song facts, human-confirmed)
// ---------------------------------------------------------------------------
// Written ONLY by an explicit human Save in the review-queue editor (Story
// 8.10). The analyzer never writes `reference/`.

export interface SongFact {
  value: unknown;
  provenance: string | null;
  confirmed_on: string | null;
  note: string | null;
}

export interface SongFactsFile {
  schema_version: string;
  song_name: string;
  facts: Record<string, SongFact>;
}

// ---------------------------------------------------------------------------
// song_event_timeline.json  (v1.1 — composite events + texture_summary)
// ---------------------------------------------------------------------------

export type EventPhaseName =
  | "approach"
  | "build"
  | "tension"
  | "impact"
  | "release"
  | "recovery"
  | (string & {});

export interface EventPhase {
  phase: EventPhaseName;
  start_time: number;
  end_time: number;
  intensity: number;
}

export interface TimelineEvent {
  id: string;
  type: string;
  start_time: number;
  end_time: number;
  confidence: number;
  /** v1.1: absolute magnitude within a fixed per-type band, not per-song norm */
  intensity: number;
  section_id: string | null;
  section_name: string | null;
  provenance: string | null;
  summary: string | null;
  created_by: string | null;
  evidence_summary: string | null;
  lighting_hint: string | null;
  evidence_ref: Record<string, unknown> | null;
  /** v1.1: true when this row folds a build → drop → post_drop run */
  composite: boolean;
  /** ordered sub-phases of a composite gesture; null for a plain event */
  phases: EventPhase[] | null;
  member_event_ids: string[] | null;
}

export interface TextureSummary {
  section_id: string;
  start_time: number;
  stem_activity: Record<string, number>;
  stems_entering: string[];
  stems_leaving: string[];
}

export interface EventTimeline {
  schema_version: string;
  song_name: string;
  generated_from: Record<string, unknown> | null;
  events: TimelineEvent[];
  /** v1.1: replaces the removed layer_add / layer_remove events */
  texture_summary: TextureSummary[];
}

// ---------------------------------------------------------------------------
// artifacts/validation/review_queue.json  (v1.1, new file)
// ---------------------------------------------------------------------------

export interface ReviewCandidate {
  value: unknown;
  score: number;
}

export interface ReviewQuestion {
  /** dotted path of the field in question, e.g. "sections.section-002.form_role" */
  field: string;
  candidates: ReviewCandidate[];
  evidence_timestamps: number[];
  reason_low_confidence: string | null;
  leverage: number | null;
}

export interface ReviewQueue {
  schema_version: string;
  song_name: string;
  direction_of_flow: string | null;
  open_question_count: number | null;
  questions: ReviewQuestion[];
}
