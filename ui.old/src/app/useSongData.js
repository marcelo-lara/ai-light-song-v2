import { useEffect, useRef, useState } from "preact/hooks";

import { buildTimelineData } from "../lib/data.js";
import { encodePath } from "../lib/utils.js";
import { discoverAvailableSongs, humanHintsPath, loadArtifactRecords, saveHumanHintsFile } from "./songDataApi.js";
import { createEnsureWaveform } from "./waveformPreview.js";

export function useSongData({ audioDecodeContextRef, onBeforeLoadSong }) {
  const waveformCacheRef = useRef(new Map());
  const latestSongRef = useRef("");

  const [availableSongs, setAvailableSongs] = useState([]);
  const [availableAudioSongs, setAvailableAudioSongs] = useState([]);
  const [isDiscovering, setIsDiscovering] = useState(true);
  const [selectedSong, setSelectedSong] = useState("");
  const [loadedSong, setLoadedSong] = useState("");
  const [artifactRecords, setArtifactRecords] = useState([]);
  const [data, setData] = useState({});
  const [timeline, setTimeline] = useState(null);
  const [audioSrc, setAudioSrc] = useState("");
  const [waveformStatus, setWaveformStatus] = useState("Waveform preview loads in the browser when audio is available.");
  const [waveformPeaks, setWaveformPeaks] = useState(null);
  const ensureWaveform = createEnsureWaveform({ audioDecodeContextRef, waveformCacheRef, latestSongRef, setWaveformStatus, setWaveformPeaks });

  async function loadSong(song) {
    const trimmedSong = song.trim();
    if (!trimmedSong) {
      return;
    }

    onBeforeLoadSong?.(trimmedSong);
    latestSongRef.current = trimmedSong;
    setSelectedSong(trimmedSong);
    setLoadedSong(trimmedSong);
    setWaveformPeaks(waveformCacheRef.current.get(trimmedSong) || null);

    const nextRecords = await loadArtifactRecords(trimmedSong);

    const nextData = Object.fromEntries(nextRecords.filter((record) => record.ok).map((record) => [record.key, record.data]));
    const nextTimeline = buildTimelineData(nextData);
    const nextAudioSrc = encodePath(["data", "songs", `${trimmedSong}.mp3`]);

    setArtifactRecords(nextRecords);
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
      const { availableSongs: discoveredSongs, availableAudioSongs: discoveredAudioSongs } = await discoverAvailableSongs();
      setAvailableSongs(discoveredSongs);
      setAvailableAudioSongs(discoveredAudioSongs);
      const nextSelectedSong = discoveredSongs.includes(preferredSong) ? preferredSong : "";
      if (nextSelectedSong) {
        await loadSong(nextSelectedSong);
      } else if (!preferredSong && discoveredSongs.length > 0) {
        await loadSong(discoveredSongs[0]);
      } else {
        setSelectedSong(nextSelectedSong);
      }
    } finally {
      setIsDiscovering(false);
    }
  }

  async function saveHumanHints(payload) {
    if (!selectedSong) {
      throw new Error("Select a song before saving human hints.");
    }

    const savedPayload = await saveHumanHintsFile(selectedSong, payload);

    setData((current) => {
      const nextData = { ...current, humanHints: savedPayload };
      setTimeline(buildTimelineData(nextData));
      return nextData;
    });

    setArtifactRecords((current) => {
      const recordIndex = current.findIndex((record) => record.key === "humanHints");
      const nextRecord = {
        key: "humanHints",
        label: "Reference Human Hints",
        path: humanHintsPath(selectedSong),
        ok: true,
        data: savedPayload,
      };
      if (recordIndex === -1) {
        return [...current, nextRecord].sort((left, right) => left.label.localeCompare(right.label));
      }
      return current.map((record, index) => index === recordIndex ? nextRecord : record);
    });

    return savedPayload;
  }

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    void discoverSongs(params.get("song") || "");
  }, []);

  return {
    availableSongs,
    availableAudioSongs,
    isDiscovering,
    selectedSong,
    setSelectedSong,
    loadedSong,
    artifactRecords,
    data,
    timeline,
    audioSrc,
    waveformStatus,
    waveformPeaks,
    loadSong,
    discoverSongs,
    saveHumanHints,
  };
}