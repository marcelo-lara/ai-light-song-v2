import { useEffect, useState } from "preact/hooks";

export function usePlaybackState({ audioRef, playbackFrameRef, audioSrc }) {
  const [currentTime, setCurrentTime] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);

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
  }, [audioRef, isPlaying, playbackFrameRef]);

  return {
    currentTime,
    isPlaying,
    setCurrentTime,
    setIsPlaying,
    handleAudioTimeUpdate(event) { setCurrentTime(Number(event.currentTarget.currentTime || 0)); },
    handleAudioPlay() {
      setCurrentTime(Number(audioRef.current?.currentTime || 0));
      setIsPlaying(true);
    },
    handleAudioPause() {
      setCurrentTime(Number(audioRef.current?.currentTime || 0));
      setIsPlaying(false);
    },
    handleAudioLoadedMetadata(event) { setCurrentTime(Number(event.currentTarget.currentTime || 0)); },
  };
}