import { coreArtifactKeys, laneDefinitions } from "./config.js";
import { elements, state } from "./runtime.js";
import { escapeHtml, formatDuration, formatPercent, formatRange, roundNumber, summarizeValidation } from "./utils.js";

export function renderSongOptions(selectedSong = "") {
  if (state.availableSongs.length === 0) {
    elements.songSelect.innerHTML = '<option value="">No artifact directories found</option>';
    elements.songSelect.disabled = true;
    return;
  }

  const options = ['<option value="">Select a song directory</option>'];
  for (const song of state.availableSongs) {
    const selected = song === selectedSong ? " selected" : "";
    options.push(`<option value="${escapeHtml(song)}"${selected}>${escapeHtml(song)}</option>`);
  }

  elements.songSelect.innerHTML = options.join("");
  elements.songSelect.disabled = false;
}

export function renderFileStatus(statuses) {
  const markup = statuses.map((status) => {
    const cssClass = status.ok ? "status-ok" : status.error ? "status-error" : "status-missing";
    const stateText = status.ok ? "loaded" : status.error ? status.error : "missing";
    return `
      <li>
        <div class="status-row">
          <span class="status-pill ${cssClass}">${escapeHtml(status.label)}</span>
          <span>${escapeHtml(stateText)}</span>
        </div>
        <div class="status-path">${escapeHtml(status.path)}</div>
      </li>
    `;
  }).join("");

  elements.fileStatus.className = "file-status";
  elements.fileStatus.innerHTML = `<ul class="file-status-list">${markup}</ul>`;
}

export function renderCoreArtifactState(statuses) {
  const missingCore = statuses.filter((status) => coreArtifactKeys.includes(status.key) && !status.ok);
  if (missingCore.length === 0) {
    elements.coreArtifactState.classList.add("hidden");
    elements.coreArtifactState.innerHTML = "";
    return;
  }

  const items = missingCore
    .map((status) => `<li><strong>${escapeHtml(status.label)}</strong> <span>${escapeHtml(status.error || "missing")}</span></li>`)
    .join("");

  elements.coreArtifactState.classList.remove("hidden");
  elements.coreArtifactState.innerHTML = `
    <strong>Core artifacts are incomplete for this song.</strong>
    <span>The debugger stays read-only and loads what it can, but some lanes and overlays will remain partial.</span>
    <ul>${items}</ul>
  `;
}

export function renderSummary(song, data, timeline) {
  const summaryCards = [
    { label: "Chord Regions", value: timeline.chords.length },
    { label: "Phrase Windows", value: timeline.phrases.length },
    { label: "Pattern Occurrences", value: timeline.patterns.length },
    { label: "Machine Events", value: timeline.machineEvents.length },
    { label: "Drum Events", value: timeline.drums.length },
    { label: "Beat Drift Flags", value: timeline.validationDrift.filter((row) => row.within_tolerance === false).length },
  ];

  elements.summaryGrid.className = "summary-grid";
  elements.summaryGrid.innerHTML = summaryCards
    .map((card) => `<div class="summary-card"><span class="stat-label">${escapeHtml(card.label)}</span><strong>${escapeHtml(card.value)}</strong></div>`)
    .join("");
  elements.songTitle.textContent = song;
  elements.songSubtitle.textContent = "Artifact lanes remain primary. Output helper projections are overlaid only when useful for comparison.";
  elements.metaBpm.textContent = Number.isFinite(timeline.bpm) && timeline.bpm > 0 ? roundNumber(timeline.bpm, 1) : "-";
  elements.metaDuration.textContent = formatDuration(timeline.duration);
  elements.metaValidation.textContent = summarizeValidation(data.validation);
  elements.metaViewport.textContent = `${state.zoom} px/s`;
}

export function renderValidation(report, timeline) {
  if (!report || typeof report !== "object") {
    elements.validationSummary.className = "empty";
    elements.validationSummary.textContent = "No validation report loaded.";
    return;
  }

  const targets = Object.entries(report.validation || {})
    .map(([key, value]) => `<li><strong>${escapeHtml(key)}</strong>: ${escapeHtml(value.status || "present")}</li>`)
    .join("");
  const beatsStatus = report.validation?.beats || {};
  const comparisonCounts = timeline.eventComparisons.reduce((accumulator, row) => {
    accumulator[row.status] = (accumulator[row.status] || 0) + 1;
    return accumulator;
  }, {});

  elements.validationSummary.className = "";
  elements.validationSummary.innerHTML = `
    <p><strong>Status:</strong> ${escapeHtml(report.status || "unknown")}</p>
    <p><strong>Command:</strong> ${escapeHtml(report.command || "-")}</p>
    <p><strong>Beat Match Ratio:</strong> ${escapeHtml(formatPercent(beatsStatus.match_ratio))}</p>
    <p><strong>Event Comparison:</strong> exact=${escapeHtml(comparisonCounts.exact || 0)} shifted=${escapeHtml(comparisonCounts.shifted || 0)} not_exported=${escapeHtml(comparisonCounts.not_exported || 0)} output_only=${escapeHtml(comparisonCounts.output_only || 0)}</p>
    <ul class="preview-list">${targets || "<li>No per-target validation details.</li>"}</ul>
  `;
}

export function renderSectionsPreview(timeline) {
  if (!timeline.sections.length) {
    elements.sectionsPreview.className = "empty";
    elements.sectionsPreview.textContent = "No section artifact loaded.";
    return;
  }

  const preview = timeline.sections.slice(0, 8).map((section) => `
    <li>
      <strong>${escapeHtml(section.label)}</strong>
      <span>${escapeHtml(formatRange(section.start_s, section.end_s))}</span>
    </li>
  `).join("");

  elements.sectionsPreview.className = "";
  elements.sectionsPreview.innerHTML = `<ul class="preview-list">${preview}</ul>`;
}

export function updateArtifactSelector() {
  const options = ['<option value="">Select a loaded file</option>'];
  for (const [key, value] of state.loadedArtifacts.entries()) {
    if (value.ok) {
      options.push(`<option value="${escapeHtml(key)}">${escapeHtml(value.label)}</option>`);
    }
  }
  elements.artifactSelect.innerHTML = options.join("");
}

export function setArtifactViewer(key) {
  if (!key || !state.loadedArtifacts.has(key)) {
    elements.artifactViewer.textContent = "No artifact selected.";
    return;
  }
  const artifact = state.loadedArtifacts.get(key);
  elements.artifactViewer.textContent = JSON.stringify(artifact.data, null, 2);
}

export function renderLaneToggles() {
  if (!state.timeline) {
    elements.laneToggles.className = "lane-toggle-list empty";
    elements.laneToggles.textContent = "Load a song to enable lane visibility controls.";
    return;
  }

  elements.laneToggles.className = "lane-toggle-list";
  elements.laneToggles.innerHTML = laneDefinitions.map((lane) => `
    <label class="lane-toggle" for="lane-toggle-${escapeHtml(lane.id)}">
      <input id="lane-toggle-${escapeHtml(lane.id)}" type="checkbox" data-lane-toggle="${escapeHtml(lane.id)}" ${state.laneVisibility[lane.id] ? "checked" : ""}>
      <span>
        <strong>${escapeHtml(lane.label)}</strong>
        <span>${escapeHtml(lane.description)}</span>
      </span>
    </label>
  `).join("");
}

export function setSelectedRegion(region) {
  state.selectedRegion = region;
  if (!region) {
    elements.selectionBrief.textContent = "No region selected.";
    elements.selectionDetail.className = "empty";
    elements.selectionDetail.textContent = "Click a region, overlay, or lane to inspect it and jump the shared cursor.";
    return;
  }

  elements.selectionBrief.textContent = `${region.laneLabel}: ${region.label} ${formatRange(region.start_s, region.end_s)}`;
  elements.selectionDetail.className = "selection-card";
  elements.selectionDetail.innerHTML = `
    <h3>${escapeHtml(region.label)}</h3>
    <dl>
      <div>
        <dt>Lane</dt>
        <dd>${escapeHtml(region.laneLabel)}</dd>
      </div>
      <div>
        <dt>Window</dt>
        <dd>${escapeHtml(formatRange(region.start_s, region.end_s))}</dd>
      </div>
      <div>
        <dt>Primary Ref</dt>
        <dd>${escapeHtml(region.reference || "-")}</dd>
      </div>
      <div>
        <dt>Detail</dt>
        <dd>${escapeHtml(region.detail || "-")}</dd>
      </div>
    </dl>
    <div class="selection-summary">${escapeHtml(region.summary || "The shared cursor was moved to the start of this region. Playback state remains browser-local and read-only.")}</div>
  `;
}