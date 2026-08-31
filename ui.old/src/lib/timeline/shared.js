import { clamp } from "../utils.js";

export function timeToPx(time, timeline, zoom) {
  return clamp(Number(time) || 0, 0, timeline?.duration || 0) * zoom;
}

export function getTrackWidth(timeline, zoom) {
  return Math.max(Math.ceil(timeline.duration * zoom), 1);
}

export function getTrackCanvas(track) {
  return track?.querySelector("[data-lane-canvas]") || null;
}

export function getTrackContext(track, width, height) {
  const canvas = getTrackCanvas(track);
  if (!canvas) {
    return null;
  }
  const devicePixelRatio = globalThis.window?.devicePixelRatio || 1;
  canvas.width = Math.max(1, Math.round(width * devicePixelRatio));
  canvas.height = Math.max(1, Math.round(height * devicePixelRatio));
  canvas.style.width = `${width}px`;
  canvas.style.height = `${height}px`;
  const context = canvas.getContext("2d");
  if (!context) {
    return null;
  }
  context.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0);
  context.clearRect(0, 0, width, height);
  return context;
}

export function drawRoundedRect(context, x, y, width, height, radius) {
  const safeRadius = Math.min(radius, width / 2, height / 2);
  context.beginPath();
  context.moveTo(x + safeRadius, y);
  context.arcTo(x + width, y, x + width, y + height, safeRadius);
  context.arcTo(x + width, y + height, x, y + height, safeRadius);
  context.arcTo(x, y + height, x, y, safeRadius);
  context.arcTo(x, y, x + width, y, safeRadius);
  context.closePath();
}

export function trimCanvasText(context, text, maxWidth) {
  const value = String(text || "");
  if (!value || maxWidth <= 0 || context.measureText(value).width <= maxWidth) {
    return value;
  }
  let trimmed = value;
  while (trimmed.length > 1 && context.measureText(`${trimmed}…`).width > maxWidth) {
    trimmed = trimmed.slice(0, -1);
  }
  return `${trimmed}…`;
}