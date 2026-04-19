import { useEffect, useMemo, useRef, useState } from "preact/hooks";

import DetailPanels from "./components/DetailPanels.jsx";
import OverlayPanel from "./components/OverlayPanel.jsx";
import OverviewPanels from "./components/OverviewPanels.jsx";
import SelectionDetailCard from "./components/SelectionDetailCard.jsx";
import Sidebar from "./components/Sidebar.jsx";
import TimelinePanel from "./components/TimelinePanel.jsx";
import { DEFAULT_ZOOM, artifactDefinitions, laneDefinitions } from "./lib/config.js";
import { buildTimelineData, fetchDirectoryFiles, fetchDirectoryListing, fetchJson } from "./lib/data.js";
import { clamp, encodePath, formatDuration, formatRange } from "./lib/utils.js";

function createInitialLaneVisibility() {
  return Object.fromEntries(laneDefinitions.map((lane) => [lane.id, lane.id !== "phrases"]));
}

function createInitialLaneCollapsed() {
  return Object.fromEntries(laneDefinitions.map((lane) => [lane.id, false]));
}

function getAudioDecodeContext(existing) {
  if (existing) {
    return existing;
  }
  if (typeof window.AudioContext === "function") {
    return new window.AudioContext();
  }
  if (typeof window.webkitAudioContext === "function") {
    return new window.webkitAudioContext();
  }
  return null;
}

function beatAtTime(timeline, time) {
  if (!timeline) {
    return null;
  }
  for (let index = 0; index < timeline.beats.length; index += 1) {
    const beat = timeline.beats[index];
    const next = timeline.beats[index + 1];
    const end = next ? next.time : timeline.duration;
    if (beat.time <= time && time < end) {
      return beat;
    }
  }
  return timeline.beats.at(-1) || null;
}

function beatIndexAtTime(timeline, time) {
  if (!timeline || !Array.isArray(timeline.beats) || timeline.beats.length === 0) {
    return null;
  }
  for (let index = 0; index < timeline.beats.length; index += 1) {
    const beat = timeline.beats[index];
    const next = timeline.beats[index + 1];
    const end = next ? Number(next.time) : Number(timeline.duration);
    if (Number(beat.time) <= Number(time) && Number(time) < end) {
      return index;
    }
  }
  return timeline.beats.length - 1;
}

function resolvedPlaybackTime(audioElement, currentTime) {
  const audioTime = Number(audioElement?.currentTime);
  const stateTime = Number(currentTime ?? 0);
  if (!Number.isFinite(audioTime)) {
    return stateTime;
  }
  if (Math.abs(audioTime - stateTime) <= 0.05) {
    return Math.max(audioTime, stateTime);
  }
  return audioTime;
}

function previousBeatTime(timeline, currentTime, fallback = 0) {
  if (!timeline || !Array.isArray(timeline.beats) || timeline.beats.length === 0) {
    return fallback;
  }
  const threshold = Number(currentTime) - 0.001;
  for (let index = timeline.beats.length - 1; index >= 0; index -= 1) {
    const markerTime = Number(timeline.beats[index]?.time);
    if (markerTime < threshold) {
      return markerTime;
    }
  }
  return fallback;
}

function nextBeatTime(timeline, currentTime, fallback = 0) {
  if (!timeline || !Array.isArray(timeline.beats) || timeline.beats.length === 0) {
    return fallback;
  }
  const threshold = Number(currentTime) + 0.001;
  for (const beat of timeline.beats) {
    const markerTime = Number(beat?.time);
    if (markerTime > threshold) {
      return markerTime;
    }
  }
  return fallback;
}

function previousMarkerTime(rows, currentTime, getTime, fallback = 0) {
  if (!Array.isArray(rows) || rows.length === 0) {
    return fallback;
  }
  const threshold = Number(currentTime) - 0.05;
  for (let index = rows.length - 1; index >= 0; index -= 1) {
    const markerTime = Number(getTime(rows[index]));
    if (markerTime < threshold) {
      return markerTime;
    }
  }
  return fallback;
}

function nextMarkerTime(rows, currentTime, getTime, fallback = 0) {
  if (!Array.isArray(rows) || rows.length === 0) {
    return fallback;
  }
  const threshold = Number(currentTime) + 0.05;
  for (const row of rows) {
    const markerTime = Number(getTime(row));
    if (markerTime > threshold) {
      return markerTime;
    }
  }
  return fallback;
}

function buildWaveformEnvelope(audioBuffer) {
  const channelCount = Math.max(1, Number(audioBuffer.numberOfChannels || 1));
  const channels = Array.from({ length: channelCount }, (_, index) => audioBuffer.getChannelData(index));
  const sampleCount = Math.max(4096, Math.min(16384, Math.floor(audioBuffer.duration * 240)));
  const blockSize = Math.max(1, Math.floor(audioBuffer.length / sampleCount));
  const envelope = [];

  for (let index = 0; index < sampleCount; index += 1) {
    const start = index * blockSize;
    const end = Math.min(audioBuffer.length, start + blockSize);
    let min = 1;
    let max = -1;

    for (let offset = start; offset < end; offset += 1) {
      for (const channel of channels) {
        const sample = channel[offset] || 0;
        if (sample < min) {
          min = sample;
        }
        if (sample > max) {
          max = sample;
        }
      }
    }

    envelope.push({
      min: Math.max(-1, min),
      max: Math.min(1, max),
    });
  }

  return envelope;
}

export default function App() {
  const audioRef = useRef(null);
  const waveformCacheRef = useRef(new Map());
  const audioDecodeContextRef = useRef(null);
  const latestSongRef = useRef("");
  const playbackFrameRef = useRef(null);

  const [availableSongs, setAvailableSongs] = useState([]);
  const [availableAudioSongs, setAvailableAudioSongs] = useState([]);
  const [isDiscovering, setIsDiscovering] = useState(true);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(true);
  const [selectedSong, setSelectedSong] = useState("");
  const [loadedSong, setLoadedSong] = useState("");
  const [artifactRecords, setArtifactRecords] = useState([]);
  const [data, setData] = useState({});
  const [timeline, setTimeline] = useState(null);
  const [selectedArtifactKey, setSelectedArtifactKey] = useState("");
  const [selectedRegion, setSelectedRegion] = useState(null);
  const [overlaySelection, setOverlaySelection] = useState(null);
  const [overlayAnchor, setOverlayAnchor] = useState(null);
  const [laneVisibility, setLaneVisibility] = useState(createInitialLaneVisibility);
  const [laneCollapsed, setLaneCollapsed] = useState(createInitialLaneCollapsed);
  const [zoom, setZoom] = useState(DEFAULT_ZOOM);
  const [followPlayhead, setFollowPlayhead] = useState(true);
  const [currentTime, setCurrentTime] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [audioSrc, setAudioSrc] = useState("");
  const [waveformStatus, setWaveformStatus] = useState("Waveform preview loads in the browser when audio is available.");
  const [waveformPeaks, setWaveformPeaks] = useState(null);
  const [visibleWindowText, setVisibleWindowText] = useState("Visible 0:00.0-0:00.0");
  const [metaViewportText, setMetaViewportText] = useState("-");

  const transportBeatLabel = useMemo(() => {
    const beat = beatAtTime(timeline, currentTime);
    return beat ? `Bar ${beat.bar} · Beat ${beat.beat_in_bar}` : "-";
  }, [timeline, currentTime]);

  const audioStatus = audioSrc ? `Read-only audio source: ${audioSrc}` : "Audio source is loaded from data/songs when present.";

  async function ensureWaveform(song, nextAudioPath) {
    const audioDecodeContext = getAudioDecodeContext(audioDecodeContextRef.current);
    audioDecodeContextRef.current = audioDecodeContext;

    if (!audioDecodeContext) {
      setWaveformStatus("Waveform preview loads in the browser when audio is available.");
      setWaveformPeaks(null);
      return;
    }

    if (waveformCacheRef.current.has(song)) {
      setWaveformPeaks(waveformCacheRef.current.get(song));
      setWaveformStatus("Waveform decoded in the browser from the mounted song file.");
      return;
    }

    setWaveformStatus("Decoding audio in the browser for waveform anchoring...");
    try {
      const response = await fetch(nextAudioPath, { cache: "force-cache" });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const buffer = await response.arrayBuffer();
      const audioBuffer = await audioDecodeContext.decodeAudioData(buffer.slice(0));
      const peaks = buildWaveformEnvelope(audioBuffer);
      waveformCacheRef.current.set(song, peaks);
      if (latestSongRef.current === song) {
        setWaveformPeaks(peaks);
        setWaveformStatus("Waveform decoded in the browser from the mounted song file.");
      }
    } catch (error) {
      if (latestSongRef.current === song) {
        setWaveformPeaks(null);
        setWaveformStatus(`Waveform unavailable: ${error.message}. Falling back to beat pulses.`);
      }
    }
  }

  async function loadSong(song) {
    const trimmedSong = song.trim();
    if (!trimmedSong) {
      return;
    }

    latestSongRef.current = trimmedSong;
    setSelectedSong(trimmedSong);
    setLoadedSong(trimmedSong);
    setSelectedRegion(null);
    setOverlaySelection(null);
    setOverlayAnchor(null);
    setSelectedArtifactKey("");
    setCurrentTime(0);
    setIsPlaying(false);
    setWaveformPeaks(waveformCacheRef.current.get(trimmedSong) || null);

    const nextRecords = await Promise.all(artifactDefinitions.map(async (definition) => {
      const parts = definition.path(trimmedSong);
      const path = encodePath(parts);
      try {
        const result = await fetchJson(parts);
        return {
          key: definition.key,
          label: definition.label,
          path,
          ok: true,
          data: result,
        };
      } catch (error) {
        return {
          key: definition.key,
          label: definition.label,
          path,
          ok: false,
          error: error.message,
          data: null,
        };
      }
    }));

    const nextData = Object.fromEntries(nextRecords.filter((record) => record.ok).map((record) => [record.key, record.data]));
    const nextTimeline = buildTimelineData(nextData);
    const nextAudioSrc = encodePath(["data", "songs", `${trimmedSong}.mp3`]);

    setArtifactRecords(nextRecords.sort((left, right) => left.label.localeCompare(right.label)));
    setData(nextData);
    setTimeline(nextTimeline);
    setAudioSrc(nextAudioSrc);
    setWaveformStatus("Waveform preview loads in the browser when audio is available.");

    const params = new URLSearchParams(window.location.search);
    params.set("song", trimmedSong);
    history.replaceState(null, "", `${window.location.pathname}?${params.toString()}`);

    await ensureWaveform(trimmedSong, nextAudioSrc);
  }

  async function discoverSongs(preferredSong = "") {
    setIsDiscovering(true);
    try {
      const [discoveredSongs, discoveredAudioSongs] = await Promise.all([
        fetchDirectoryListing(["data", "artifacts"]),
        fetchDirectoryFiles(["data", "songs"], [".mp3", ".wav", ".flac", ".m4a", ".ogg"]),
      ]);
      setAvailableSongs(discoveredSongs);
      setAvailableAudioSongs(discoveredAudioSongs);
      const selectedSong = discoveredSongs.includes(preferredSong) ? preferredSong : "";
      if (selectedSong) {
        await loadSong(selectedSong);
      } else if (!preferredSong && discoveredSongs.length > 0) {
        await loadSong(discoveredSongs[0]);
      } else {
        setSelectedSong(selectedSong);
      }
    } finally {
      setIsDiscovering(false);
    }
  }

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    void discoverSongs(params.get("song") || "");
  }, []);

  useEffect(() => {
    if (!audioRef.current) {
      return;
    }
    if (audioSrc) {
      audioRef.current.src = audioSrc;
      audioRef.current.currentTime = 0;
    } else {
      audioRef.current.removeAttribute("src");
      audioRef.current.load();
    }
  }, [audioSrc]);

  useEffect(() => {
    function cancelPlaybackFrame() {
      if (playbackFrameRef.current) {
        cancelAnimationFrame(playbackFrameRef.current);
        playbackFrameRef.current = null;
      }
    }

    function syncPlaybackFrame() {
      const audioElement = audioRef.current;
      if (!audioElement) {
        cancelPlaybackFrame();
        return;
      }

      setCurrentTime(audioElement.currentTime || 0);

      if (!audioElement.paused && !audioElement.ended) {
        playbackFrameRef.current = requestAnimationFrame(syncPlaybackFrame);
        return;
      }

      playbackFrameRef.current = null;
    }

    if (isPlaying) {
      playbackFrameRef.current = requestAnimationFrame(syncPlaybackFrame);
    } else {
      cancelPlaybackFrame();
    }

    return cancelPlaybackFrame;
  }, [isPlaying]);

  function handleSongChange(event) {
    setSelectedSong(event.currentTarget.value);
  }

  async function handleLoadSong(event) {
    event.preventDefault();
    await loadSong(selectedSong);
  }

  async function handleRefreshSongs() {
    await discoverSongs(selectedSong);
  }

  function handleLaneToggle(laneId, checked) {
    setLaneVisibility((current) => ({ ...current, [laneId]: checked }));
  }

  function handleLaneCollapsedToggle(laneId) {
    setLaneCollapsed((current) => ({ ...current, [laneId]: !current[laneId] }));
  }

  function handleFollowPlayheadChange(event) {
    setFollowPlayhead(event.currentTarget.checked);
  }

  async function handlePlayPause() {
    if (!audioRef.current?.src) {
      return;
    }
    const audioDecodeContext = getAudioDecodeContext(audioDecodeContextRef.current);
    audioDecodeContextRef.current = audioDecodeContext;
    if (audioDecodeContext && audioDecodeContext.state === "suspended") {
      await audioDecodeContext.resume();
    }
    if (audioRef.current.paused) {
      await audioRef.current.play();
    } else {
      audioRef.current.pause();
    }
  }

  function seekTo(time, selection = null) {
    const duration = Number(timeline?.duration || audioRef.current?.duration || 0);
    const clampedTime = clamp(Number(time) || 0, 0, duration);
    if (audioRef.current) {
      audioRef.current.currentTime = clampedTime;
    }
    setCurrentTime(clampedTime);
    if (selection) {
      setSelectedRegion(selection);
    }
  }

  function handleJumpStart() {
    seekTo(0, {
      laneLabel: "Playback",
      label: "Song Start",
      start_s: 0,
      end_s: 0,
      reference: "playback",
      detail: "jump_start",
      summary: "Playback was returned to the start of the mounted song file.",
    });
  }

  function handlePreviousBeat() {
    const playbackTime = resolvedPlaybackTime(audioRef.current, currentTime);
    const targetTime = previousBeatTime(timeline, playbackTime, 0);
    seekTo(targetTime, {
      laneLabel: "Playback",
      label: `Previous Beat ${formatDuration(targetTime)}`,
      start_s: targetTime,
      end_s: targetTime,
      reference: "playback",
      detail: "previous_beat",
      summary: "Playback moved to the previous detected beat on the shared timeline.",
    });
  }

  function handleNextBeat() {
    const playbackTime = resolvedPlaybackTime(audioRef.current, currentTime);
    const fallback = Number(timeline?.duration || audioRef.current?.duration || currentTime || 0);
    const targetTime = nextBeatTime(timeline, playbackTime, fallback);
    seekTo(targetTime, {
      laneLabel: "Playback",
      label: `Next Beat ${formatDuration(targetTime)}`,
      start_s: targetTime,
      end_s: targetTime,
      reference: "playback",
      detail: "next_beat",
      summary: "Playback moved to the next detected beat on the shared timeline.",
    });
  }

  function handlePreviousBar() {
    const targetTime = previousMarkerTime(timeline?.bars, currentTime, (bar) => bar.start_s, 0);
    seekTo(targetTime, {
      laneLabel: "Playback",
      label: `Previous Bar ${formatDuration(targetTime)}`,
      start_s: targetTime,
      end_s: targetTime,
      reference: "playback",
      detail: "previous_bar",
      summary: "Playback moved to the previous bar boundary on the shared timeline.",
    });
  }

  function handleNextBar() {
    const fallback = Number(timeline?.duration || audioRef.current?.duration || currentTime || 0);
    const targetTime = nextMarkerTime(timeline?.bars, currentTime, (bar) => bar.start_s, fallback);
    seekTo(targetTime, {
      laneLabel: "Playback",
      label: `Next Bar ${formatDuration(targetTime)}`,
      start_s: targetTime,
      end_s: targetTime,
      reference: "playback",
      detail: "next_bar",
      summary: "Playback moved to the next bar boundary on the shared timeline.",
    });
  }

  function handleAudioTimeUpdate(event) {
    setCurrentTime(Number(event.currentTarget.currentTime || 0));
  }

  function handleAudioPlay() {
    setCurrentTime(Number(audioRef.current?.currentTime || 0));
    setIsPlaying(true);
  }

  function handleAudioPause() {
    setCurrentTime(Number(audioRef.current?.currentTime || 0));
    setIsPlaying(false);
  }

  function handleAudioLoadedMetadata(event) {
    setCurrentTime(Number(event.currentTarget.currentTime || 0));
  }

  function handleVisibleWindowChange(nextVisibleWindowText, nextMetaViewportText) {
    setVisibleWindowText(nextVisibleWindowText);
    setMetaViewportText(nextMetaViewportText);
  }

  function handleOpenSelectionOverlay(selection, anchorPosition) {
    setOverlaySelection(selection);
    setOverlayAnchor(anchorPosition || null);
  }

  function handleCloseSelectionOverlay() {
    setOverlaySelection(null);
    setOverlayAnchor(null);
  }

  async function handleHeaderSongSelect(song) {
    await loadSong(song);
  }

  function handleToggleSidebar() {
    setIsSidebarCollapsed((current) => !current);
  }

  return (
    <>
      <div className={`shell${isSidebarCollapsed ? " sidebar-collapsed" : ""}`}>
        <Sidebar
          availableSongs={availableSongs}
          selectedSong={selectedSong}
          isDiscovering={isDiscovering}
          onSongChange={handleSongChange}
          onLoadSong={handleLoadSong}
          onRefreshSongs={handleRefreshSongs}
          timelineLoaded={Boolean(timeline)}
          laneVisibility={laneVisibility}
          onLaneToggle={handleLaneToggle}
          currentTimeLabel={formatDuration(currentTime)}
          transportBeatLabel={transportBeatLabel}
          followPlayhead={followPlayhead}
          onFollowPlayheadChange={handleFollowPlayheadChange}
          onPlayPause={handlePlayPause}
          onJumpStart={handleJumpStart}
          isPlaying={isPlaying}
          fileStatuses={artifactRecords}
          onToggleCollapse={handleToggleSidebar}
        />

        <div>
          <main className="main">
            <TimelinePanel
              loadedSong={loadedSong}
              availableAudioSongs={availableAudioSongs}
              timeline={timeline}
              zoom={zoom}
              onZoomChange={setZoom}
              selection={{ region: selectedRegion, visibleWindowLabel: visibleWindowText }}
              currentTime={currentTime}
              isPlaying={isPlaying}
              followPlayhead={followPlayhead}
              onSeek={seekTo}
              onPlayPause={handlePlayPause}
              onJumpStart={handleJumpStart}
              onPreviousBar={handlePreviousBar}
              onPreviousBeat={handlePreviousBeat}
              onNextBeat={handleNextBeat}
              onNextBar={handleNextBar}
              onHeaderSongSelect={handleHeaderSongSelect}
              isSidebarCollapsed={isSidebarCollapsed}
              onToggleSidebar={handleToggleSidebar}
              onOpenSelectionOverlay={handleOpenSelectionOverlay}
              onCloseSelectionOverlay={handleCloseSelectionOverlay}
              onVisibleWindowChange={handleVisibleWindowChange}
              laneVisibility={laneVisibility}
              laneCollapsed={laneCollapsed}
              onToggleLaneCollapsed={handleLaneCollapsedToggle}
              waveformPeaks={waveformPeaks}
            />

            <DetailPanels
              artifactRecords={artifactRecords}
              selectedArtifactKey={selectedArtifactKey}
              onSelectArtifact={(event) => setSelectedArtifactKey(event.currentTarget.value)}
              selection={selectedRegion}
            />

            <OverviewPanels
              loadedSong={loadedSong}
              data={data}
              timeline={timeline}
              artifactRecords={artifactRecords}
              visibleWindowLabel={metaViewportText}
              waveformStatus={waveformStatus}
              audioStatus={audioStatus}
              audioRef={audioRef}
              onAudioTimeUpdate={handleAudioTimeUpdate}
              onAudioPlay={handleAudioPlay}
              onAudioPause={handleAudioPause}
              onAudioLoadedMetadata={handleAudioLoadedMetadata}
            />

          </main>
        </div>
      </div>

      <OverlayPanel
        isOpen={Boolean(overlaySelection)}
        title={overlaySelection?.label || "Selection Detail"}
        subtitle={overlaySelection ? `${overlaySelection.laneLabel} · ${formatRange(overlaySelection.start_s, overlaySelection.end_s)}` : ""}
        anchorPosition={overlayAnchor}
        onClose={handleCloseSelectionOverlay}
      >
        <SelectionDetailCard selection={overlaySelection} emptyMessage="Click a lane item to inspect it here." />
      </OverlayPanel>
    </>
  );
}