// TS types for every artifact the UI reads.
//
// These mirror the v1.1 artifact contracts documented in
// `docs/web-ui/7.2.build_ui_data_story.md` and
// `docs/source references/contract-change-v1.1.md`, grounded against the real
// artifact shapes under `data/analysis/_test_song/`.
//
// Fields that v1.1 added to a pre-existing file (e.g. `section_id`, `form_role`
// on the top-level sections list) are typed as `T | null`: a not-yet-reanalysed
// song still carries the older shape, and the parsers coerce a missing field to
// `null` rather than rejecting the file. Quality of the structural read comes
// first, but the UI must not hard-fail on a v1.0 song.

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
}

export type Beats = BeatRow[];

// ---------------------------------------------------------------------------
// sections.json  (top-level UI projection)
// ---------------------------------------------------------------------------

export interface SectionRow {
  start: number;
  end: number;
  /** e.g. "003 Verse (0.76)" */
  label: string;
  description: string | null;
  /** placeholder array kept for compatibility; never the editable hint store */
  hints: unknown[];
  // --- v1.1 additions (projected through from the segmentation artifact) ---
  section_id: string | null;
  form_role: string | null;
  energy_character: string | null;
  repetition_group: string | null;
  confidence: number | null;
}

export type SectionsTopLevel = SectionRow[];

// ---------------------------------------------------------------------------
// artifacts/section_segmentation/sections.json  (v1.1)
// ---------------------------------------------------------------------------

export type FormFamilyValue =
  | "dance_form"
  | "song_form"
  | "hybrid"
  | "unknown"
  | (string & {});

export interface FormFamily {
  value: FormFamilyValue;
  confidence: number;
  provenance: "inferred" | "human-confirmed" | (string & {});
  evidence: Record<string, unknown> | null;
}

export type FormRole =
  | "intro"
  | "verse"
  | "pre_chorus"
  | "chorus"
  | "hook"
  | "bridge"
  | "breakdown"
  | "build"
  | "drop"
  | "post_drop"
  | "instrumental"
  | "outro"
  | "unknown"
  | (string & {});

export interface SegmentationSection {
  section_id: string;
  start: number;
  end: number;
  label: string;
  confidence: number | null;
  section_character: string | null;
  onset_anchored: boolean | null;
  form_role: FormRole | null;
  form_role_confidence: number | null;
  form_role_margin: number | null;
  energy_character: string | null;
  repetition_group: string | null;
  variant_of: string | null;
  similarity: number | null;
  confidence_terms: Record<string, unknown> | null;
}

export interface SectionSegmentation {
  schema_version: string;
  song_name: string;
  form_family: FormFamily | null;
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
}

export interface HumanHintsFile {
  song_name: string;
  human_hints: HumanHint[];
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
