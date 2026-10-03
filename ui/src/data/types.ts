// TS types for every artifact the UI reads.
//
// These mirror the artifact contracts documented in `docs/reference/artifacts.md`
// and `docs/mcp-definition.md`, grounded against the real artifact shapes under
// `data/analysis/_test_song/`.
//
// `sections.json` and `artifacts/section_segmentation/sections.json` carry the
// v3.0 allin1 named-segmentation shape (plan v3.0 item 7): a `function` from
// allin1's Harmonix vocabulary, its confidence, a `function_status` that reads
// `"unknown"` when the song is outside allin1's training distribution, and
// `same_label_as` linking repeated occurrences of the same function. The old
// `section_character` / `energy_character` / `repetition_group` / `form_role`
// fields are gone — see `docs/analysis-definition.md`.

// ---------------------------------------------------------------------------
// info.json  (top-level UI contract)
// ---------------------------------------------------------------------------

export interface SongInfo {
  schema_version: string;
  song_name: string;
  bpm: number;
  duration: number;
  /** v3.1 item 2 attribution header — `bpm` / `duration` → `essentia`.
   *  v3.1 item 8 removed `song_path`, `artifacts`, `outputs`, `debug` and
   *  `generated_from`: they embedded absolute host paths and a per-song file
   *  manifest no consumer needs (files are discovered from the fixed top-level
   *  layout). */
  field_sources: Record<string, string>;
}

// ---------------------------------------------------------------------------
// beats.json  (top-level UI contract — compact row shape)
// ---------------------------------------------------------------------------

export type BeatType = "downbeat" | "beat" | (string & {});

export interface BeatRow {
  time: number;
  beat: number;
  bar: number;
  type: BeatType;
  downbeat_confidence: number | null;
}

export interface BeatsFile {
  field_sources: Record<string, string>;
  beats: BeatRow[];
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
  /** allin1's Harmonix-vocabulary functional label (e.g. "chorus"), or `null`.
   * v3.1 item 3 — merged onto the top-level row so a consumer never opens
   * artifacts/section_segmentation/sections.json. */
  function: string | null;
  function_confidence: number | null;
  /** "known" / "unknown" — treat `function` as unverified when "unknown". */
  function_status: string;
  /** section_id of the first section allin1 gave the same label; label
   * repetition, not acoustic identity. */
  same_label_as: string | null;
  confidence: number | null;
}

export interface SectionsFile {
  field_sources: Record<string, string>;
  sections: SectionRow[];
}

export type SectionsTopLevel = SectionRow[];

// v3.6 item 8 — the trimmed wire shape of the top-level sections.json row,
// after `label` / `description` moved to
// artifacts/section_segmentation/sections_display.json. Used only as the
// raw parse of the top-level file, before `mergeSectionDisplay` joins it
// with the display artifact back into the full `SectionRow` every UI
// component still consumes.
export interface SectionsTopLevelRow {
  section_id: string;
  start: number;
  end: number;
  function: string | null;
  function_confidence: number | null;
  function_status: string;
  same_label_as: string | null;
  confidence: number | null;
}

export type SectionsTopLevelRows = SectionsTopLevelRow[];

// v3.6 item 8 — artifacts/section_segmentation/sections_display.json. The
// display-only fields split out of sections.json; never exposed to the MCP
// server, read by the UI only to re-merge into `SectionRow`.
export interface SectionDisplayRow {
  section_id: string;
  label: string;
  description: string | null;
}

export interface SectionDisplayFile {
  schema_version: string;
  song_name: string;
  sections: SectionDisplayRow[];
}

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
  /**
   * "review" when the hint originated from an experiment/event block seeded
   * for review or annotation; "vocal" when a voice sounds continuously across
   * the span (only ever chosen explicitly by the operator, never inferred);
   * absent (equivalent to "hint") for a hand-authored one. Editable in the
   * hint editor; "review" defaults from whether the hint carries a
   * `captured_from` note, "vocal" never defaults.
   */
  type?: "hint" | "review" | "vocal";
}

export interface HumanHintsFile {
  song_name: string;
  human_hints: HumanHint[];
}

// ---------------------------------------------------------------------------
// reference/human/segments.json  (editable, hand-authored section segmentation)
// ---------------------------------------------------------------------------

/**
 * A bare array on disk — no wrapper object, no id/type/summary fields. Much
 * simpler than `HumanHint`: this is the operator's own section segmentation.
 * `label` is a fixed value, optional (honest-unknown when unset), one of
 * `SEGMENT_FUNCTION_NAMES` (../data/segmentFunctions) — the canonical
 * vocabulary is docs/segments-vocabulary.md. Free text is never accepted:
 * a segment's label is either a vocabulary name or unset, never anything
 * else. `description` is optional free text, never validated against the
 * vocabulary. `preserved` holds every other key the row carries on disk,
 * verbatim, so a Save writes it back untouched; nothing reads it.
 */
export interface HumanSegment {
  start: number;
  end: number;
  label?: string | null;
  description?: string | null;
  preserved?: Record<string, unknown>;
}

export type HumanSegmentsFile = HumanSegment[];

// ---------------------------------------------------------------------------
// reference/moises/segments.json  (Moises.ai reference segmentation)
// ---------------------------------------------------------------------------
// Same bare-array shape as reference/human/segments.json ({start, end, label}
// only — no description, no confidence field of its own: see
// docs/reference/analysis.segments.md). Reuses HumanSegment's parser.

export type MoisesSegmentsFile = HumanSegment[];

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
// reference/human/lyric_validations.json  (v3.4 item 5 / D6 — operator's
// hand-verification of Moises lyric-token timing)
// ---------------------------------------------------------------------------
// An overlay on `reference/moises/lyrics.json`: the ids of the Moises word
// tokens whose timing the operator has personally checked against the
// waveform. The Moises Lyrics lane substitutes confidence `1` for a listed
// token at read time — a value Moises itself never emits — so a validated
// token is unambiguous. `reference/moises/lyrics.json` is never edited; it
// stays read-only, inference-only.
//
// SCOPE GUARD: nothing in `src/` or `mcp/` reads this file. It is
// `reference/human/` material like the hints — one producer (the operator),
// no `field_sources` / `source` attribution. Written per-click by
// `PUT /api/lyric-validations/<song>` (dev-server only), which diverges from
// the explicit-Save pattern the other `reference/human/` writers use (D5.1 —
// a rapid token-by-token pass should not need a Save button).

export interface LyricValidationsFile {
  schema_version: string;
  song_name: string;
  validated_ids: number[];
}

// ---------------------------------------------------------------------------
// reference/human/block_reviews.json  (v3.7 item 1 — a precision instrument:
// the operator's verdict on whether a claim-bearing lane's emitted block is
// real)
// ---------------------------------------------------------------------------
// A three-state verdict per block of a claim-bearing lane (docs/product-
// refinement-v3.7.md item 1). The join key is `(lane_id, start)`, `start`
// rounded to 3 decimals — block ids are array positions and shift on every
// re-run, so they are never the key. `verdict`/`reason` are fixed
// vocabularies (they are counted by the experiments/truth_common scorer);
// `note` is free text, never parsed. SCOPE GUARD: nothing in `src/` or `mcp/`
// reads this file — it is `reference/human/` material like the hints, one
// producer (the operator), written per-click like `lyric_validations.json`.

export type BlockReviewVerdict = "correct" | "wrong" | "misplaced";
export type BlockReviewReason = "boundary" | "label" | "value";

export interface BlockReview {
  lane_id: string;
  /** rounded to 3 decimal places — the join key alongside `lane_id` */
  start: number;
  verdict: BlockReviewVerdict;
  /** `null` on `correct`; required (non-null) on `wrong` / `misplaced` */
  reason: BlockReviewReason | null;
  note: string;
  reviewed_at: string;
}

export interface BlockReviewsFile {
  schema_version: string;
  song_name: string;
  reviews: BlockReview[];
}

/**
 * A review annotated at read time against the CURRENT run's emitted blocks.
 * `stale: true` when no block of `lane_id` in the current run has a `start`
 * within ±0.25 s of this review's `start` — never dropped, never
 * re-attached to a neighbouring block (see `../data/blockReviewMatch.ts`).
 */
export interface BlockReviewMatched extends BlockReview {
  stale: boolean;
}

// ---------------------------------------------------------------------------
// song_event_timeline.json  (plan v3.0 item 9 — flat gesture-phase /
// section-transition events, replacing the Epic-5 composite event_* stack)
// ---------------------------------------------------------------------------

/** A gesture-phase `type`, or a `"<from> → <to>"` section-pair transition
 * (never a literal drop -- it is derived from a named section pair), so this stays open-ended. */
export type EventPhaseName =
  | "approach"
  | "build"
  | "tension"
  | "impact"
  | "release"
  | (string & {});

export interface TimelineEvent {
  type: EventPhaseName;
  start_time: number;
  end_time: number;
  confidence: number;
  /** absolute magnitude within a fixed per-type band, not per-song norm */
  intensity: number;
  section_id: string | null;
  section_name: string | null;
  /** v3.1 item 4 — shared by every gesture-phase row of one composite gesture
   * (e.g. "gesture-003"); absent on section-pair transition rows. */
  gesture_id?: string;
  provenance: string | null;
  summary: string | null;
  evidence_summary: string | null;
}

export interface EventTimeline {
  schema_version: string;
  song_name: string;
  generated_from: Record<string, unknown> | null;
  events: TimelineEvent[];
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

// ---------------------------------------------------------------------------
// reference/proposals/pending.json  (v3.7 item 10/11 — MCP correction
// proposals queue. Written only by `propose_hint`
// (mcp/proposals.py) and by the debugger's approve/reject endpoints
// (ui/vite.config.ts); read here for the Pending proposals panel.)
// ---------------------------------------------------------------------------

export type ProposalStatus = "pending" | "approved" | "rejected";

export interface ProposedHint {
  start: number;
  end: number;
  title: string;
  summary: string;
}

interface PendingProposalBase {
  id: string;
  status: ProposalStatus;
  created_at: string;
  rejection_reason: string | null;
  evidence: string;
}

export type PendingHintProposal = PendingProposalBase & {
  type: "hint";
  hint: ProposedHint;
  /** Operator-corrected start/end, set only when the times approved
   *  differ from `hint`'s proposed ones (ui/vite.config.ts's
   *  `normalizeProposalDecisionPayload`/PUT handler). `hint` itself is
   *  never mutated. */
  approved_hint?: { start: number; end: number };
};

/** One audio / web evidence kind of a `verdict_check`: what was read and what it showed. */
export interface VerdictCheckEvidenceItem {
  read: string;
  showed: string;
}

export const VERDICT_CHECK_EVIDENCE_KINDS = [
  "stems",
  "drum_density",
  "dropouts",
  "loudness",
  "web_search",
] as const;

export type VerdictCheckEvidenceKind = (typeof VERDICT_CHECK_EVIDENCE_KINDS)[number];

/** `verdict_check` queue row body (v3.11 item 23, mcp `write_verdict_check`). */
export interface VerdictCheckBody {
  field: string;
  claim: string;
  evidence: Record<VerdictCheckEvidenceKind, VerdictCheckEvidenceItem>;
  cannot_settle: string;
  question: string;
}

export type PendingVerdictCheckProposal = PendingProposalBase & {
  type: "verdict_check";
  verdict_check: VerdictCheckBody;
};

export type PendingProposal = PendingHintProposal | PendingVerdictCheckProposal;

export interface PendingProposalsFile {
  schema_version: string;
  song_name: string;
  proposals: PendingProposal[];
}

// ---------------------------------------------------------------------------
// reference/pre-analysis/verdict.json  (v3.11 items 21-24 — hint verdicts and
// the second pass over them; read-only here except `operator`, which only the
// approve flow of a `verdict_check` writes.)
// ---------------------------------------------------------------------------

export type VerdictOutcome = "confirmed" | "refuted" | "unresolved";

export interface VerdictOperatorAnswer {
  answer: "confirmed" | "rejected";
  reason: string | null;
  check_id: string | null;
}

export interface VerdictSecondPass {
  verdict: "confirmed" | "refuted" | null;
  wrong: "hint" | "analysis" | null;
  operator: VerdictOperatorAnswer | null;
}

export interface VerdictRow {
  field: string;
  verdict: VerdictOutcome;
  /** every section id the first-pass evidence names (`*_section_ids` keys), in file order */
  section_ids: string[];
  second_pass: VerdictSecondPass | null;
}

export interface VerdictFile {
  schema_version: string;
  song_name: string;
  rows: VerdictRow[];
}
