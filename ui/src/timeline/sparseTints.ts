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
  dropProposals: [318, 72, 46], // magenta — deliberately unlike the amber of the
  //                               human hints it is auditioned against
  dropProposalsMatched: [168, 60, 40], // muted teal — a proposal that already
  //                                      matches a hand-authored drop impact
  // Wave-2 experiments (docs/experiments.md, run orders 1-3, 6).
  vocalPhrases: [340, 55, 46], // rose — distinct from moisesLyrics' slate blue
  vocalPhrasesGap: [220, 10, 40], // near-grey — an instrumental (no-vocal) span
  vocalPhrasesSustained: [280, 60, 48], // violet-pink — a held note marker
  arrangementState: [95, 55, 44], // olive-lime — distinct from vocalPhrases' rose
  //                                 (340) and dropProposals' magenta (318)
  arrangementStateSparse: [95, 25, 34], // same hue, dimmer + desaturated: a
  //                                       block where one stem or fewer is playing
  textureNovelty: [70, 60, 44], // chartreuse — distinct from arrangementState's
  //   olive-lime (95); v3.4 item 6 experiment lane
  //   (failed kill condition, kept for one review pass)
  phrasePeriodicity: [130, 55, 40], // emerald — distinct from textureNovelty's
  //   chartreuse (70) and arrangementState's olive-lime (95); v3.4 item 7
  //   experiment lane (passed its kill condition)
  structuralVsMicro: [245, 50, 52], // indigo — a `structural` block (edge locks
  //   to the 4-bar phrase grid). Distinct from every neighbour hue: textureNovelty
  //   70, phrasePeriodicity 130, moisesLyrics 210, character 275; v3.4 item 8
  //   experiment lane (failed its kill condition, kept for one review pass)
  structuralVsMicroMicro: [300, 62, 52], // magenta-purple — a `micro` cue that
  //   lives inside a phrase. Per-block tint override the adapter emits for
  //   kind === "micro"; precedent dropProposalsMatched
  gestures: [10, 75, 46], // burnt orange — sound-design device gestures
  sections: [174, 78, 38], // teal    (the previous app rgba(15,118,110))
  sectionsContested: [28, 90, 50], // vivid orange — a section whose allin1
  //   `function` label is kept but contradicted by the energy contest (v3.4
  //   item 3). Reads clearly against the Sections lane's teal blocks; precedent
  //   is `dropProposalsMatched`.
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
  chords: [193, 82, 44], // cyan    (the previous app rgba(14,116,144))
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
