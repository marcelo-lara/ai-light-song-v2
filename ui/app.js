const artifactDefinitions = [
  {
    key: "info",
    label: "Output Info",
    path: (song) => ["data", "output", song, "info.json"],
  },
  {
    key: "beatsOutput",
    label: "Output Beats",
    path: (song) => ["data", "output", song, "beats.json"],
  },
  {
    key: "sectionsOutput",
    label: "Output Sections",
    path: (song) => ["data", "output", song, "sections.json"],
  },
  {
    key: "eventsTimeline",
    label: "Output Event Timeline",
    path: (song) => ["data", "output", song, "song_event_timeline.json"],
  },
  {
    key: "harmonic",
    label: "Layer A Harmonic",
    path: (song) => ["data", "artifacts", song, "layer_a_harmonic.json"],
  },
  {
    key: "symbolic",
    label: "Layer B Symbolic",
    path: (song) => ["data", "artifacts", song, "layer_b_symbolic.json"],
  },
  {
    key: "energy",
    label: "Layer C Energy",
    path: (song) => ["data", "artifacts", song, "layer_c_energy.json"],
  },
  {
    key: "patterns",
    label: "Layer D Patterns",
    path: (song) => ["data", "artifacts", song, "layer_d_patterns.json"],
  },
  {
    key: "sectionsArtifact",
    label: "Artifact Sections",
    path: (song) => ["data", "artifacts", song, "section_segmentation", "sections.json"],
  },
  {
    key: "drums",
    label: "Drum Events",
    path: (song) => ["data", "artifacts", song, "symbolic_transcription", "drum_events.json"],
  },
  {
    key: "eventFeatures",
    label: "Event Features",
    path: (song) => ["data", "artifacts", song, "event_inference", "features.json"],
  },
  {
    key: "eventIndex",
    label: "Event Timeline Index",
    path: (song) => ["data", "artifacts", song, "event_inference", "timeline_index.json"],
  },
  {
    key: "eventRules",
    label: "Rule Candidates",
    path: (song) => ["data", "artifacts", song, "event_inference", "rule_candidates.json"],
  },
  {
    key: "eventMachine",
    label: "Machine Events",
    path: (song) => ["data", "artifacts", song, "event_inference", "events.machine.json"],
  },
  {
    key: "patternMining",
    label: "Pattern Mining",
    path: (song) => ["data", "artifacts", song, "pattern_mining", "chord_patterns.json"],
  },
  {
    key: "unified",
    label: "Music Feature Layers",
    path: (song) => ["data", "artifacts", song, "music_feature_layers.json"],
  },
  {
    key: "validation",
    label: "Phase 1 Validation",
    path: (song) => ["data", "artifacts", song, "validation", "phase_1_report.json"],
  },
];

const elements = {
  songForm: document.querySelector("#song-form"),
  songSelect: document.querySelector("#song-select"),
  refreshSongs: document.querySelector("#refresh-songs"),
  songTitle: document.querySelector("#song-title"),
  songSubtitle: document.querySelector("#song-subtitle"),
  fileStatus: document.querySelector("#file-status"),
  coreArtifactState: document.querySelector("#core-artifact-state"),
  summaryGrid: document.querySelector("#summary-grid"),
  validationSummary: document.querySelector("#validation-summary"),
  sectionsPreview: document.querySelector("#sections-preview"),
  artifactSelect: document.querySelector("#artifact-select"),
  artifactViewer: document.querySelector("#artifact-viewer"),
  metaBpm: document.querySelector("#meta-bpm"),
  metaDuration: document.querySelector("#meta-duration"),
  metaValidation: document.querySelector("#meta-validation"),
  audioPlayer: document.querySelector("#audio-player"),
  audioStatus: document.querySelector("#audio-status"),
};

let loadedArtifacts = new Map();
let availableSongs = [];

const coreArtifactKeys = ["harmonic", "symbolic", "energy", "sectionsArtifact", "eventMachine", "validation"];

function encodePath(parts) {
  return "/" + parts.map((part) => encodeURIComponent(part)).join("/");
}

async function fetchJson(parts) {
  const response = await fetch(encodePath(parts), { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return response.json();
}

async function fetchDirectoryListing(parts) {
  const response = await fetch(encodePath(parts), { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }

  const html = await response.text();
  const parser = new DOMParser();
  const documentNode = parser.parseFromString(html, "text/html");
  const links = Array.from(documentNode.querySelectorAll("a"));

  return links
    .map((link) => link.getAttribute("href") || "")
    .filter((href) => href.endsWith("/") && href !== "../")
    .map((href) => decodeURIComponent(href.replace(/\/$/, "")))
    .filter((name) => name && name !== "data" && name !== "artifacts")
    .sort((left, right) => left.localeCompare(right));
}

function readCount(value, fallbackKeys = []) {
  if (Array.isArray(value)) {
    return value.length;
  }
  if (!value || typeof value !== "object") {
    return 0;
  }
  for (const key of fallbackKeys) {
    if (Array.isArray(value[key])) {
      return value[key].length;
    }
  }
  return Object.keys(value).length;
}

function formatDuration(seconds) {
  const numeric = Number(seconds);
  if (!Number.isFinite(numeric)) {
    return "-";
  }
  const minutes = Math.floor(numeric / 60);
  const remainder = numeric % 60;
  return `${minutes}:${remainder.toFixed(1).padStart(4, "0")}`;
}

function summarizeValidation(report) {
  if (!report || typeof report !== "object") {
    return "missing";
  }
  return report.status || "present";
}

function getArtifactLabel(key) {
  const definition = artifactDefinitions.find((artifact) => artifact.key === key);
  return definition ? definition.label : key;
}

function renderSongOptions(selectedSong = "") {
  if (availableSongs.length === 0) {
    elements.songSelect.innerHTML = '<option value="">No artifact directories found</option>';
    elements.songSelect.disabled = true;
    return;
  }

  const options = ['<option value="">Select a song directory</option>'];
  for (const song of availableSongs) {
    const selected = song === selectedSong ? ' selected' : '';
    options.push(`<option value="${song}"${selected}>${song}</option>`);
  }

  elements.songSelect.innerHTML = options.join("");
  elements.songSelect.disabled = false;
}

function renderFileStatus(statuses) {
  const markup = statuses
    .map((status) => {
      const cssClass = status.ok ? "status-ok" : status.error ? "status-error" : "status-missing";
      const stateText = status.ok ? "loaded" : status.error ? status.error : "missing";
      return `<li><span class="${cssClass}">${status.label}</span> <code>${status.path}</code> <span>${stateText}</span></li>`;
    })
    .join("");

  elements.fileStatus.className = "file-status";
  elements.fileStatus.innerHTML = `<ul class="file-status-list">${markup}</ul>`;
}

function renderCoreArtifactState(statuses) {
  const missingCore = statuses.filter((status) => coreArtifactKeys.includes(status.key) && !status.ok);

  if (missingCore.length === 0) {
    elements.coreArtifactState.classList.add("hidden");
    elements.coreArtifactState.innerHTML = "";
    return;
  }

  const items = missingCore
    .map((status) => `<li><strong>${status.label}</strong> <span>${status.error || "missing"}</span></li>`)
    .join("");

  elements.coreArtifactState.classList.remove("hidden");
  elements.coreArtifactState.innerHTML = `
    <strong>Core artifacts are incomplete for this song.</strong>
    <span>The debugger loaded the directory, but some primary inference surfaces are unavailable. Views that depend on them will stay partial.</span>
    <ul>${items}</ul>
  `;
}

function renderSummary(song, data) {
  const summaryCards = [
    { label: "Chord Events", value: readCount(data.harmonic?.chords || data.harmonic?.events, ["chords", "events"]) },
    { label: "Note Events", value: readCount(data.symbolic?.note_events || data.symbolic?.notes, ["note_events", "notes"]) },
    { label: "Energy Peaks", value: readCount(data.energy?.peaks, ["peaks"]) },
    { label: "Pattern Occurrences", value: readCount(data.patterns?.occurrences, ["occurrences"]) },
    { label: "Machine Events", value: readCount(data.eventMachine?.events, ["events"]) },
    { label: "Sections", value: readCount(data.sectionsArtifact?.sections || data.sectionsOutput, ["sections"]) },
  ];

  elements.summaryGrid.className = "summary-grid";
  elements.summaryGrid.innerHTML = summaryCards
    .map((card) => `<div class="summary-card"><span class="stat-label">${card.label}</span><strong>${card.value}</strong></div>`)
    .join("");

  elements.songTitle.textContent = song;
  elements.songSubtitle.textContent = "Primary source: data/artifacts. Output files are shown only as supporting projections.";
  elements.metaBpm.textContent = data.info?.bpm ?? data.validation?.validation?.beats?.diagnostics?.reference_beat_interval_seconds ?? "-";
  elements.metaDuration.textContent = formatDuration(data.info?.duration);
  elements.metaValidation.textContent = summarizeValidation(data.validation);
}

function renderValidation(report) {
  if (!report || typeof report !== "object") {
    elements.validationSummary.className = "empty";
    elements.validationSummary.textContent = "No validation report loaded.";
    return;
  }

  const blocks = Object.entries(report.validation || {})
    .map(([key, value]) => `<li><strong>${key}</strong>: ${value.status || "present"}</li>`)
    .join("");

  elements.validationSummary.className = "";
  elements.validationSummary.innerHTML = `
    <p><strong>Status:</strong> ${report.status || "unknown"}</p>
    <p><strong>Command:</strong> ${report.command || "-"}</p>
    <ul class="preview-list">${blocks || "<li>No per-target validation details.</li>"}</ul>
  `;
}

function renderSections(sectionsArtifact, sectionsOutput) {
  const sections = sectionsArtifact?.sections || sectionsOutput || [];
  if (!Array.isArray(sections) || sections.length === 0) {
    elements.sectionsPreview.className = "empty";
    elements.sectionsPreview.textContent = "No section artifact loaded.";
    return;
  }

  const preview = sections.slice(0, 8).map((section) => {
    const start = section.start ?? section.start_s ?? "-";
    const end = section.end ?? section.end_s ?? "-";
    const label = section.label ?? section.section_character ?? section.id ?? "section";
    return `<li><strong>${label}</strong> <span>${start} -> ${end}</span></li>`;
  }).join("");

  elements.sectionsPreview.className = "";
  elements.sectionsPreview.innerHTML = `<ul class="preview-list">${preview}</ul>`;
}

function updateArtifactSelector() {
  const options = ["<option value=\"\">Select a loaded file</option>"];
  for (const [key, value] of loadedArtifacts.entries()) {
    if (!value.ok) {
      continue;
    }
    options.push(`<option value="${key}">${value.label}</option>`);
  }
  elements.artifactSelect.innerHTML = options.join("");
}

function setArtifactViewer(key) {
  if (!key || !loadedArtifacts.has(key)) {
    elements.artifactViewer.textContent = "No artifact selected.";
    return;
  }
  const artifact = loadedArtifacts.get(key);
  elements.artifactViewer.textContent = JSON.stringify(artifact.data, null, 2);
}

async function loadSong(song) {
  const trimmedSong = song.trim();
  if (!trimmedSong) {
    return;
  }

  elements.songSelect.value = trimmedSong;

  const statusRows = [];
  const data = {};
  loadedArtifacts = new Map();

  await Promise.all(artifactDefinitions.map(async (definition) => {
    const parts = definition.path(trimmedSong);
    const path = encodePath(parts);
    try {
      const result = await fetchJson(parts);
      data[definition.key] = result;
      loadedArtifacts.set(definition.key, { ok: true, label: definition.label, data: result });
      statusRows.push({ key: definition.key, label: definition.label, path, ok: true });
    } catch (error) {
      loadedArtifacts.set(definition.key, { ok: false, label: definition.label, error: error.message });
      statusRows.push({ key: definition.key, label: definition.label, path, ok: false, error: error.message });
    }
  }));

  const sortedStatuses = statusRows.sort((left, right) => left.label.localeCompare(right.label));
  renderFileStatus(sortedStatuses);
  renderCoreArtifactState(sortedStatuses);
  renderSummary(trimmedSong, data);
  renderValidation(data.validation);
  renderSections(data.sectionsArtifact, data.sectionsOutput);
  updateArtifactSelector();
  setArtifactViewer("");

  const audioPath = encodePath(["data", "songs", `${trimmedSong}.mp3`]);
  elements.audioPlayer.src = audioPath;
  elements.audioStatus.textContent = `Read-only audio source: ${audioPath}`;

  const params = new URLSearchParams(window.location.search);
  params.set("song", trimmedSong);
  history.replaceState(null, "", `${window.location.pathname}?${params.toString()}`);
}

async function discoverSongs(preferredSong = "") {
  elements.songSelect.disabled = true;
  elements.songSelect.innerHTML = '<option value="">Discovering artifact directories...</option>';

  try {
    availableSongs = await fetchDirectoryListing(["data", "artifacts"]);
    const selectedSong = availableSongs.includes(preferredSong) ? preferredSong : "";
    renderSongOptions(selectedSong);

    if (selectedSong) {
      await loadSong(selectedSong);
      return;
    }

    if (!preferredSong && availableSongs.length > 0) {
      elements.songSelect.value = availableSongs[0];
      await loadSong(availableSongs[0]);
      return;
    }

    if (preferredSong && !selectedSong && availableSongs.length > 0) {
      elements.songSelect.value = availableSongs[0];
    }
  } catch (error) {
    availableSongs = [];
    elements.songSelect.innerHTML = `<option value="">Song discovery failed: ${error.message}</option>`;
    elements.songSelect.disabled = true;
    elements.songSubtitle.textContent = "Could not read /data/artifacts for song discovery.";
  }
}

elements.songForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  await loadSong(elements.songSelect.value);
});

elements.refreshSongs.addEventListener("click", async () => {
  await discoverSongs(elements.songSelect.value);
});

elements.artifactSelect.addEventListener("change", (event) => {
  setArtifactViewer(event.target.value);
});

const initialSong = new URLSearchParams(window.location.search).get("song") || "";
discoverSongs(initialSong);