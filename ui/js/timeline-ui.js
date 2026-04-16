import { DEFAULT_ZOOM, LABEL_WIDTH, dynamicLaneIds, laneDefinitions } from "./config.js";
import { audioDecodeContext, elements, state, waveformCache } from "./runtime.js";
import { clamp, encodePath, escapeHtml, formatDuration, formatRange, roundNumber } from "./utils.js";
import { setSelectedRegion } from "./overview-render.js";

export function timeToPx(time) {
  return clamp(Number(time) || 0, 0, state.timeline?.duration || 0) * state.zoom;
}

function getVisibleRange() {
  const scrollLeft = elements.timelineScroller.scrollLeft;
  const viewportWidth = Math.max(elements.timelineScroller.clientWidth - LABEL_WIDTH, 0);
  const start = clamp(scrollLeft / state.zoom, 0, state.timeline?.duration || 0);
  const end = clamp(start + (viewportWidth / state.zoom), start, state.timeline?.duration || 0);
  return { start, end };
}

function renderGridHtml() {
  if (!state.timeline) {
    return "";
  }
  if (state.zoom >= 64) {
    return state.timeline.beats.map((beat) => `<span class="grid-line ${beat.beat_in_bar === 1 ? "downbeat" : ""}" style="left:${timeToPx(beat.time)}px"></span>`).join("");
  }
  if (state.zoom >= 24) {
    return state.timeline.beats.filter((beat) => beat.beat_in_bar === 1).map((beat) => `<span class="grid-line downbeat" style="left:${timeToPx(beat.time)}px"></span>`).join("");
  }
  return state.timeline.bars.filter((bar) => (Number(bar.bar) - 1) % 4 === 0).map((bar) => `<span class="grid-line measure" style="left:${timeToPx(bar.start_s)}px"></span>`).join("");
}

function renderRulerTicksHtml() {
  if (!state.timeline) {
    return "";
  }
  const barStep = state.zoom >= 64 ? 1 : state.zoom >= 32 ? 2 : state.zoom >= 18 ? 4 : 8;
  return state.timeline.bars
    .filter((bar) => (Number(bar.bar) - 1) % barStep === 0)
    .map((bar) => `<span class="ruler-tick" style="left:${timeToPx(bar.start_s)}px">Bar ${escapeHtml(bar.bar)} · ${escapeHtml(formatDuration(bar.start_s))}</span>`)
    .join("");
}

function regionMarkup(items, cssClass, laneLabel) {
  return items.map((item) => {
    const left = timeToPx(item.start_s);
    const width = Math.max(2, timeToPx(item.end_s) - left);
    return `
      <button
        type="button"
        class="lane-region ${escapeHtml(cssClass)}"
        data-select-region="true"
        data-lane-label="${escapeHtml(laneLabel)}"
        data-label="${escapeHtml(item.label)}"
        data-start-s="${escapeHtml(item.start_s)}"
        data-end-s="${escapeHtml(item.end_s)}"
        data-reference="${escapeHtml(item.id || "-")}"
        data-detail="${escapeHtml(item.detail || "-")}"
        data-summary="${escapeHtml(item.summary || "")}"
        style="left:${left}px;width:${width}px"
      >
        <strong>${escapeHtml(item.label)}</strong>
        <span>${escapeHtml(item.caption || formatRange(item.start_s, item.end_s))}</span>
      </button>
    `;
  }).join("");
}

function buildSparseLaneContent(laneId) {
  switch (laneId) {
    case "sections":
      return regionMarkup(state.timeline.sections.map((section) => ({
        ...section,
        caption: `${formatRange(section.start_s, section.end_s)} · conf ${roundNumber(section.confidence, 2)}`,
        summary: section.description || "Section navigation stays browser-local and updates only the shared playback cursor.",
      })), "sections", "Sections");
    case "phrases":
      return regionMarkup(state.timeline.phrases.map((phrase) => ({
        ...phrase,
        caption: `${formatRange(phrase.start_s, phrase.end_s)} · ${phrase.group_id || "single"}`,
        detail: phrase.group_id || phrase.id,
      })), "phrases", "Phrase Windows");
    case "chords":
      return regionMarkup(state.timeline.chords.map((chord) => ({
        ...chord,
        caption: `${formatRange(chord.start_s, chord.end_s)} · conf ${roundNumber(chord.confidence, 2)}`,
      })), "chords", "Chord Regions");
    case "patterns":
      return regionMarkup(state.timeline.patterns.map((pattern) => ({
        ...pattern,
        label: `Pattern ${pattern.label}`,
        caption: `${formatRange(pattern.start_s, pattern.end_s)} · ${pattern.sequence}`,
        detail: `bars ${pattern.start_bar}-${pattern.end_bar}`,
      })), "patterns", "Pattern Occurrences");
    case "machineEvents":
      return regionMarkup(state.timeline.machineEvents.map((event) => ({
        id: event.id,
        label: String(event.type),
        start_s: Number(event.start_time),
        end_s: Number(event.end_time),
        caption: `${formatRange(event.start_time, event.end_time)} · conf ${roundNumber(event.confidence, 2)}`,
        detail: event.section_id || event.created_by || "machine",
        summary: event.evidence?.summary || event.notes || "Machine event window",
      })), "machine-events", "Machine Events");
    case "timelineEvents":
      return regionMarkup(state.timeline.timelineEvents.map((event) => ({
        id: event.id,
        label: String(event.type),
        start_s: Number(event.start_time),
        end_s: Number(event.end_time),
        caption: `${formatRange(event.start_time, event.end_time)} · ${event.provenance}`,
        detail: event.created_by || event.provenance || "timeline",
        summary: event.summary || event.evidence_summary || "Exported event timeline window",
      })), "timeline-events", "Export Timeline");
    default:
      return "";
  }
}

function bucketRows(rows, secondsPerBucket, start, end) {
  const buckets = new Map();
  for (const row of rows) {
    if (Number(row.end_s) < start || Number(row.start_s) > end) {
      continue;
    }
    const index = Math.floor(Number(row.start_s) / secondsPerBucket);
    const bucket = buckets.get(index) || {
      start_s: index * secondsPerBucket,
      end_s: (index + 1) * secondsPerBucket,
      value: 0,
      count: 0,
      byType: { kick: 0, snare: 0, hat: 0 },
    };
    bucket.value = Math.max(bucket.value, Number(row.value ?? 0));
    bucket.count += 1;
    if (row.event_type && bucket.byType[row.event_type] !== undefined) {
      bucket.byType[row.event_type] += 1;
    }
    buckets.set(index, bucket);
  }
  return [...buckets.values()].sort((left, right) => left.start_s - right.start_s);
}

function buildAreaPath(rows, height) {
  if (!rows.length) {
    return "";
  }
  const baseline = height - 8;
  const topPoints = rows.map((row) => {
    const x = timeToPx((Number(row.start_s) + Number(row.end_s)) / 2);
    const y = baseline - (clamp(Number(row.value), 0, 1) * (height - 18));
    return `${x},${y}`;
  });
  const startX = timeToPx(rows[0].start_s);
  const endX = timeToPx(rows.at(-1).end_s);
  return `M ${startX},${baseline} L ${topPoints.join(" L ")} L ${endX},${baseline} Z`;
}

function buildWaveformPath(peaks, height) {
  const center = height / 2;
  const scale = height * 0.38;
  const top = peaks.map((peak, index) => {
    const x = (index / Math.max(peaks.length - 1, 1)) * (state.timeline.duration * state.zoom);
    return `${x},${center - (peak * scale)}`;
  });
  const bottom = peaks.slice().reverse().map((peak, reverseIndex) => {
    const index = peaks.length - 1 - reverseIndex;
    const x = (index / Math.max(peaks.length - 1, 1)) * (state.timeline.duration * state.zoom);
    return `${x},${center + (peak * scale)}`;
  });
  return `M ${top.join(" L ")} L ${bottom.join(" L ")} Z`;
}

function renderWaveformLane(track) {
  const width = Math.max(Math.ceil(state.timeline.duration * state.zoom), 1);
  const peaks = Array.isArray(waveformCache.get(state.currentSong))
    ? waveformCache.get(state.currentSong)
    : state.timeline.beats.map((beat) => beat.beat_in_bar === 1 ? 0.9 : 0.45);
  track.querySelector(".lane-content").innerHTML = `
    <svg class="lane-svg" viewBox="0 0 ${width} 84" preserveAspectRatio="none" style="width:${width}px;height:84px">
      <path d="${buildWaveformPath(peaks, 84)}" fill="rgba(15, 118, 110, 0.18)" stroke="rgba(15, 118, 110, 0.65)" stroke-width="1.2"></path>
    </svg>
  `;
}

function renderSeriesLane(track, laneId) {
  const width = Math.max(Math.ceil(state.timeline.duration * state.zoom), 1);
  const { start, end } = getVisibleRange();
  const source = laneId === "density" ? state.timeline.densityRows : state.timeline.energyRows;
  const rows = bucketRows(source, Math.max(0.1, 12 / state.zoom), Math.max(0, start - 4), Math.min(state.timeline.duration, end + 4));
  const fill = laneId === "density" ? "rgba(76, 29, 149, 0.14)" : "rgba(14, 116, 144, 0.16)";
  const stroke = laneId === "density" ? "rgba(76, 29, 149, 0.72)" : "rgba(14, 116, 144, 0.72)";
  const accents = laneId === "energy"
    ? state.timeline.accentCandidates
      .filter((accent) => Number(accent.time) >= start - 2 && Number(accent.time) <= end + 2)
      .map((accent) => {
        const x = timeToPx(accent.time);
        const y = 72 - (clamp(Number(accent.intensity) || 0, 0, 1) * 52);
        return `<circle cx="${x}" cy="${y}" r="3.6" fill="rgba(185, 28, 28, 0.8)"></circle>`;
      }).join("")
    : "";
  track.querySelector(".lane-content").innerHTML = `
    <svg class="lane-svg" viewBox="0 0 ${width} 84" preserveAspectRatio="none" style="width:${width}px;height:84px">
      <path d="${buildAreaPath(rows, 84)}" fill="${fill}" stroke="${stroke}" stroke-width="1.4"></path>
      ${accents}
    </svg>
  `;
}

function renderDrumsLane(track) {
  const width = Math.max(Math.ceil(state.timeline.duration * state.zoom), 1);
  const { start, end } = getVisibleRange();
  const content = track.querySelector(".lane-content");
  if (state.zoom >= 42) {
    const visibleEvents = state.timeline.drums.filter((event) => Number(event.time) >= start - 1.5 && Number(event.time) <= end + 1.5);
    const typeY = { kick: 58, snare: 38, hat: 18, unresolved: 68 };
    const typeColor = {
      kick: "rgba(15, 118, 110, 0.9)",
      snare: "rgba(185, 28, 28, 0.9)",
      hat: "rgba(202, 138, 4, 0.9)",
      unresolved: "rgba(107, 114, 128, 0.8)",
    };
    content.innerHTML = `
      <svg class="lane-svg" viewBox="0 0 ${width} 84" preserveAspectRatio="none" style="width:${width}px;height:84px">
        ${visibleEvents.map((event) => {
          const x = timeToPx(event.time);
          const y = typeY[event.event_type] || 68;
          const color = typeColor[event.event_type] || typeColor.unresolved;
          return `<line x1="${x}" x2="${x}" y1="${y - 10}" y2="${y + 10}" stroke="${color}" stroke-width="2.2"></line>`;
        }).join("")}
      </svg>
    `;
    return;
  }
  const buckets = bucketRows(
    state.timeline.drums.map((event) => ({
      start_s: Number(event.time),
      end_s: Number(event.end_s ?? event.time),
      value: 0,
      event_type: String(event.event_type),
    })),
    Math.max(0.2, 14 / state.zoom),
    start,
    end,
  );
  const maxCount = Math.max(...buckets.map((bucket) => bucket.count), 1);
  content.innerHTML = `
    <svg class="lane-svg" viewBox="0 0 ${width} 84" preserveAspectRatio="none" style="width:${width}px;height:84px">
      ${buckets.map((bucket) => {
        const left = timeToPx(bucket.start_s);
        const widthPx = Math.max(1, timeToPx(bucket.end_s) - left);
        const kickHeight = (bucket.byType.kick / maxCount) * 24;
        const snareHeight = (bucket.byType.snare / maxCount) * 18;
        const hatHeight = (bucket.byType.hat / maxCount) * 16;
        return `
          <rect x="${left}" y="${78 - kickHeight}" width="${widthPx}" height="${kickHeight}" fill="rgba(15, 118, 110, 0.85)"></rect>
          <rect x="${left}" y="${52 - snareHeight}" width="${widthPx}" height="${snareHeight}" fill="rgba(185, 28, 28, 0.82)"></rect>
          <rect x="${left}" y="${28 - hatHeight}" width="${widthPx}" height="${hatHeight}" fill="rgba(202, 138, 4, 0.84)"></rect>
        `;
      }).join("")}
    </svg>
  `;
}

function renderValidationLane(track) {
  const width = Math.max(Math.ceil(state.timeline.duration * state.zoom), 1);
  const { start, end } = getVisibleRange();
  const visibleDrift = state.timeline.validationDrift.filter((row) => Number(row.reference_time) >= start - 2 && Number(row.reference_time) <= end + 2);
  const visibleEvents = state.timeline.eventComparisons.filter((row) => Number(row.end_s) >= start - 2 && Number(row.start_s) <= end + 2);
  const colorByStatus = {
    exact: "rgba(15, 118, 110, 0.7)",
    shifted: "rgba(202, 138, 4, 0.76)",
    not_exported: "rgba(185, 28, 28, 0.76)",
    output_only: "rgba(30, 64, 175, 0.7)",
  };
  track.querySelector(".lane-content").innerHTML = `
    <svg class="lane-svg" viewBox="0 0 ${width} 84" preserveAspectRatio="none" style="width:${width}px;height:84px">
      ${visibleEvents.map((row) => {
        const left = timeToPx(row.start_s);
        const widthPx = Math.max(2, timeToPx(row.end_s) - left);
        return `<rect x="${left}" y="10" width="${widthPx}" height="16" rx="8" fill="${colorByStatus[row.status] || colorByStatus.shifted}"></rect>`;
      }).join("")}
      ${visibleDrift.map((row) => {
        const x = timeToPx(row.reference_time ?? row.inferred_time ?? 0);
        const delta = Number(row.delta_seconds ?? 0);
        const height = Math.min(24, Math.abs(delta) * 140);
        const color = row.within_tolerance ? "rgba(15, 118, 110, 0.82)" : "rgba(185, 28, 28, 0.88)";
        return `<line x1="${x}" x2="${x}" y1="${64 - height}" y2="64" stroke="${color}" stroke-width="2.4"></line>`;
      }).join("")}
      <line x1="0" x2="${width}" y1="64" y2="64" stroke="rgba(77, 53, 29, 0.18)" stroke-width="1"></line>
    </svg>
  `;
}

function renderDynamicLane(laneId) {
  const track = elements.timelineRows.querySelector(`[data-track-lane="${laneId}"]`);
  if (!track || !state.timeline) {
    return;
  }
  if (laneId === "waveform") {
    renderWaveformLane(track);
    return;
  }
  if (laneId === "drums") {
    renderDrumsLane(track);
    return;
  }
  if (laneId === "density" || laneId === "energy") {
    renderSeriesLane(track, laneId);
    return;
  }
  if (laneId === "validation") {
    renderValidationLane(track);
  }
}

export function renderTimeline() {
  if (!state.timeline) {
    elements.timelineRows.className = "timeline-rows empty";
    elements.timelineRows.textContent = "Load a song to inspect the synchronized timeline lanes.";
    return;
  }
  const width = Math.max(Math.ceil(state.timeline.duration * state.zoom), 1);
  const gridHtml = renderGridHtml();
  const rows = [
    `
      <div class="timeline-row ruler-row">
        <div class="lane-label">
          <h4>Timeline</h4>
          <span class="lane-meta">Shared beat grid and bar ruler</span>
        </div>
        <div class="lane-track ruler-track" style="width:${width}px">
          <div class="grid-layer">${gridHtml}</div>
          <div class="ruler-ticks">${renderRulerTicksHtml()}</div>
          <div class="now-markers"><span class="now-marker" data-now-marker></span></div>
        </div>
      </div>
    `,
  ];
  for (const lane of laneDefinitions) {
    if (!state.laneVisibility[lane.id]) {
      continue;
    }
    rows.push(`
      <div class="timeline-row" data-lane-row="${escapeHtml(lane.id)}">
        <div class="lane-label">
          <h3>${escapeHtml(lane.label)}</h3>
          <span class="lane-meta">${escapeHtml(lane.description)}</span>
        </div>
        <div class="lane-track" data-track-lane="${escapeHtml(lane.id)}" style="width:${width}px">
          <div class="grid-layer">${gridHtml}</div>
          <div class="lane-content">${dynamicLaneIds.has(lane.id) ? "" : buildSparseLaneContent(lane.id)}</div>
          <div class="now-markers"><span class="now-marker" data-now-marker></span></div>
        </div>
      </div>
    `);
  }
  elements.timelineRows.className = "timeline-rows";
  elements.timelineRows.innerHTML = rows.join("");
  for (const lane of laneDefinitions) {
    if (state.laneVisibility[lane.id] && dynamicLaneIds.has(lane.id)) {
      renderDynamicLane(lane.id);
    }
  }
  updateViewportReadout();
  updateNowMarkers();
}

export function updateViewportReadout() {
  if (!state.timeline) {
    elements.visibleWindow.textContent = "Visible 0:00.0-0:00.0";
    elements.metaViewport.textContent = "-";
    return;
  }
  const range = getVisibleRange();
  elements.visibleWindow.textContent = `Visible ${formatRange(range.start, range.end)}`;
  elements.metaViewport.textContent = formatRange(range.start, range.end);
}

function beatAtTime(time) {
  for (let index = 0; index < state.timeline.beats.length; index += 1) {
    const beat = state.timeline.beats[index];
    const next = state.timeline.beats[index + 1];
    const end = next ? next.time : state.timeline.duration;
    if (beat.time <= time && time < end) {
      return beat;
    }
  }
  return state.timeline.beats.at(-1) || null;
}

export function updateTransportReadout() {
  const time = Number(elements.audioPlayer.currentTime || 0);
  elements.transportNow.textContent = formatDuration(time);
  const beat = state.timeline ? beatAtTime(time) : null;
  elements.transportBeat.textContent = beat ? `Bar ${beat.bar} · Beat ${beat.beat_in_bar}` : "-";
}

export function updateNowMarkers() {
  if (!state.timeline) {
    return;
  }
  const x = timeToPx(Number(elements.audioPlayer.currentTime || 0));
  for (const marker of elements.timelineRows.querySelectorAll("[data-now-marker]")) {
    marker.style.left = `${x}px`;
  }
  updateTransportReadout();
}

export function centerTimeInView(time) {
  const viewportWidth = Math.max(elements.timelineScroller.clientWidth - LABEL_WIDTH, 0);
  elements.timelineScroller.scrollLeft = Math.max(0, timeToPx(time) - (viewportWidth / 2));
}

export function scheduleViewportRender() {
  if (state.viewportRenderQueued || !state.timeline) {
    return;
  }
  state.viewportRenderQueued = true;
  requestAnimationFrame(() => {
    state.viewportRenderQueued = false;
    updateViewportReadout();
    for (const laneId of ["drums", "density", "energy", "validation"]) {
      if (state.laneVisibility[laneId]) {
        renderDynamicLane(laneId);
      }
    }
  });
}

function animationLoop() {
  if (elements.audioPlayer.paused) {
    state.animationFrame = null;
    updateNowMarkers();
    return;
  }
  updateNowMarkers();
  if (state.followPlayhead) {
    centerTimeInView(Number(elements.audioPlayer.currentTime || 0));
  }
  state.animationFrame = requestAnimationFrame(animationLoop);
}

export function startAnimationLoop() {
  if (!state.animationFrame) {
    state.animationFrame = requestAnimationFrame(animationLoop);
  }
}

export function stopAnimationLoop() {
  if (state.animationFrame) {
    cancelAnimationFrame(state.animationFrame);
    state.animationFrame = null;
  }
}

export function seekTo(time, selection) {
  const clampedTime = clamp(Number(time) || 0, 0, Number(state.timeline?.duration || elements.audioPlayer.duration || 0));
  elements.audioPlayer.currentTime = clampedTime;
  if (state.followPlayhead) {
    centerTimeInView(clampedTime);
  }
  updateNowMarkers();
  if (selection) {
    setSelectedRegion(selection);
  }
}

function buildSelectionFromDataset(dataset) {
  return {
    laneLabel: dataset.laneLabel,
    label: dataset.label,
    start_s: Number(dataset.startS),
    end_s: Number(dataset.endS),
    reference: dataset.reference,
    detail: dataset.detail,
    summary: dataset.summary,
  };
}

export function handleTimelineClick(event) {
  if (!state.timeline) {
    return;
  }
  const region = event.target.closest("[data-select-region]");
  if (region) {
    const selection = buildSelectionFromDataset(region.dataset);
    seekTo(selection.start_s, selection);
    return;
  }
  const track = event.target.closest("[data-track-lane], .ruler-track");
  if (!track) {
    return;
  }
  const rectangle = track.getBoundingClientRect();
  const absoluteX = elements.timelineScroller.scrollLeft + (event.clientX - rectangle.left);
  const time = absoluteX / state.zoom;
  seekTo(time, {
    laneLabel: laneDefinitions.find((lane) => lane.id === track.dataset.trackLane)?.label || "Timeline",
    label: `Cursor ${formatDuration(time)}`,
    start_s: time,
    end_s: time,
    reference: track.dataset.trackLane || "timeline",
    detail: "scrub",
    summary: "The shared playback cursor was moved directly on the synchronized timeline.",
  });
}

export async function ensureWaveform(song, audioPath) {
  if (!audioDecodeContext || waveformCache.has(song)) {
    return waveformCache.get(song) || null;
  }
  elements.waveformStatus.textContent = "Decoding audio in the browser for waveform anchoring...";
  try {
    const response = await fetch(audioPath, { cache: "force-cache" });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const buffer = await response.arrayBuffer();
    const audioBuffer = await audioDecodeContext.decodeAudioData(buffer.slice(0));
    const channel = audioBuffer.getChannelData(0);
    const peakCount = 1400;
    const blockSize = Math.max(1, Math.floor(channel.length / peakCount));
    const peaks = [];
    for (let index = 0; index < peakCount; index += 1) {
      const start = index * blockSize;
      const end = Math.min(channel.length, start + blockSize);
      let peak = 0;
      for (let offset = start; offset < end; offset += 1) {
        peak = Math.max(peak, Math.abs(channel[offset]));
      }
      peaks.push(peak);
    }
    waveformCache.set(song, peaks);
    if (state.currentSong === song) {
      elements.waveformStatus.textContent = "Waveform decoded in the browser from the mounted song file.";
      if (state.laneVisibility.waveform) {
        renderDynamicLane("waveform");
      }
    }
    return peaks;
  } catch (error) {
    if (state.currentSong === song) {
      elements.waveformStatus.textContent = `Waveform unavailable: ${error.message}. Falling back to beat pulses.`;
      if (state.laneVisibility.waveform) {
        renderDynamicLane("waveform");
      }
    }
    return null;
  }
}

export function initializeTimelineUi() {
  elements.zoomControl.value = String(DEFAULT_ZOOM);
  elements.zoomValue.textContent = `${DEFAULT_ZOOM} px/s`;
}