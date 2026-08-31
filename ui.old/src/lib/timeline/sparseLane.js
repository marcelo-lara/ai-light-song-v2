import { formatRange } from "../utils.js";

import { CAPTION_FONT, LABEL_FONT, sparseLaneStyles, TRACK_HEIGHT, TRACK_PADDING } from "./constants.js";
import { buildSparseLaneContent } from "./sparseContent.js";
import { drawRoundedRect, getTrackContext, getTrackWidth, timeToPx, trimCanvasText } from "./shared.js";

function buildSparseRegions(laneId, timeline, zoom) {
  const overlapCompactLaneIds = new Set(["identifierHints", "machineEvents", "mlEvents", "phrases"]);
  const top = TRACK_PADDING;
  const availableHeight = TRACK_HEIGHT - (TRACK_PADDING * 2);
  const baseRegions = buildSparseLaneContent(laneId, timeline).map((item) => ({ x: timeToPx(item.start_s, timeline, zoom), width: Math.max(2, timeToPx(item.end_s, timeline, zoom) - timeToPx(item.start_s, timeline, zoom)), selection: { laneLabel: item.laneLabel, label: item.label, start_s: Number(item.start_s), end_s: Number(item.end_s), reference: item.reference || item.id || "-", detail: item.detail || "-", summary: item.summary || "", caption: item.caption || "" }, caption: item.caption || formatRange(item.start_s, item.end_s) }));
  if (!overlapCompactLaneIds.has(laneId) || baseRegions.length <= 1) {
    return baseRegions.map((region) => ({ ...region, y: top, height: availableHeight }));
  }
  const sortedRegions = [...baseRegions].sort((left, right) => left.x !== right.x ? left.x - right.x : left.width - right.width);
  const rowEnds = [];
  let maxOverlap = 1;
  for (const region of sortedRegions) {
    const rowIndex = rowEnds.findIndex((endX) => region.x >= endX);
    region.rowIndex = rowIndex === -1 ? rowEnds.length : rowIndex;
    rowEnds[region.rowIndex] = region.x + region.width;
    maxOverlap = Math.max(maxOverlap, region.rowIndex + 1);
  }
  const rowGap = maxOverlap > 1 ? 4 : 0;
  const rowHeight = Math.max(14, (availableHeight - (rowGap * Math.max(maxOverlap - 1, 0))) / maxOverlap);
  return sortedRegions.map((region) => ({ ...region, y: top + (region.rowIndex * (rowHeight + rowGap)), height: rowHeight }));
}

export function drawSparseLane(track, laneId, timeline, zoom) {
  const context = getTrackContext(track, getTrackWidth(timeline, zoom), TRACK_HEIGHT);
  if (!context) {
    return;
  }
  const regions = buildSparseRegions(laneId, timeline, zoom);
  context.save();
  context.textBaseline = "top";
  context.lineWidth = 1;
  for (const region of regions) {
    const contentWidth = Math.max(region.width - 20, 0);
    drawRoundedRect(context, region.x, region.y, region.width, region.height, region.height <= 22 ? 8 : 12);
    context.fillStyle = (sparseLaneStyles[laneId] || sparseLaneStyles.sections).fill;
    context.fill();
    context.strokeStyle = (sparseLaneStyles[laneId] || sparseLaneStyles.sections).stroke;
    context.stroke();
    if (region.width < 36) { continue; }
    context.font = LABEL_FONT;
    context.fillStyle = (sparseLaneStyles[laneId] || sparseLaneStyles.sections).text;
    context.fillText(trimCanvasText(context, region.selection.label, contentWidth), region.x + 10, region.height <= 24 ? region.y + Math.max(4, (region.height - 12) / 2) : region.y + 8);
    if (region.width >= 96 && region.height > 30) {
      context.font = CAPTION_FONT;
      context.fillStyle = (sparseLaneStyles[laneId] || sparseLaneStyles.sections).caption;
      context.fillText(trimCanvasText(context, region.caption, contentWidth), region.x + 10, region.y + 28);
    }
  }
  context.restore();
  track.__laneRegions = regions;
}