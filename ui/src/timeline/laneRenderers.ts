// laneRenderers.ts — the per-`kind` canvas painters for the data lanes.
// Straight port of the previous app's src/lib/timeline/{fftBandsLane,loudnessLane,
// waveformLane,drumsLane,seriesLane}.js — geometry maths live in
// laneGeometry.ts, colours in palette.ts.

import type { FftBands, LoudnessSeries } from "../data/types";

import {
  bucketDrums,
  bucketLevels,
  bucketSeconds,
  DRUM_MARKER_PXPERSEC,
  envelopeRowGeometry,
  fftBandRows,
  fftVisibleIntensity,
  rmsVisibleIntensity,
  stemRows,
  subLabelX,
} from "./laneGeometry";
import { bandColor, CAPTION_FONT, clamp01, sourceColor, sourceRgb } from "./palette";

export interface RenderCtx {
  ctx: CanvasRenderingContext2D;
  /** css px — full body width (= coords.timelineW) */
  width: number;
  height: number;
  pxPerSec: number;
  timeToX: (time: number) => number;
  /** seconds visible at the left / right edge of the scroll viewport */
  visibleStart: number;
  visibleEnd: number;
  /** scrollLeft / pxPerSec (seconds) — the viewport's left edge */
  scrollStart: number;
}

export interface LaneMarker {
  laneId: string;
  id: string;
  time: number;
  kind: string;
  intensity?: number;
  raw: unknown;
}

export interface HitRegion {
  x1: number;
  x2: number;
  y1: number;
  y2: number;
  marker: LaneMarker;
}

function metadataSeconds(
  metadata: Record<string, unknown> | null | undefined,
  keys: string[],
  fallback: number,
): number {
  const md = metadata ?? {};
  for (const key of keys) {
    const ms = Number((md as Record<string, unknown>)[key]);
    if (Number.isFinite(ms) && ms > 0) return ms / 1000;
  }
  return fallback;
}

// ---------------------------------------------------------------------------
// FFT
// ---------------------------------------------------------------------------

export function drawFft(rc: RenderCtx, fft: FftBands): void {
  const { ctx } = rc;
  const bandCount = fft.bands.length;
  if (!bandCount || !fft.frames.length) return;

  const intervalSeconds = metadataSeconds(fft.metadata, ["interval_ms"], 0.05);
  const secs = bucketSeconds(intervalSeconds, rc.pxPerSec, 0.05);
  const buckets = bucketLevels(
    fft.frames,
    bandCount,
    secs,
    rc.visibleStart - 1,
    rc.visibleEnd + 1,
  );
  const rows = fftBandRows(bandCount, rc.height, 6, 6);

  ctx.save();
  for (const bucket of buckets) {
    const left = Math.floor(rc.timeToX(bucket.start_s));
    const right = Math.ceil(rc.timeToX(bucket.end_s));
    const w = Math.max(1, right - left);
    for (let bandIndex = 0; bandIndex < bandCount; bandIndex += 1) {
      const visible = fftVisibleIntensity(bucket.maxes[bandIndex] ?? 0);
      if (visible === null) continue;
      const row = rows[bandIndex]!;
      ctx.fillStyle = bandColor(bandIndex, visible);
      ctx.fillRect(left, row.top, w, row.height);
    }
  }
  ctx.restore();
}

// ---------------------------------------------------------------------------
// RMS + Envelope
// ---------------------------------------------------------------------------

function drawStemRow(
  ctx: CanvasRenderingContext2D,
  rowTop: number,
  rowHeight: number,
  width: number,
): void {
  ctx.fillStyle = "rgba(148, 163, 184, 0.06)";
  ctx.fillRect(0, rowTop, width, rowHeight);
  ctx.strokeStyle = "rgba(148, 163, 184, 0.16)";
  ctx.beginPath();
  ctx.moveTo(0, rowTop + rowHeight + 0.5);
  ctx.lineTo(width, rowTop + rowHeight + 0.5);
  ctx.stroke();
}

function drawSourceLabel(
  rc: RenderCtx,
  label: string,
  rowTop: number,
  sourceIndex: number,
): void {
  const { ctx } = rc;
  ctx.font = CAPTION_FONT;
  const trimmed = trimText(ctx, label || `Source ${sourceIndex + 1}`, 56);
  const textWidth = ctx.measureText(trimmed).width;
  const x = subLabelX(rc.scrollStart, rc.pxPerSec);
  ctx.fillStyle = "rgba(10, 18, 28, 0.68)";
  ctx.fillRect(x - 2, rowTop + 2, textWidth + 6, 13);
  const [r, g, b] = sourceRgb(sourceIndex);
  ctx.fillStyle = `rgba(${r}, ${g}, ${b}, 0.9)`;
  ctx.fillText(trimmed, x, rowTop + 11);
}

function trimText(
  ctx: CanvasRenderingContext2D,
  text: string,
  maxWidth: number,
): string {
  if (!text || ctx.measureText(text).width <= maxWidth) return text;
  let out = text;
  while (out.length > 1 && ctx.measureText(`${out}…`).width > maxWidth) {
    out = out.slice(0, -1);
  }
  return `${out}…`;
}

export function drawLoudness(
  rc: RenderCtx,
  series: LoudnessSeries,
  mode: "rms" | "env",
): void {
  const { ctx } = rc;
  const sources = series.sources;
  if (!sources.length || !series.frames.length) return;

  const windowSeconds = metadataSeconds(
    series.metadata,
    ["interval_ms", "window_ms"],
    mode === "rms" ? 0.01 : 0.2,
  );
  const secs = bucketSeconds(windowSeconds, rc.pxPerSec, mode === "rms" ? 0.01 : 0.2);
  const buckets = bucketLevels(
    series.frames,
    sources.length,
    secs,
    rc.visibleStart - 1,
    rc.visibleEnd + 1,
  );
  const rows = stemRows(rc.height, sources.length, 5, 5, 2);

  ctx.save();
  for (let i = 0; i < sources.length; i += 1) {
    const { rowTop, rowHeight } = rows[i]!;
    drawStemRow(ctx, rowTop, rowHeight, rc.width);
    if (mode === "rms") {
      for (const bucket of buckets) {
        const visible = rmsVisibleIntensity(bucket.maxes[i] ?? 0);
        if (visible === null) continue;
        const left = rc.timeToX(bucket.start_s);
        const w = Math.max(1, rc.timeToX(bucket.end_s) - left);
        ctx.fillStyle = sourceColor(i, 0.16 + visible * 0.72);
        ctx.fillRect(left, rowTop + 1, w, Math.max(1, rowHeight - 2));
      }
    } else {
      drawEnvelopeTrace(rc, buckets, i, rowTop, rowHeight);
    }
    drawSourceLabel(rc, sources[i]!.label, rowTop, i);
  }
  ctx.restore();
}

function drawEnvelopeTrace(
  rc: RenderCtx,
  buckets: ReturnType<typeof bucketLevels>,
  sourceIndex: number,
  rowTop: number,
  rowHeight: number,
): void {
  const { ctx } = rc;
  const rows = buckets.filter(
    (bucket) => (Number(bucket.averages[sourceIndex]) || 0) > 0,
  );
  if (!rows.length) return;
  const { baseline, amplitude } = envelopeRowGeometry(rowTop, rowHeight);
  const midX = (bucket: (typeof rows)[number]): number =>
    rc.timeToX((bucket.start_s + bucket.end_s) / 2);
  const y = (bucket: (typeof rows)[number]): number =>
    baseline - clamp01(Number(bucket.averages[sourceIndex]) || 0) * amplitude;

  ctx.beginPath();
  ctx.moveTo(rc.timeToX(rows[0]!.start_s), baseline);
  for (const bucket of rows) ctx.lineTo(midX(bucket), y(bucket));
  ctx.lineTo(rc.timeToX(rows[rows.length - 1]!.end_s), baseline);
  ctx.closePath();
  ctx.fillStyle = sourceColor(sourceIndex, 0.18);
  ctx.fill();

  ctx.beginPath();
  rows.forEach((bucket, index) => {
    if (index === 0) ctx.moveTo(midX(bucket), y(bucket));
    else ctx.lineTo(midX(bucket), y(bucket));
  });
  ctx.strokeStyle = sourceColor(sourceIndex, 0.94);
  ctx.lineWidth = 1.5;
  ctx.stroke();
}

// ---------------------------------------------------------------------------
// Drums (kick / snare / hat density)
// ---------------------------------------------------------------------------

export interface DrumEventRow {
  id: string;
  time: number;
  end_s: number;
  event_type: string;
}

export function drawDrums(
  rc: RenderCtx,
  events: readonly DrumEventRow[],
  laneId: string,
): HitRegion[] {
  const { ctx } = rc;
  const hits: HitRegion[] = [];
  ctx.save();
  if (rc.pxPerSec >= DRUM_MARKER_PXPERSEC) {
    const typeY: Record<string, number> = { kick: 58, snare: 38, hat: 18, unresolved: 68 };
    const typeColor: Record<string, string> = {
      kick: "rgba(15, 118, 110, 0.9)",
      snare: "rgba(185, 28, 28, 0.9)",
      hat: "rgba(202, 138, 4, 0.9)",
      unresolved: "rgba(107, 114, 128, 0.8)",
    };
    for (const ev of events) {
      if (ev.time < rc.visibleStart - 1.5 || ev.time > rc.visibleEnd + 1.5) continue;
      const x = rc.timeToX(ev.time);
      const cy = typeY[ev.event_type] ?? 68;
      ctx.strokeStyle = typeColor[ev.event_type] ?? typeColor.unresolved!;
      ctx.beginPath();
      ctx.moveTo(x, cy - 10);
      ctx.lineTo(x, cy + 10);
      ctx.stroke();
      hits.push({
        x1: x - 4,
        x2: x + 4,
        y1: cy - 10,
        y2: cy + 10,
        marker: { laneId, id: ev.id, time: ev.time, kind: "drum", raw: ev },
      });
    }
    ctx.restore();
    return hits;
  }
  const secs = Math.max(0.2, 14 / Math.max(rc.pxPerSec, 1));
  const buckets = bucketDrums(events, secs, rc.visibleStart - 1, rc.visibleEnd + 1);
  const maxCount = Math.max(1, ...buckets.map((b) => b.count));
  for (const bucket of buckets) {
    const left = rc.timeToX(bucket.start_s);
    const w = Math.max(1, rc.timeToX(bucket.end_s) - left);
    const kickH = (bucket.byType.kick / maxCount) * 24;
    const snareH = (bucket.byType.snare / maxCount) * 18;
    const hatH = (bucket.byType.hat / maxCount) * 16;
    ctx.fillStyle = "rgba(15, 118, 110, 0.85)";
    ctx.fillRect(left, 78 - kickH, w, kickH);
    ctx.fillStyle = "rgba(185, 28, 28, 0.82)";
    ctx.fillRect(left, 52 - snareH, w, snareH);
    ctx.fillStyle = "rgba(202, 138, 4, 0.84)";
    ctx.fillRect(left, 28 - hatH, w, hatH);
  }
  ctx.restore();
  return hits;
}

// ---------------------------------------------------------------------------
// Energy (beat-aligned energy + accent candidates)
// ---------------------------------------------------------------------------

export interface EnergyBeatRow {
  start_s: number;
  end_s: number;
  value: number;
}

export interface AccentCandidate {
  id: string;
  time: number;
  intensity: number;
  kind: string;
  raw?: unknown;
}

export function drawEnergy(
  rc: RenderCtx,
  beatRows: readonly EnergyBeatRow[],
  accents: readonly AccentCandidate[],
  laneId: string,
): HitRegion[] {
  const { ctx } = rc;
  const hits: HitRegion[] = [];
  const baseline = rc.height - 8;
  const amplitude = rc.height - 18;
  const rows = beatRows.filter(
    (r) => r.end_s >= rc.visibleStart - 4 && r.start_s <= rc.visibleEnd + 4,
  );

  ctx.save();
  if (rows.length) {
    const midX = (r: EnergyBeatRow): number =>
      rc.timeToX((r.start_s + r.end_s) / 2);
    ctx.beginPath();
    ctx.moveTo(rc.timeToX(rows[0]!.start_s), baseline);
    for (const r of rows) {
      ctx.lineTo(midX(r), baseline - clamp01(r.value) * amplitude);
    }
    ctx.lineTo(rc.timeToX(rows[rows.length - 1]!.end_s), baseline);
    ctx.closePath();
    ctx.fillStyle = "rgba(14, 116, 144, 0.16)";
    ctx.fill();
    ctx.strokeStyle = "rgba(14, 116, 144, 0.72)";
    ctx.lineWidth = 1.4;
    ctx.stroke();
  }

  ctx.fillStyle = "rgba(185, 28, 28, 0.8)";
  for (const accent of accents) {
    if (accent.time < rc.visibleStart - 2 || accent.time > rc.visibleEnd + 2) continue;
    const x = rc.timeToX(accent.time);
    const y = 72 - clamp01(accent.intensity) * 52;
    ctx.beginPath();
    ctx.arc(x, y, 3.6, 0, Math.PI * 2);
    ctx.fill();
    hits.push({
      x1: x - 5,
      x2: x + 5,
      y1: y - 5,
      y2: y + 5,
      marker: {
        laneId,
        id: accent.id,
        time: accent.time,
        kind: "accent",
        intensity: accent.intensity,
        raw: accent.raw ?? accent,
      },
    });
  }
  ctx.restore();
  return hits;
}

// ---------------------------------------------------------------------------
// Collapsed strip (26px faint summary)
// ---------------------------------------------------------------------------

export function drawCollapsedStrip(
  rc: RenderCtx,
  samples: ReadonlyArray<{ t: number; v: number }>,
): void {
  const { ctx } = rc;
  if (!samples.length) return;
  const baseline = rc.height - 2;
  const amplitude = rc.height - 5;
  ctx.save();
  ctx.beginPath();
  ctx.moveTo(rc.timeToX(samples[0]!.t), baseline);
  for (const s of samples) {
    ctx.lineTo(rc.timeToX(s.t), baseline - clamp01(s.v) * amplitude);
  }
  ctx.lineTo(rc.timeToX(samples[samples.length - 1]!.t), baseline);
  ctx.closePath();
  ctx.fillStyle = "rgba(148, 163, 184, 0.14)";
  ctx.fill();
  ctx.restore();
}
