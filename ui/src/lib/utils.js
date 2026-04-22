export function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

export function clamp(value, minimum, maximum) {
  return Math.min(Math.max(value, minimum), maximum);
}

export function roundNumber(value, digits = 2) {
  return Number.isFinite(Number(value)) ? Number(value).toFixed(digits) : "-";
}

export function formatDuration(seconds) {
  const numeric = Number(seconds);
  if (!Number.isFinite(numeric)) {
    return "-";
  }
  const minutes = Math.floor(numeric / 60);
  const remainder = numeric - (minutes * 60);
  return `${minutes}:${remainder.toFixed(1).padStart(4, "0")}`;
}

export function formatRange(start, end) {
  return `${formatDuration(start)}-${formatDuration(end)}`;
}

export function formatPercent(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return "-";
  }
  return `${(numeric * 100).toFixed(1)}%`;
}

export function encodePath(parts) {
  return "/" + parts.map((part) => encodeURIComponent(part)).join("/");
}

export function summarizeValidation(report) {
  if (!report || typeof report !== "object") {
    return "missing";
  }
  return report.status || "present";
}