// romanNumeral.ts — best-effort diatonic roman numeral for a chord symbol given
// a global key. Used by the `chords` sparse-lane adapter (roman only shown when
// the block is wide). Returns null when the key is unknown or the chord root
// isn't diatonic — the lane then falls back to the plain chord name.

const PITCH_CLASS: Record<string, number> = {
  C: 0, "C#": 1, DB: 1, D: 2, "D#": 3, EB: 3, E: 4, "E#": 5, FB: 4,
  F: 5, "F#": 6, GB: 6, G: 7, "G#": 8, AB: 8, A: 9, "A#": 10, BB: 10, B: 11, "B#": 0, CB: 11,
};

const MAJOR_STEPS = [0, 2, 4, 5, 7, 9, 11];
const MINOR_STEPS = [0, 2, 3, 5, 7, 8, 10];
const MAJOR_QUALITIES = ["", "m", "m", "", "", "m", "dim"];
const MINOR_QUALITIES = ["m", "dim", "", "m", "m", "", ""];
const NUMERALS = ["I", "II", "III", "IV", "V", "VI", "VII"];

export interface ParsedKey {
  tonicPc: number;
  minor: boolean;
}

/** "D# minor", "D#m", "Eb", "F# major" → { tonicPc, minor } */
export function parseKey(label: string | null | undefined): ParsedKey | null {
  if (!label) return null;
  const m = /^\s*([A-Ga-g][#b]?)\s*(.*)$/.exec(label.trim());
  if (!m) return null;
  const tonicPc = PITCH_CLASS[m[1]!.toUpperCase()];
  if (tonicPc === undefined) return null;
  const rest = m[2]!.toLowerCase();
  const minor = rest.startsWith("m") && !rest.startsWith("maj");
  return { tonicPc, minor };
}

/** chord root pitch class + whether the chord is minor/diminished */
function parseChordRoot(chord: string): { pc: number; minorish: boolean } | null {
  const m = /^\s*([A-Ga-g][#b]?)(.*)$/.exec(chord.trim());
  if (!m) return null;
  const pc = PITCH_CLASS[m[1]!.toUpperCase()];
  if (pc === undefined) return null;
  const rest = m[2]!.toLowerCase();
  const minorish =
    /^(m(?!aj)|min|dim|°|o\b)/.test(rest) || rest.includes("dim");
  return { pc, minorish };
}

export function romanNumeral(
  chord: string | null | undefined,
  keyLabel: string | null | undefined,
): string | null {
  if (!chord) return null;
  const key = parseKey(keyLabel);
  const root = parseChordRoot(chord);
  if (!key || !root) return null;

  const steps = key.minor ? MINOR_STEPS : MAJOR_STEPS;
  const quals = key.minor ? MINOR_QUALITIES : MAJOR_QUALITIES;
  const interval = (root.pc - key.tonicPc + 12) % 12;
  const degree = steps.indexOf(interval);
  if (degree === -1) return null;

  const diatonicMinor = quals[degree] === "m" || quals[degree] === "dim";
  let numeral = NUMERALS[degree]!;
  if (root.minorish || diatonicMinor) numeral = numeral.toLowerCase();
  if (quals[degree] === "dim") numeral += "°";
  return numeral;
}
