import { useMemo, useRef } from "preact/hooks";

import AppView from "./app/AppView.jsx";
import { createAppViewProps } from "./app/createAppViewProps.js";
import { useSongData } from "./app/useSongData.js";
import { beatAtTime } from "./app/timelineNavigation.js";
import { usePlaybackActions } from "./app/usePlaybackActions.js";
import { usePlaybackState } from "./app/usePlaybackState.js";
import { useShellState } from "./app/useShellState.js";

export default function App() {
  const audioRef = useRef(null);
  const audioDecodeContextRef = useRef(null);
  const playbackFrameRef = useRef(null);
  const shellState = useShellState();

  const {
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
  } = useSongData({
    audioDecodeContextRef,
    onBeforeLoadSong() {
      shellState.handleBeforeLoadSong();
      playback.setCurrentTime(0);
      playback.setIsPlaying(false);
    },
  });

  const playback = usePlaybackState({ audioRef, playbackFrameRef, audioSrc });
  const actions = usePlaybackActions({
    audioRef,
    audioDecodeContextRef,
    timeline,
    currentTime: playback.currentTime,
    setCurrentTime: playback.setCurrentTime,
    setIsPlaying: playback.setIsPlaying,
    setSelectedRegion: shellState.setSelectedRegion,
  });

  const transportBeatLabel = useMemo(() => {
    const beat = beatAtTime(timeline, playback.currentTime);
    return beat ? `Bar ${beat.bar} · Beat ${beat.beat_in_bar}` : "-";
  }, [timeline, playback.currentTime]);

  const audioStatus = audioSrc ? `Read-only audio source: ${audioSrc}` : "Audio source is loaded from data/songs when present.";
  const viewProps = createAppViewProps({
    audioRef,
    audioStatus,
    actions,
    artifactRecords,
    availableAudioSongs,
    availableSongs,
    data,
    discoverSongs,
    isDiscovering,
    loadedSong,
    loadSong,
    playback,
    selectedSong,
    setSelectedSong,
    shellState,
    timeline,
    transportBeatLabel,
    waveformPeaks,
    waveformStatus,
  });

  return <AppView {...viewProps} />;
}