export function createOverviewProps(context) {
  const { loadedSong, data, timeline, artifactRecords, shellState, waveformStatus, audioStatus, audioRef, playback } = context;
  return {
    loadedSong,
    data,
    timeline,
    artifactRecords,
    visibleWindowLabel: shellState.metaViewportText,
    waveformStatus,
    audioStatus,
    audioRef,
    onAudioTimeUpdate: playback.handleAudioTimeUpdate,
    onAudioPlay: playback.handleAudioPlay,
    onAudioPause: playback.handleAudioPause,
    onAudioLoadedMetadata: playback.handleAudioLoadedMetadata,
  };
}