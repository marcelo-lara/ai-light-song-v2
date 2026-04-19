import { getAudioDecodeContext, resolvedPlaybackTime } from "./audio.js";
import {
  nextBeatTime,
  nextMarkerTime,
  previousBeatTime,
  previousMarkerTime,
} from "./timelineNavigation.js";
import { buildPlaybackSelection } from "./playbackSelection.js";
import { clamp, formatDuration } from "../lib/utils.js";

export function usePlaybackActions({ audioRef, audioDecodeContextRef, timeline, currentTime, setCurrentTime, setIsPlaying, setSelectedRegion }) {
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
      return;
    }
    audioRef.current.pause();
    setIsPlaying(false);
  }

  return {
    seekTo,
    handlePlayPause,
    handleJumpStart() {
      seekTo(0, buildPlaybackSelection("Song Start", 0, "jump_start", "Playback was returned to the start of the mounted song file."));
    },
    handlePreviousBeat() {
      const time = previousBeatTime(timeline, resolvedPlaybackTime(audioRef.current, currentTime), 0);
      seekTo(time, buildPlaybackSelection(`Previous Beat ${formatDuration(time)}`, time, "previous_beat", "Playback moved to the previous detected beat on the shared timeline."));
    },
    handleNextBeat() {
      const fallback = Number(timeline?.duration || audioRef.current?.duration || currentTime || 0);
      const time = nextBeatTime(timeline, resolvedPlaybackTime(audioRef.current, currentTime), fallback);
      seekTo(time, buildPlaybackSelection(`Next Beat ${formatDuration(time)}`, time, "next_beat", "Playback moved to the next detected beat on the shared timeline."));
    },
    handlePreviousBar() {
      const time = previousMarkerTime(timeline?.bars, currentTime, (bar) => bar.start_s, 0);
      seekTo(time, buildPlaybackSelection(`Previous Bar ${formatDuration(time)}`, time, "previous_bar", "Playback moved to the previous bar boundary on the shared timeline."));
    },
    handleNextBar() {
      const fallback = Number(timeline?.duration || audioRef.current?.duration || currentTime || 0);
      const time = nextMarkerTime(timeline?.bars, currentTime, (bar) => bar.start_s, fallback);
      seekTo(time, buildPlaybackSelection(`Next Bar ${formatDuration(time)}`, time, "next_bar", "Playback moved to the next bar boundary on the shared timeline."));
    },
  };
}