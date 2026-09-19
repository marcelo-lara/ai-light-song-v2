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
  rhythmDrumIoi: [290, 55, 46], // violet — v3.6 item 5's three rhythm.* candidate
  //   producers get their own hue each; distinct from character's 275
  rhythmStemAutocorr: [309, 55, 48], // magenta-violet — distinct from
  //   rhythmDrumIoi's 290 and moisesLyricsValidated's 265
  rhythmVocalOnsets: [329, 55, 48], // pink-magenta — distinct from
  //   rhythmStemAutocorr's 309 and vocalPhrasesSustained's 280
  energyLevel: [350, 60, 46], // red-pink — v3.6 item 5's energy candidate
  //   producer; distinct from every neighbour hue in the 300-340 range above
  tensionShape: [227, 55, 46], // blue — v3.6 item 5's tension candidate
  segmentSeeds: [246, 55, 46], // indigo — the unreviewed seed tier below the five clue producers; distinct from tensionShape's blue (227) and moisesLyricsValidated's violet (265)
  //   producer; distinct from arrangementState's olive-lime (95)
  gestures: [10, 75, 46], // burnt orange — sound-design device gestures
  sections: [174, 78, 38], // teal    (the previous app rgba(15,118,110))
  sectionsContested: [28, 90, 50], // vivid orange — a section whose allin1
  //   `function` label is kept but contradicted by the energy contest (v3.4
  //   item 3). Reads clearly against the Sections lane's teal blocks; a
  //   per-block tint override.
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
