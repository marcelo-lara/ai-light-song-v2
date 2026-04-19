import { formatDuration } from "../lib/utils.js";

export function createSidebarProps(context) {
  const { availableSongs, selectedSong, isDiscovering, setSelectedSong, loadSong, discoverSongs, timeline, shellState, playback, artifactRecords, transportBeatLabel, actions } = context;
  return {
    availableSongs,
    selectedSong,
    isDiscovering,
    onSongChange: (event) => setSelectedSong(event.currentTarget.value),
    onLoadSong: async (event) => { event.preventDefault(); await loadSong(selectedSong); },
    onRefreshSongs: async () => discoverSongs(selectedSong),
    timelineLoaded: Boolean(timeline),
    laneVisibility: shellState.laneVisibility,
    onLaneToggle: shellState.handleLaneToggle,
    currentTimeLabel: formatDuration(playback.currentTime),
    transportBeatLabel,
    followPlayhead: shellState.followPlayhead,
    onFollowPlayheadChange: shellState.handleFollowPlayheadChange,
    onPlayPause: actions.handlePlayPause,
    onJumpStart: actions.handleJumpStart,
    isPlaying: playback.isPlaying,
    fileStatuses: artifactRecords,
    onToggleCollapse: shellState.handleToggleSidebar,
  };
}