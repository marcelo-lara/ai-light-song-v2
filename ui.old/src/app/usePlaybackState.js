import { useEffect, useRef, useState } from "preact/hooks";

export function usePlaybackState({ audioRef, playbackFrameRef, audioSrc }) {
  const [currentTime, setCurrentTime] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const currentTimeRef = useRef(0);

  function updateCurrentTime(nextTime) {
    const numericTime = Number(nextTime);
    const safeTime = Number.isFinite(numericTime) && numericTime >= 0 ? numericTime : 0;
    currentTimeRef.current = safeTime;
    setCurrentTime(safeTime);
  }

  useEffect(() => {
    if (!audioRef.current) {
      return;
    }
    if (audioSrc) {
      audioRef.current.src = audioSrc;
      audioRef.current.currentTime = 0;
      return;
    }
    audioRef.current.removeAttribute("src");
    audioRef.current.load();
  }, [audioRef, audioSrc]);

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
      updateCurrentTime(audioElement.currentTime || 0);
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
  }, [audioRef, isPlaying, playbackFrameRef]);

  return {
    currentTime,
    isPlaying,
    setCurrentTime: updateCurrentTime,
    setIsPlaying,
    handleAudioTimeUpdate(event) {
      if (!isPlaying) {
        return;
      }
      updateCurrentTime(Number(event.currentTarget.currentTime || 0));
    },
    handleAudioPlay() {
      updateCurrentTime(Number(audioRef.current?.currentTime || currentTimeRef.current || 0));
      setIsPlaying(true);
    },
    handleAudioPause() {
      updateCurrentTime(Number(audioRef.current?.currentTime || currentTimeRef.current || 0));
      setIsPlaying(false);
    },
    handleAudioLoadedMetadata(event) {
      const audioElement = event.currentTarget;
      if (!isPlaying && currentTimeRef.current > 0) {
        try {
          audioElement.currentTime = currentTimeRef.current;
        } catch {
          // Ignore browsers that reject currentTime writes before media is seekable.
        }
        updateCurrentTime(currentTimeRef.current);
        return;
      }
      updateCurrentTime(Number(audioElement.currentTime || 0));
    },
  };
}