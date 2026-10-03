// sparseTints.ts — per-lane block tints for SparseLane (replaces the previous app's
// `sparseLaneStyles` table).
//
// The hue assignments are carried over from the previous app — hints amber, sections
// teal, chords cyan, identifiers blue, machine red, ml violet —
// but instead of hand-written rgba
// quads the values are now derived from one documented base hue per lane
// (`BASE_HUE`) plus a fixed alpha ramp (`FILL_A` / `STROKE_A`). Canvas needs
// concrete colour strings, so these resolve to `hsl()` / `hsla()` here rather
// than Nocturne CSS custom properties; the label + caption inks are the shared
// Nocturne foreground tokens' literal values.

export interface SparseTint {
  /** rounded-rect fill */
  fill: string;
  /** rounded-rect 1px stroke */
  stroke: string;
  /** block label ink */
  label: string;
  /** block caption ink */
  caption: string;
}

/** documented base hue (deg) + saturation (%) per lane id */
const BASE: Record<string, [hue: number, sat: number, light: number]> = {
  humanHints: [35, 92, 48], // amber   (the previous app rgba(217,119,6))
  humanHintsReview: [205, 80, 55], // azure — a hint seeded from an
  //   experiment/event block for review, distinct from a hand-authored
  //   hint's amber
  humanHintsVocal: [118, 65, 36], // warm green — a voice sounds continuously
  //   across the span (voice = alive/present); distinct from humanHints'
  //   amber (35), humanHintsReview's azure (205), and every green-ish hue
  //   elsewhere in this file (arrangementState 95,
  //   characterVocalLead/moisesLyricsHigh 150)
  llmPendingProposals: [245, 70, 58], // indigo — a proposal still awaiting an
  //   operator decision (mcp/propose_hint), auditioning against humanHints'
  //   amber (35) directly above it; distinct from moisesLyricsValidated's
  //   265 (it does not co-occur with this lane)
  // v3.11 item 24 — Verdict Checks: one tint per outcome (the operator's
  // answer, else a settled second pass, else the first pass).
  verdictConfirmed: [150, 60, 40], // green — the hint's claim holds
  verdictRefuted: [0, 72, 46], // red — the claim does not hold
  verdictUnresolved: [43, 88, 46], // amber — evidence could not answer it
  verdictChecks: [43, 30, 40], // lane fallback base, never drawn on a row
  humanSections: [55, 85, 46], // golden yellow — the operator's own hand-authored
  //   segmentation, deliberately near humanHints' amber (35, same "hand-authored"
  //   family) but distinct from it and from the production Sections lane's
  //   teal (174)
  moisesSections: [160, 55, 42], // seafoam — the Moises.ai reference
  //   segmentation, read-only; distinct from humanSections' gold (55),
  //   moisesLyrics' slate blue (210), and the fused Sections lane's teal (174)
  allin1Sections: [90, 45, 42], // olive — our own pre-fusion segmentation,
  //   distinct from humanSections (55), moisesSections (160) and the fused
  //   Sections lane's teal (174)
  // Wave-2 experiments (docs/experiments.md, run orders 1-3, 6).
  vocalPhrases: [340, 55, 46], // rose — distinct from moisesLyrics' slate blue
  vocalPhrasesGap: [220, 10, 40], // near-grey — an instrumental (no-vocal) span
  vocalPhrasesSustained: [280, 60, 48], // violet-pink — a held note marker
  allin1Posterior: [130, 50, 44], // spring green — distinct from allin1Sections'
  //   olive (90) and moisesSections' seafoam (160); hue 130 is free since the
  //   phrase_periodicity lane that previously used it was retired 2026-09-17
  stemPresenceSections: [70, 55, 45], // yellow-green — distinct from
  //   humanSections' gold (55) and allin1Sections' olive (90) either side of it
  vocalCadence: [190, 55, 44], // cyan-teal — a line block; distinct from
  //   sections' teal (174) and humanHintsReview's azure (205) either side
  vocalCadenceCall: [140, 60, 46], // green — a call point marker, deliberately
  //   distinct in hue AND shape (zero-length) from the vocalCadence line
  //   blocks above; also distinct from allin1Posterior's spring green (130)
  //   and characterVocalLead's green (150)
  // v3.5 item 7 — whisperX's VAD front-end (speech-domain, VAD-only —
  // diarization not attempted, no HF_TOKEN in this environment). Hue 20
  // (amber-orange) sits between gestures' burnt orange (10) and humanHints'
  // amber (35) — distinguished from both by this lane's own intensity ramp
  // and by never co-occurring with either lane's block shape. The overlaid
  // `vocal_phrase` hue (80, yellow-green) sits below
  // arrangementState (95) for the same reason. This candidate's phrase spans
  // carry real sub-second onsets (Binarize hysteresis, not a 5s clip window)
  // — see model.py.
  whisperxVadVeryLow: [20, 20, 20],
  whisperxVadLow: [20, 40, 28],
  whisperxVadMid: [20, 60, 38],
  whisperxVadHigh: [20, 80, 46],
  whisperxVadVeryHigh: [20, 95, 54],
  whisperxVadPhrase: [80, 60, 42],
  arrangementState: [95, 55, 44], // olive-lime — distinct from vocalPhrases' rose
  //                                 (340)
  arrangementStateSparse: [95, 25, 34], // same hue, dimmer + desaturated: a
  //                                       block where one stem or fewer is playing
  gestures: [10, 75, 46], // burnt orange — sound-design device gestures
  sections: [174, 78, 38], // teal    (the previous app rgba(15,118,110))
  // Character blocks are tinted by *kind*, so a song's texture reads as a
  // colour strip before any label is. Violet for `breath` is not arbitrary —
  // it is the look the operator wrote for the block this lane was built to
  // find ("parcans slow violet waves").
  character: [275, 55, 44],
  characterBreath: [275, 60, 46],
  characterVoid: [214, 28, 38],
  characterVocalLead: [150, 55, 38],
  characterFullPower: [12, 80, 45],
  characterShadow: [96, 34, 34], // allin1's family hue, muted: a losing label
  //                                with sustained posterior mass
  // Vocal transcription: the whisper baseline is a warm neutral, the singing
  // models a brighter amber against it, structure tags a muted variant.
  // Moises' external word-level lyrics. Each token is tinted by the confidence
  // Moises reported for it, on a green → amber → red ramp, so shaky stretches
  // of the transcription read at a glance; the line markers get a cool slate,
  // and `moisesLyrics` is the lane's fallback base.
  moisesLyrics: [210, 40, 44],
  moisesLyricsHigh: [150, 60, 40],
  moisesLyricsMid: [43, 88, 46],
  moisesLyricsLow: [0, 72, 46],
  moisesLyricsUnscored: [210, 12, 40],
  moisesLyricsMarker: [210, 30, 34],
  // v3.4 item 5 — a token the operator has hand-verified. Deliberately NOT the
  // `≥ 0.7` "High" bucket (150, green): a bright indigo, unlike every Moises
  // confidence tint, so a validated token reads as validated at a glance and
  // is never mistaken for Moises' own 0.99s. Applies in both the panel card
  // and the timeline lane.
  moisesLyricsValidated: [265, 80, 56],
  vocalTranscription: [32, 45, 42],
  vocalTranscriptionBaseline: [28, 20, 40],
  vocalTranscriptionModel: [32, 80, 46],
  vocalTranscriptionStructure: [32, 30, 34],
  // v3.7 item 1 — a block review's verdict, applied as a tint OVERRIDE on top
  // of whatever a reviewed block's own lane tint would be, so coverage reads
  // at a glance without opening the inspector. A fixed green/red/amber
  // vocabulary shared across every reviewable lane (docs/product-
  // refinement-v3.7.md item 1) — deliberately NOT reused from any producer
  // hue above, since a verdict is a judgement ON a block, not a lane identity.
  blockReviewCorrect: [150, 60, 40], // green — real and correctly described
  blockReviewWrong: [0, 72, 46], // red — a phantom, nothing is here
  blockReviewMisplaced: [43, 88, 46], // amber — real, but this block gets it wrong
  // v3.9 item 2 + the "crash over-fires" bug — per-hit drum-label accuracy
  // checks. clapEvents is a detection lane (no keep/reject split, every row
  // is a positive). kickCheck/crashCheck carry a keep/reject verdict per
  // row, tinted green/red so the split reads without opening the inspector —
  // deliberately different hues from blockReview's green/red (150/0) since
  // these are a different lane family's own verdict, not a block review.
  clapEvents: [235, 55, 46], // periwinkle — distinct from vocalCadence (190),
  //   moisesLyrics (210) and allin1Posterior (130)
  kickCheckKeep: [105, 55, 40], // green — a kick that keeps its label
  kickCheckReject: [5, 70, 46], // red-orange — a kick relabelled away
  // v3.12 item 29 — kick attacks on the mix. Echo and off-grid rows read apart.
  kickAttacks: [150, 60, 40], // green — a kick attack on the grid
  kickAttacksOffGrid: [150, 30, 30], // dusky green — beyond 1/4 beat from the grid, low confidence
  kickAttacksEcho: [0, 0, 40], // grey — weaker, duller repeat of an earlier attack
  crashCheckKeep: [168, 55, 40], // teal-green — an isolated accent kept
  crashCheckReject: [355, 65, 46], // red — a stream member rejected
  // v3.10 item 14 — filter sweeps. One lane; the tint only splits direction
  // so an opening (brightening) sweep reads apart from a closing one.
  filterSweepOpening: [310, 55, 48], // magenta — distinct from vocalPhrases'
  //   rose (340) and characterShadow/vocalPhrasesSustained violets (265-280)
  filterSweepClosing: [310, 30, 36], // dusky magenta — same hue, darker/greyer
  // v3.12 item 1 — bar features. Tinted by the bar's brightness tercile within
  // the song (low / mid / high); a bar that is not 4 beats long is grey.
  barFeaturesLow: [200, 35, 30], // slate blue — dark bar
  barFeaturesMid: [200, 50, 40],
  barFeaturesHigh: [190, 70, 52], // bright cyan — bright bar
  barFeaturesIrregular: [200, 5, 36], // grey — bar length != 4 beats (grid slip)
  // v3.12 item 30 — downbeat reanchor: a bar whose downbeat has agreeing anchors vs. none/disagreeing.
  downbeatReanchor: [30, 60, 42], // amber — resolved downbeat
  downbeatReanchorUnresolved: [30, 5, 36], // grey — confidence null (anchors disagree or none)
  // v3.12 item 31 — filter sweeps v2. Tinted by aftermath: a sweep end followed by
  // nothing (`none`) is a suspect detection and reads grey.
  filterSweepV2Gap: [310, 60, 50], // magenta — sweep end followed by a gap
  filterSweepV2Drop: [330, 70, 52], // hot pink — followed by a drop
  filterSweepV2Break: [290, 50, 44], // violet-magenta — followed by a break
  filterSweepV2None: [310, 10, 36], // grey — nothing follows, suspect
  // v3.12 item 2 — light changes. One tint per role.
  lightChangeGrooveIn: [140, 55, 42], // green
  lightChangeBuild: [45, 75, 50], // amber
  lightChangeBreak: [225, 55, 45], // blue
  lightChangeDrop: [355, 70, 50], // red
  lightChangeGap: [260, 10, 30], // dark grey-violet
  lightChangeFill: [300, 45, 48], // purple
  lightChangeUnknown: [0, 0, 40], // grey — a change point no role rule claimed
  // v3.10 item 15 — phrases. One lane; the tint only marks a phrase whose edge
  // evidence disagrees (`resolved: false`) in grey, so it reads apart at a glance.
  phrases: [20, 60, 44], // burnt orange — distinct from gestures (10) by lane kind
  phrasesUnresolved: [20, 10, 38], // desaturated — evidence for an edge disagrees
  // v3.10 item 17 — section names. The tint only marks rows that are NOT the
  // experiment's own naming (the current sections.json labels it kept), in grey.
  sectionNames: [250, 45, 46], // indigo — distinct from clapEvents (235) / llm proposals (245) by sat/lightness
  sectionNamesKept: [250, 8, 38], // desaturated — the current label, kept and attributed
};

/** fixed alpha ramp shared by every lane */
const FILL_A = 0.16;
const STROKE_A = 0.3;

/** shared Nocturne foreground inks (literal values of the CSS tokens) */
const LABEL_INK = "rgba(233, 233, 237, 0.96)";
const CAPTION_INK = "rgba(201, 200, 208, 0.82)";

function tintFor(id: string): SparseTint {
  const [h, s, l] = BASE[id] ?? BASE.sections!;
  return {
    fill: `hsla(${h}, ${s}%, ${l}%, ${FILL_A})`,
    stroke: `hsla(${h}, ${s}%, ${l}%, ${STROKE_A})`,
    label: LABEL_INK,
    caption: CAPTION_INK,
  };
}

export const SPARSE_TINTS: Record<string, SparseTint> = Object.fromEntries(
  Object.keys(BASE).map((id) => [id, tintFor(id)]),
);

export function sparseTint(laneId: string): SparseTint {
  return SPARSE_TINTS[laneId] ?? tintFor("sections");
}

/** discrete-mark colours for the validation (regression overlay) lane */
export const VALIDATION_MARK_COLORS: Record<string, string> = {
  exact: "hsla(174, 78%, 38%, 0.72)",
  shifted: "hsla(43, 96%, 40%, 0.78)",
  not_exported: "hsla(0, 74%, 42%, 0.78)",
  output_only: "hsla(201, 96%, 40%, 0.72)",
};
