// shared.ts — formatting helpers used by every laneContent/* family module.
// Ported from the previous app's src/lib/utils.js (see laneContent.ts's own header).

export function fmtTime(seconds: number): string {
  const n = Number(seconds);
  if (!Number.isFinite(n)) return "-";
  const m = Math.floor(n / 60);
  return `${m}:${(n - m * 60).toFixed(1).padStart(4, "0")}`;
}

export function formatRange(start: number, end: number): string {
  return `${fmtTime(start)}–${fmtTime(end)}`;
}

export function round(v: number | null | undefined, digits = 2): string {
  return v == null || !Number.isFinite(Number(v)) ? "-" : Number(v).toFixed(digits);
}
