// palette.ts — lane fill colours + fonts, carried over VERBATIM from
// the previous app's src/lib/timeline/{fftBandsLane,loudnessLane,constants}.js
// (design notes §3a). These are NOT re-derived from Nocturne's accent ramp —
// the shipped debugger's spectral / per-stem palette is the authority for the
// FFT / RMS / Envelope lanes and their stem sub-labels.

export const clamp01 = (value: number): number =>
  value < 0 ? 0 : value > 1 ? 1 : value;

/** Sub … Brilliance — one hue per FFT band, fallback 196 for any index ≥ 7. */
export const FFT_BAND_HUES = [22, 46, 88, 138, 164, 186, 196] as const;

export const bandColor = (bandIndex: number, intensity: number): string => {
  const hue = FFT_BAND_HUES[bandIndex] ?? 196;
  return `hsla(${hue}, 84%, 58%, ${clamp01(intensity) * 0.9})`;
};

/** Mix / Bass / Drums / Harmonic / Vocals — index-aligned with `sources[]`. */
export const SOURCE_COLORS: ReadonlyArray<readonly [number, number, number]> = [
  [250, 204, 21], // Mix    — yellow-400
  [248, 113, 113], // Bass   — red-400
  [34, 211, 238], // Drums  — cyan-400
  [74, 222, 128], // Harmonic — green-400
  [192, 132, 252], // Vocals — purple-400
];

export const sourceRgb = (
  sourceIndex: number,
): readonly [number, number, number] =>
  SOURCE_COLORS[sourceIndex] ?? SOURCE_COLORS[SOURCE_COLORS.length - 1]!;

const roundAlpha = (value: number): number =>
  Math.round(clamp01(value) * 1000) / 1000;

/** `rgba(stem, a)` for the RMS heatmap / envelope fill + stroke. */
export const sourceColor = (sourceIndex: number, alpha: number): string => {
  const [r, g, b] = sourceRgb(sourceIndex);
  return `rgba(${r}, ${g}, ${b}, ${roundAlpha(alpha)})`;
};

export const CAPTION_FONT = '11px "IBM Plex Mono", monospace';

/** Lane body heights (px). Collapsed is always 26. */
export const LANE_HEIGHTS = {
  fft: 84,
  rms: 112,
  env: 112,
  hints: 58,
  collapsed: 26,
} as const;
