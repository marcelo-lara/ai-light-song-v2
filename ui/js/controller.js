import { DEFAULT_ZOOM, MAX_ZOOM, MIN_ZOOM, artifactDefinitions } from "./config.js";
import { fetchDirectoryListing, fetchJson, buildTimelineData } from "./data.js";
import { elements, state, audioDecodeContext } from "./runtime.js";
import { encodePath, escapeHtml } from "./utils.js";
import {
  renderSongOptions,
  renderFileStatus,
  renderCoreArtifactState,
  renderSummary,
  renderValidation,
  renderSectionsPreview,
  updateArtifactSelector,
  setArtifactViewer,
  renderLaneToggles,
  setSelectedRegion,
} from "./overview-render.js";
import {
  handleTimelineClick,
  renderTimeline,
  scheduleViewportRender,
  centerTimeInView,
  updateNowMarkers,
  updateTransportReadout,
  startAnimationLoop,
  stopAnimationLoop,
  seekTo,
  ensureWaveform,
  initializeTimelineUi,
} from "./timeline-ui.js";

export async function loadSong(song) {
  const trimmedSong = song.trim();
  if (!trimmedSong) {
    return;
  }

  elements.songSelect.value = trimmedSong;
  state.currentSong = trimmedSong;
  state.currentData = {};
  state.loadedArtifacts = new Map();
  setSelectedRegion(null);
  stopAnimationLoop();
  elements.playPause.textContent = "Play";

  const statusRows = [];
  const data = {};
  await Promise.all(artifactDefinitions.map(async (definition) => {
    const parts = definition.path(trimmedSong);
    const path = encodePath(parts);
    try {
      const result = await fetchJson(parts);
      data[definition.key] = result;
      state.loadedArtifacts.set(definition.key, { ok: true, label: definition.label, data: result });
      statusRows.push({ key: definition.key, label: definition.label, path, ok: true });
    } catch (error) {
      state.loadedArtifacts.set(definition.key, { ok: false, label: definition.label, error: error.message });
      statusRows.push({ key: definition.key, label: definition.label, path, ok: false, error: error.message });
    }
  }));

  state.currentData = data;
  state.timeline = buildTimelineData(data);

  const sortedStatuses = statusRows.sort((left, right) => left.label.localeCompare(right.label));
  renderFileStatus(sortedStatuses);
  renderCoreArtifactState(sortedStatuses);
  renderSummary(trimmedSong, data, state.timeline);
  renderValidation(data.validation, state.timeline);
  renderSectionsPreview(state.timeline);
  updateArtifactSelector();
  setArtifactViewer("");
  renderLaneToggles();
  renderTimeline();

  const audioPath = encodePath(["data", "songs", `${trimmedSong}.mp3`]);
  elements.audioPlayer.src = audioPath;
  elements.audioPlayer.currentTime = 0;
  elements.audioStatus.textContent = `Read-only audio source: ${audioPath}`;
  elements.transportStatus.textContent = "Audio playback time is the shared timeline source of truth.";
  elements.waveformStatus.textContent = "Waveform preview loads in the browser when audio is available.";
  updateTransportReadout();

  const params = new URLSearchParams(window.location.search);
  params.set("song", trimmedSong);
  history.replaceState(null, "", `${window.location.pathname}?${params.toString()}`);

  void ensureWaveform(trimmedSong, audioPath);
}

export async function discoverSongs(preferredSong = "") {
  elements.songSelect.disabled = true;
  elements.songSelect.innerHTML = '<option value="">Discovering artifact directories...</option>';
  try {
    state.availableSongs = await fetchDirectoryListing(["data", "artifacts"]);
    const selectedSong = state.availableSongs.includes(preferredSong) ? preferredSong : "";
    renderSongOptions(selectedSong);
    if (selectedSong) {
      await loadSong(selectedSong);
      return;
    }
    if (!preferredSong && state.availableSongs.length > 0) {
      await loadSong(state.availableSongs[0]);
    }
  } catch (error) {
    state.availableSongs = [];
    elements.songSelect.innerHTML = `<option value="">Song discovery failed: ${escapeHtml(error.message)}</option>`;
    elements.songSelect.disabled = true;
    elements.songSubtitle.textContent = "Could not read /data/artifacts for song discovery.";
  }
}

function bindEventListeners() {
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

  elements.laneToggles.addEventListener("change", (event) => {
    const toggle = event.target.closest("[data-lane-toggle]");
    if (!toggle) {
      return;
    }
    state.laneVisibility[toggle.dataset.laneToggle] = toggle.checked;
    renderTimeline();
  });

  elements.timelineRows.addEventListener("click", handleTimelineClick);
  elements.timelineScroller.addEventListener("scroll", scheduleViewportRender);

  elements.zoomControl.addEventListener("input", (event) => {
    const zoomValue = Number(event.target.value) || DEFAULT_ZOOM;
    state.zoom = Math.min(Math.max(zoomValue, MIN_ZOOM), MAX_ZOOM);
    elements.zoomValue.textContent = `${state.zoom} px/s`;
    renderTimeline();
    if (state.followPlayhead) {
      centerTimeInView(Number(elements.audioPlayer.currentTime || 0));
    }
  });

  elements.followPlayhead.addEventListener("change", (event) => {
    state.followPlayhead = event.target.checked;
  });

  elements.playPause.addEventListener("click", async () => {
    if (!elements.audioPlayer.src) {
      return;
    }
    if (audioDecodeContext && audioDecodeContext.state === "suspended") {
      await audioDecodeContext.resume();
    }
    if (elements.audioPlayer.paused) {
      await elements.audioPlayer.play();
    } else {
      elements.audioPlayer.pause();
    }
  });

  elements.jumpStart.addEventListener("click", () => {
    seekTo(0, {
      laneLabel: "Playback",
      label: "Song Start",
      start_s: 0,
      end_s: 0,
      reference: "playback",
      detail: "jump_start",
      summary: "Playback was returned to the start of the mounted song file.",
    });
  });

  elements.audioPlayer.addEventListener("play", () => {
    elements.playPause.textContent = "Pause";
    startAnimationLoop();
  });

  elements.audioPlayer.addEventListener("pause", () => {
    elements.playPause.textContent = "Play";
    stopAnimationLoop();
    updateNowMarkers();
  });

  elements.audioPlayer.addEventListener("timeupdate", updateNowMarkers);
  elements.audioPlayer.addEventListener("loadedmetadata", updateNowMarkers);
}

export async function initializeApp() {
  initializeTimelineUi();
  elements.followPlayhead.checked = true;
  bindEventListeners();
  const params = new URLSearchParams(window.location.search);
  const requestedSong = params.get("song") || "";
  await discoverSongs(requestedSong);
}