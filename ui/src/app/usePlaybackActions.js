import { getAudioDecodeContext, resolvedPlaybackTime } from "./audio.js";
import {
  nextBeatTime,
  nextMarkerTime,
  previousBeatTime,
  previousMarkerTime,
} from "./timelineNavigation.js";
import { buildPlaybackSelection } from "./playbackSelection.js";
import { clamp, formatDuration } from "../lib/utils.js";

function onceEvent(target, eventName, handler, options) {
  target.addEventListener(eventName, handler, options);
  return () => target.removeEventListener(eventName, handler, options);
}

async function ensureAudioMetadata(audioElement) {
  if (audioElement.readyState >= 1) {
    return;
  }

  await new Promise((resolve) => {
    let timeoutId = 0;
    const finish = () => {
      cleanup();
      resolve();
    };
    const removers = [
      onceEvent(audioElement, "loadedmetadata", finish, { once: true }),
      onceEvent(audioElement, "error", finish, { once: true }),
    ];
    const cleanup = () => {
      clearTimeout(timeoutId);
      removers.forEach((remove) => remove());
    };
    timeoutId = window.setTimeout(finish, 5000);
    audioElement.load();
  });
}

async function ensureAudioSeek(audioElement, targetTime) {
  const clampedTarget = Math.max(0, Number(targetTime) || 0);
  if (Math.abs(Number(audioElement.currentTime || 0) - clampedTarget) <= 0.05) {
    return;
  }

  await new Promise((resolve) => {
    let timeoutId = 0;
    const finish = () => {
      cleanup();
      resolve();
    };
    const cleanup = () => {
      clearTimeout(timeoutId);
      removers.forEach((remove) => remove());
    };
    const maybeFinish = () => {
      if (Math.abs(Number(audioElement.currentTime || 0) - clampedTarget) <= 0.05) {
        finish();
      }
    };
    const removers = [
      onceEvent(audioElement, "seeked", finish, { once: true }),
      onceEvent(audioElement, "timeupdate", maybeFinish),
      onceEvent(audioElement, "error", finish, { once: true }),
    ];
    timeoutId = window.setTimeout(finish, 750);
    try {
      audioElement.currentTime = clampedTarget;
    } catch {
      finish();
      return;
    }
    maybeFinish();
  });
}

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
    const audioElement = audioRef.current;
    const duration = Number(timeline?.duration || audioElement.duration || currentTime || 0);
    const clampedTime = clamp(Number(currentTime) || 0, 0, duration);
    const audioDecodeContext = getAudioDecodeContext(audioDecodeContextRef.current);
    audioDecodeContextRef.current = audioDecodeContext;
    if (audioDecodeContext && audioDecodeContext.state === "suspended") {
      await audioDecodeContext.resume();
    }
    if (audioElement.paused) {
      await ensureAudioMetadata(audioElement);
      await ensureAudioSeek(audioElement, clampedTime);
      setCurrentTime(clampedTime);
      await audioElement.play();
      return;
    }
    audioElement.pause();
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