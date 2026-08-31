// useTransport.ts — the master clock.
//
// wavesurfer.js owns audio + waveform + the single `currentTime` the whole
// timeline follows. This hook creates one WaveSurfer instance per song, keeps
// its render surface alive across lane collapse/hide (the surface is an
// imperatively-created <div> the hook owns, mounted into WaveformLane), and
// exposes a transport API whose `currentTime` is driven ONLY by wavesurfer
// events — `audioprocess` (playback), `seeking` (programmatic + scrub) and
// `interaction` (waveform click). There is NO requestAnimationFrame position
// loop.
//
// `stepBeat` / `stepBar` resolve against the real beat list / bar lines from
// coords. The pure resolvers (`nextBeatTime`, `nextBarTime`) are unit-tested.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import WaveSurfer from "wavesurfer.js";

import type { Coords } from "./coords";

// design notes §3a — Nocturne blurple, not the previous app's teal.
export const WAVE_COLOR = "#968ae0"; // --color-accent-500
export const WAVE_PROGRESS_COLOR = "#d2cefd"; // --color-accent-300
export const WAVE_HEIGHT = 84; // TRACK_HEIGHT

// --- pure step resolvers (unit-tested) -----------------------------------

export interface TimePoint {
  time: number;
}

/**
 * Time of the beat `dir` steps from the beat currently under `currentTime`
 * (`beatIndexAtTime` from coords), clamped to the list. `null` when there are
 * no beats.
 */
export function nextBeatTime(
  beats: readonly TimePoint[],
  beatIndexAtTime: (t: number) => number,
  currentTime: number,
  dir: 1 | -1,
): number | null {
  if (beats.length === 0) return null;
  const i = beatIndexAtTime(currentTime);
  const base = i < 0 ? 0 : i;
  const j = Math.max(0, Math.min(base + dir, beats.length - 1));
  return beats[j]?.time ?? null;
}

/**
 * Time of the next / previous bar line relative to `currentTime` (a small
 * epsilon keeps "previous" from snapping to the line the playhead sits on).
 * `null` when there are no bar lines.
 */
export function nextBarTime(
  barLines: readonly TimePoint[],
  currentTime: number,
  dir: 1 | -1,
): number | null {
  if (barLines.length === 0) return null;
  const t = currentTime;
  const line =
    dir === 1
      ? barLines.find((l) => l.time > t + 1e-3)
      : [...barLines].reverse().find((l) => l.time < t - 1e-3);
  return line ? line.time : null;
}

// --- the hook -----------------------------------------------------------

export interface TransportInput {
  /** `/data/songs/<song>.mp3` — or null when no song is selected */
  audioUrl: string | null;
  coords: Coords;
}

export interface Transport {
  currentTime: number;
  isPlaying: boolean;
  duration: number;
  isReady: boolean;
  error: string | null;
  /** the wavesurfer render surface — WaveformLane mounts this into its body */
  surface: HTMLDivElement | null;
  play(): void;
  pause(): void;
  togglePlay(): void;
  seekTo(time: number): void;
  seekToBeat(beatIndex: number): void;
  stepBeat(dir: 1 | -1): void;
  stepBar(dir: 1 | -1): void;
}

export function useTransport({ audioUrl, coords }: TransportInput): Transport {
  const wsRef = useRef<WaveSurfer | null>(null);

  // The render surface is owned here (not by WaveformLane) so the wavesurfer
  // instance and its audio survive the lane being collapsed or hidden.
  const surfaceRef = useRef<HTMLDivElement | null>(null);
  if (surfaceRef.current === null && typeof document !== "undefined") {
    const el = document.createElement("div");
    el.className = "tl-waveform__surface";
    surfaceRef.current = el;
  }

  const [currentTime, setCurrentTime] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [wsDuration, setWsDuration] = useState(0);
  const [isReady, setIsReady] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // (re)create wavesurfer whenever the song's audio changes
  useEffect(() => {
    const surface = surfaceRef.current;
    if (!surface || !audioUrl) {
      setIsReady(false);
      setCurrentTime(0);
      setIsPlaying(false);
      setWsDuration(0);
      setError(null);
      return;
    }

    setIsReady(false);
    setCurrentTime(0);
    setIsPlaying(false);
    setError(null);

    const ws = WaveSurfer.create({
      container: surface,
      url: audioUrl,
      height: WAVE_HEIGHT,
      width: Math.max(coords.timelineW, 1),
      fillParent: false,
      hideScrollbar: true,
      autoScroll: false,
      autoCenter: false,
      normalize: true,
      interact: true,
      dragToSeek: true,
      waveColor: WAVE_COLOR,
      progressColor: WAVE_PROGRESS_COLOR,
      cursorWidth: 0, // shared playhead is drawn by the timeline shell
    });
    wsRef.current = ws;

    const onReady = () => {
      setIsReady(true);
      setWsDuration(ws.getDuration());
    };
    const onAudioprocess = (t: number) => setCurrentTime(t);
    const onSeeking = (t: number) => setCurrentTime(t);
    const onInteraction = (t: number) => setCurrentTime(t);
    const onPlay = () => setIsPlaying(true);
    const onPause = () => setIsPlaying(false);
    const onFinish = () => setIsPlaying(false);
    const onError = (err: Error) =>
      setError(err?.message ?? "Failed to load audio.");

    ws.on("ready", onReady);
    ws.on("audioprocess", onAudioprocess);
    ws.on("seeking", onSeeking);
    ws.on("interaction", onInteraction);
    ws.on("play", onPlay);
    ws.on("pause", onPause);
    ws.on("finish", onFinish);
    ws.on("error", onError);

    return () => {
      wsRef.current = null;
      ws.destroy();
    };
    // timelineW intentionally omitted — width changes are applied below, not by
    // rebuilding the instance.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [audioUrl]);

  // redraw on zoom — resize the existing instance, never rebuild it
  useEffect(() => {
    const ws = wsRef.current;
    if (ws && isReady) ws.setOptions({ width: Math.max(coords.timelineW, 1) });
  }, [coords.timelineW, isReady]);

  const duration = wsDuration || coords.duration;

  const seekTo = useCallback(
    (time: number) => {
      const clamped = Math.max(0, Math.min(time, duration || 0));
      const ws = wsRef.current;
      if (ws && isReady && duration > 0) {
        ws.setTime(clamped);
      }
      setCurrentTime(clamped); // event-driven update, mirrored for immediacy
    },
    [duration, isReady],
  );

  const play = useCallback(() => {
    void wsRef.current?.play();
  }, []);
  const pause = useCallback(() => {
    wsRef.current?.pause();
  }, []);
  const togglePlay = useCallback(() => {
    void wsRef.current?.playPause();
  }, []);

  const beats = coords.beats;
  const barLines = coords.barLines;

  const seekToBeat = useCallback(
    (beatIndex: number) => {
      const beat = beats[Math.max(0, Math.min(beatIndex, beats.length - 1))];
      if (beat) seekTo(beat.time);
    },
    [beats, seekTo],
  );

  const stepBeat = useCallback(
    (dir: 1 | -1) => {
      const t = nextBeatTime(beats, coords.beatIndexAtTime, currentTime, dir);
      if (t != null) seekTo(t);
    },
    [beats, coords, currentTime, seekTo],
  );

  const stepBar = useCallback(
    (dir: 1 | -1) => {
      const t = nextBarTime(barLines, currentTime, dir);
      if (t != null) seekTo(t);
    },
    [barLines, currentTime, seekTo],
  );

  return useMemo(
    () => ({
      currentTime,
      isPlaying,
      duration,
      isReady,
      error,
      surface: surfaceRef.current,
      play,
      pause,
      togglePlay,
      seekTo,
      seekToBeat,
      stepBeat,
      stepBar,
    }),
    [
      currentTime,
      isPlaying,
      duration,
      isReady,
      error,
      play,
      pause,
      togglePlay,
      seekTo,
      seekToBeat,
      stepBeat,
      stepBar,
    ],
  );
}
