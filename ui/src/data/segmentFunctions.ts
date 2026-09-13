// segmentFunctions.ts — the Human Sections "function" dropdown vocabulary.
//
// Copied by hand from docs/segments-vocabulary.md (the canonical section-label
// vocabulary — keep this list in sync with that doc, not the other way round).
// A combined entry there ("Breakdown / Break", "Build-Up / Build",
// "Fill / Pre-Drop", "Chorus / Chorus (Inst)") becomes two separate names
// here that share one hint — the hint is a UI tooltip only and is never
// copied into segments.json.

export interface SegmentFunctionOption {
  name: string;
  hint: string;
}

export const SEGMENT_FUNCTIONS: SegmentFunctionOption[] = [
  { name: "Intro", hint: "Stripped-back beginning with basic percussion for DJs to beatmatch." },
  { name: "Outro", hint: "Stripped-back ending that fades out or reduces to basic drums for mixing out." },
  {
    name: "Verse",
    hint: "A recurring narrative or thematic section, typically lower in energy and focused on developing the song's lyrical or musical idea.",
  },
  {
    name: "Main",
    hint: "A primary musical section in arrangements that do not follow a conventional verse/chorus structure.",
  },
  { name: "Pre-Chorus", hint: "A transitional section that builds anticipation and leads into the chorus." },
  {
    name: "Chorus",
    hint: 'The main recurring hook or payoff section of a song; "Chorus (Inst)" is the same section without any significant vocal part.',
  },
  {
    name: "Chorus (Inst)",
    hint: 'The main recurring hook or payoff section of a song; "Chorus (Inst)" is the same section without any significant vocal part.',
  },
  {
    name: "Post-Chorus",
    hint: "A section immediately following the chorus, often extending its hook or energy without functioning as a full chorus.",
  },
  {
    name: "Refrain",
    hint: "A recurring lyrical or musical phrase that may function as a hook without constituting a full chorus.",
  },
  {
    name: "Breakdown",
    hint: "Drops the drums and bass out completely; focuses on melody, chords, and emotion.",
  },
  {
    name: "Break",
    hint: "Drops the drums and bass out completely; focuses on melody, chords, and emotion.",
  },
  { name: "Pre-Build", hint: "A transition zone between the breakdown and the actual build." },
  { name: "Build-Up", hint: "Ramps up the energy using snare rolls, risers, and pitch bends." },
  { name: "Build", hint: "Ramps up the energy using snare rolls, risers, and pitch bends." },
  {
    name: "Fill",
    hint: "The final 1 to 4 beats of silence, a vocal phrase, or a quick drum roll right before the beat hits.",
  },
  {
    name: "Pre-Drop",
    hint: "The final 1 to 4 beats of silence, a vocal phrase, or a quick drum roll right before the beat hits.",
  },
  { name: "Drop", hint: "A main high-energy chorus/peak of the track." },
  { name: "Extended Drop", hint: "Common in longer club formats or specific genres like Trance." },
  {
    name: "Bridge",
    hint: "A contrasting section that connects major parts of the song, often appearing later in the arrangement.",
  },
  {
    name: "Mid-Intro",
    hint: "Used in extended club mixes, a transition section after the first drop before the main breakdown.",
  },
];

export const SEGMENT_FUNCTION_NAMES: string[] = SEGMENT_FUNCTIONS.map((f) => f.name);
