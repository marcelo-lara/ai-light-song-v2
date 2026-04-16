import { laneDefinitions } from "./config.js";

export const waveformCache = new Map();

export const audioDecodeContext = typeof window.AudioContext === "function"
  ? new window.AudioContext()
  : typeof window.webkitAudioContext === "function"
    ? new window.webkitAudioContext()
    : null;

export const elements = {
  songForm: document.querySelector("#song-form"),
  songSelect: document.querySelector("#song-select"),
  refreshSongs: document.querySelector("#refresh-songs"),
  laneToggles: document.querySelector("#lane-toggles"),
  songTitle: document.querySelector("#song-title"),
  songSubtitle: document.querySelector("#song-subtitle"),
  fileStatus: document.querySelector("#file-status"),
  coreArtifactState: document.querySelector("#core-artifact-state"),
  summaryGrid: document.querySelector("#summary-grid"),
  validationSummary: document.querySelector("#validation-summary"),
  sectionsPreview: document.querySelector("#sections-preview"),
  selectionDetail: document.querySelector("#selection-detail"),
  selectionBrief: document.querySelector("#selection-brief"),
  artifactSelect: document.querySelector("#artifact-select"),
  artifactViewer: document.querySelector("#artifact-viewer"),
  metaBpm: document.querySelector("#meta-bpm"),
  metaDuration: document.querySelector("#meta-duration"),
  metaValidation: document.querySelector("#meta-validation"),
  metaViewport: document.querySelector("#meta-viewport"),
  zoomControl: document.querySelector("#zoom-control"),
  zoomValue: document.querySelector("#zoom-value"),
  visibleWindow: document.querySelector("#visible-window"),
  timelineScroller: document.querySelector("#timeline-scroller"),
  timelineRows: document.querySelector("#timeline-rows"),
  audioPlayer: document.querySelector("#audio-player"),
  audioStatus: document.querySelector("#audio-status"),
  waveformStatus: document.querySelector("#waveform-status"),
  playPause: document.querySelector("#play-pause"),
  jumpStart: document.querySelector("#jump-start"),
  followPlayhead: document.querySelector("#follow-playhead"),
  transportNow: document.querySelector("#transport-now"),
  transportBeat: document.querySelector("#transport-beat"),
  transportStatus: document.querySelector("#transport-status"),
};

export const state = {
  availableSongs: [],
  loadedArtifacts: new Map(),
  currentSong: "",
  currentData: {},
  timeline: null,
  zoom: 48,
  laneVisibility: Object.fromEntries(laneDefinitions.map((lane) => [lane.id, lane.id !== "phrases"])),
  selectedRegion: null,
  followPlayhead: true,
  animationFrame: null,
  viewportRenderQueued: false,
};