import { laneDefinitions } from "../config.js";
import { escapeHtml, formatDuration } from "../utils.js";

import { getTrackWidth, timeToPx } from "./shared.js";

function renderGridHtml(timeline, zoom) {
  if (!timeline) { return ""; }
  if (zoom >= 64) { return timeline.beats.map((beat) => `<span class="grid-line ${beat.beat_in_bar === 1 ? "downbeat" : ""}" style="left:${timeToPx(beat.time, timeline, zoom)}px"></span>`).join(""); }
  if (zoom >= 24) { return timeline.beats.filter((beat) => beat.beat_in_bar === 1).map((beat) => `<span class="grid-line downbeat" style="left:${timeToPx(beat.time, timeline, zoom)}px"></span>`).join(""); }
  return timeline.bars.filter((bar) => (Number(bar.bar) - 1) % 4 === 0).map((bar) => `<span class="grid-line measure" style="left:${timeToPx(bar.start_s, timeline, zoom)}px"></span>`).join("");
}

function renderRulerTicksHtml(timeline, zoom) {
  const barStep = zoom >= 64 ? 1 : zoom >= 32 ? 2 : zoom >= 18 ? 4 : 8;
  return timeline.bars.filter((bar) => (Number(bar.bar) - 1) % barStep === 0).map((bar) => `<span class="ruler-tick" style="left:${timeToPx(bar.start_s, timeline, zoom)}px">Bar ${escapeHtml(bar.bar)} · ${escapeHtml(formatDuration(bar.start_s))}</span>`).join("");
}

export function renderTimelineMarkup(timeline, laneVisibility, laneCollapsed, zoom) {
  if (!timeline) { return ""; }
  const width = getTrackWidth(timeline, zoom);
  const gridHtml = renderGridHtml(timeline, zoom);
  const rows = [`<div class="timeline-row ruler-row"><div class="lane-label"><h4>Timeline</h4><span class="lane-meta">Shared beat grid and bar ruler</span></div><div class="lane-track ruler-track" style="width:${width}px"><div class="grid-layer">${gridHtml}</div><div class="ruler-ticks">${renderRulerTicksHtml(timeline, zoom)}</div><div class="now-markers"><span class="now-marker" data-now-marker></span></div></div></div>`];
  for (const lane of laneDefinitions) {
    if (!laneVisibility[lane.id]) { continue; }
    const isCollapsed = Boolean(laneCollapsed?.[lane.id]);
    rows.push(`<div class="timeline-row${isCollapsed ? " lane-collapsed" : ""}" data-lane-row="${escapeHtml(lane.id)}"><div class="lane-label"><div class="lane-label-title-row"><h3>${escapeHtml(lane.label)}</h3><button type="button" class="lane-collapse-toggle" data-lane-toggle="${escapeHtml(lane.id)}" aria-expanded="${isCollapsed ? "false" : "true"}" aria-label="${isCollapsed ? "Expand" : "Collapse"} ${escapeHtml(lane.label)} lane" title="${isCollapsed ? "Expand" : "Collapse"} ${escapeHtml(lane.label)}">${isCollapsed ? "▸" : "▾"}</button></div><span class="lane-meta">${escapeHtml(lane.description)}</span></div>${isCollapsed ? "" : `<div class="lane-track" data-track-lane="${escapeHtml(lane.id)}" style="width:${width}px"><div class="grid-layer">${gridHtml}</div><div class="lane-content"><canvas class="lane-canvas" data-lane-canvas></canvas></div><div class="now-markers"><span class="now-marker" data-now-marker></span></div></div>`}</div>`);
  }
  return rows.join("");
}