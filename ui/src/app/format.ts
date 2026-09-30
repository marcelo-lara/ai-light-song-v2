// format.ts — App.tsx's header-bar time formatters. Split out of App.tsx
// (v3.9 item 7) with no behaviour change.

export function formatClock(seconds: number): string {
  const safe = Math.max(0, seconds || 0);
  const m = Math.floor(safe / 60);
  const s = safe - m * 60;
  return `${m}:${s < 10 ? "0" : ""}${s.toFixed(1)}`;
}

export function formatSecondsFixed(seconds: number): string {
  return Math.max(0, seconds || 0).toFixed(2);
}
