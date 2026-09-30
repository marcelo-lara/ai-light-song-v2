// useTimelineViewport.ts — playback, zoom, scroll and follow-playhead state
// for the timeline. Split out of App.tsx (v3.9 item 7), kept as ONE hook
// rather than several: `scrollerRef`, `autoScrollRef`, `zoomAnchorRef`,
// `followPlayheadRef`/`playingRef`/`currentTimeRef` are read and written
// across the scroll-tracking effect, the follow-playhead effect, the
// zoom-anchor-restore effect and `captureZoomAnchor` — splitting further
// would either duplicate those refs (breaking the single source of truth
// each effect depends on) or force awkward cross-hook ref-passing with no
// behaviour benefit. See App.tsx's own header note.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { artifactPaths } from "../data";
import type { BeatLike, Coords } from "../timeline/coords";
import { makeCoords } from "../timeline/coords";
import {
  followScrollLeft,
  isUserScroll,
  LABEL_WIDTH,
  loadFollowPlayhead,
  saveFollowPlayhead,
} from "../timeline/follow";
import { useTransport, type Transport } from "../timeline/useTransport";
import {
  clampPxPerBar,
  fitToWidthPxPerBar,
  PX_PER_BAR_MIN,
  zoomInPxPerBar,
  zoomOutPxPerBar,
} from "../timeline/zoom";
import { seekTimeForCardClick } from "./transportRules";

export interface TimelineViewportInputs {
  song: string | null;
  /** re-registers the scroll-tracking effect on a view change too, matching
   *  App.tsx's original `[song, activeView]` effect dependency. */
  activeView: string;
  beats: readonly BeatLike[];
  estimatedDuration: number;
}

export interface TimelineViewport {
  coords: Coords;
  transport: Transport;
  duration: number;
  pxPerBar: number;
  setPxPerBar: React.Dispatch<React.SetStateAction<number>>;
  minZoomPxPerBar: number;
  clampZoomForViewport: (value: number) => number;
  scrollLeft: number;
  viewportWidth: number;
  followPlayhead: boolean;
  setFollowPlayhead: React.Dispatch<React.SetStateAction<boolean>>;
  scrollerRef: React.RefObject<HTMLDivElement>;
  scrollTimelineToTime: (seconds: number) => void;
  isTimeVisible: (seconds: number) => boolean;
  seekToTime: (time: number) => void;
  seekToTimeAlways: (time: number) => void;
  captureZoomAnchor: () => void;
  fitToWidth: () => void;
  zoomIn: () => void;
  zoomOut: () => void;
}

export function useTimelineViewport({
  song,
  activeView,
  beats,
  estimatedDuration,
}: TimelineViewportInputs): TimelineViewport {
  const [pxPerBar, setPxPerBar] = useState(62);
  const [scrollLeft, setScrollLeft] = useState(0);
  const [viewportWidth, setViewportWidth] = useState(0);
  // plan v1.5 item 6 / R6: follow the playhead while playing. Persisted per
  // session, default on (D7). A user scroll during playback flips it off.
  const [followPlayhead, setFollowPlayhead] = useState(loadFollowPlayhead);

  const scrollerRef = useRef<HTMLDivElement>(null);
  // plan v1.5 D6: the offset the follow effect last wrote, so the scroll
  // listener can tell a user scroll from the effect's own. null until the
  // effect writes.
  const autoScrollRef = useRef<number | null>(null);

  const coords = useMemo(
    () => makeCoords({ beats, duration: estimatedDuration, pxPerBar }),
    [beats, estimatedDuration, pxPerBar],
  );

  const audioUrl = song ? artifactPaths.audio(song) : null;
  const transport = useTransport({ audioUrl, coords });
  const duration = transport.duration || estimatedDuration;
  const minZoomPxPerBar = useMemo(() => {
    if (!duration || viewportWidth <= 0) return PX_PER_BAR_MIN;
    return fitToWidthPxPerBar(viewportWidth, duration, coords.medianBarSeconds);
  }, [duration, viewportWidth, coords.medianBarSeconds]);
  const clampZoomForViewport = useCallback(
    (value: number): number => Math.max(minZoomPxPerBar, clampPxPerBar(value)),
    [minZoomPxPerBar],
  );

  // Persist the follow-playhead flag (plan v1.5 item 6 / D7).
  useEffect(() => {
    saveFollowPlayhead(followPlayhead);
  }, [followPlayhead]);

  const scrollTimelineToTime = useCallback(
    (seconds: number) => {
      const el = scrollerRef.current;
      if (!el) return;
      const target = LABEL_WIDTH + coords.timeToX(seconds) - el.clientWidth * 0.3;
      const max = el.scrollWidth - el.clientWidth;
      el.scrollLeft = Math.max(0, Math.min(target, max));
    },
    [coords],
  );

  // whether `seconds`' playhead x-position currently sits inside the
  // scroller's visible window (label column excluded).
  const isTimeVisible = useCallback(
    (seconds: number) => {
      const el = scrollerRef.current;
      if (!el) return true;
      const x = LABEL_WIDTH + coords.timeToX(seconds);
      return x >= el.scrollLeft + LABEL_WIDTH && x <= el.scrollLeft + el.clientWidth;
    },
    [coords],
  );

  // R3/D1 + D2: a card click seeks (only when paused) and scrolls the
  // playhead into view when it's off-screen. Shared by every "click a card,
  // move the playhead" surface — the lane-events panel (`handleSelectBlock`).
  const seekToTime = useCallback(
    (time: number) => {
      const seekTo = seekTimeForCardClick(transport.isPlaying, time);
      if (seekTo !== null) {
        transport.seekTo(seekTo);
        if (!isTimeVisible(seekTo)) scrollTimelineToTime(seekTo);
      }
    },
    [transport, isTimeVisible, scrollTimelineToTime],
  );

  // Pending Proposals panel's own card-click seek: unlike `seekToTime`, this
  // deliberately overrides the R3 paused-only rule, since a proposal card's
  // window is a correction to review against the live show, not a "jump
  // back and replay" navigation — the operator needs to move the playhead
  // there even mid-playback.
  const seekToTimeAlways = useCallback(
    (time: number) => {
      transport.seekTo(time);
      if (!isTimeVisible(time)) scrollTimelineToTime(time);
    },
    [transport, isTimeVisible, scrollTimelineToTime],
  );

  // Latest values for the scroll listener below, read through refs so the
  // listener need not re-register on every playback tick (plan v1.5 item 6).
  const followPlayheadRef = useRef(followPlayhead);
  followPlayheadRef.current = followPlayhead;
  const playingRef = useRef(transport.isPlaying);
  playingRef.current = transport.isPlaying;
  const currentTimeRef = useRef(transport.currentTime);
  currentTimeRef.current = transport.currentTime;

  // Zoom anchoring: record the playhead's on-screen pixel position right
  // before a zoom change, so the effect below can restore that same screen
  // position under the new px/bar instead of leaving the scroll wherever it
  // lands. Captured in the click/change handlers (pre-update coords), read
  // and cleared by the effect once pxPerBar has actually changed.
  const zoomAnchorRef = useRef<{ time: number; screenX: number } | null>(null);
  const captureZoomAnchor = useCallback(() => {
    const el = scrollerRef.current;
    if (!el) return;
    const t = currentTimeRef.current;
    const x = LABEL_WIDTH + coords.timeToX(t);
    zoomAnchorRef.current = { time: t, screenX: x - el.scrollLeft };
  }, [coords]);

  const zoomIn = useCallback(() => {
    captureZoomAnchor();
    setPxPerBar((v) => zoomInPxPerBar(v));
  }, [captureZoomAnchor]);

  const zoomOut = useCallback(() => {
    captureZoomAnchor();
    setPxPerBar((v) => clampZoomForViewport(zoomOutPxPerBar(v)));
  }, [captureZoomAnchor, clampZoomForViewport]);

  // Track the timeline scroll offset + viewport width for the canvas lanes
  // (sub-labels are anchored to the viewport's left edge). rAF-coalesced.
  useEffect(() => {
    const el = scrollerRef.current;
    if (!el) return;
    let raf = 0;
    const sync = () => {
      raf = 0;
      setScrollLeft(el.scrollLeft);
      setViewportWidth(el.clientWidth);
    };
    const onScroll = () => {
      // plan v1.5 item 6 / D6: a user scroll during playback turns following
      // off. `isUserScroll` distinguishes it from the follow effect's own write.
      if (
        playingRef.current &&
        followPlayheadRef.current &&
        isUserScroll(el.scrollLeft, autoScrollRef.current)
      ) {
        setFollowPlayhead(false);
      }
      if (!raf) raf = requestAnimationFrame(sync);
    };
    sync();
    el.addEventListener("scroll", onScroll, { passive: true });
    const observer = new ResizeObserver(sync);
    observer.observe(el);
    return () => {
      el.removeEventListener("scroll", onScroll);
      observer.disconnect();
      if (raf) cancelAnimationFrame(raf);
    };
  }, [song, activeView]);

  // Follow-playhead scroll while playing (design notes §2; plan v1.5 item 6).
  useEffect(() => {
    const el = scrollerRef.current;
    if (!el) return;
    if (!(followPlayhead && transport.isPlaying)) return;
    const next = followScrollLeft({
      playheadX: LABEL_WIDTH + coords.timeToX(transport.currentTime),
      scrollLeft: el.scrollLeft,
      viewportWidth: el.clientWidth,
      maxScrollLeft: el.scrollWidth - el.clientWidth,
      playing: transport.isPlaying,
    });
    if (Math.abs(next - el.scrollLeft) > 0.5) {
      autoScrollRef.current = next;
      el.scrollLeft = next;
    }
  }, [transport.currentTime, transport.isPlaying, followPlayhead, coords]);

  // Zooming changes each bar's pixel width, which otherwise scrolls the
  // playhead out from under the viewport with no way back short of a manual
  // scroll. While paused (the follow effect above already covers playback):
  // if a zoom control captured an anchor, pin the playhead to the same
  // screen pixel it occupied before the zoom; otherwise (e.g. fit-to-width)
  // just make sure it's still visible.
  useEffect(() => {
    const el = scrollerRef.current;
    if (!el) return;
    if (playingRef.current) {
      zoomAnchorRef.current = null;
      return;
    }
    const anchor = zoomAnchorRef.current;
    zoomAnchorRef.current = null;
    if (anchor) {
      const playheadX = LABEL_WIDTH + coords.timeToX(anchor.time);
      const max = el.scrollWidth - el.clientWidth;
      el.scrollLeft = Math.max(0, Math.min(playheadX - anchor.screenX, max));
      return;
    }
    if (!isTimeVisible(currentTimeRef.current)) {
      scrollTimelineToTime(currentTimeRef.current);
    }
  }, [pxPerBar, coords, isTimeVisible, scrollTimelineToTime]);

  const fitToWidth = useCallback(() => {
    const el = scrollerRef.current;
    if (!el || !duration) return;
    setPxPerBar(fitToWidthPxPerBar(el.clientWidth, duration, coords.medianBarSeconds));
  }, [duration, coords.medianBarSeconds]);

  // Zoom floor is dynamic: never below full-song fit in the current viewport
  // (with the global 3 px/bar absolute floor from `clampPxPerBar`).
  useEffect(() => {
    setPxPerBar((v) => (v < minZoomPxPerBar ? minZoomPxPerBar : v));
  }, [minZoomPxPerBar]);

  return {
    coords,
    transport,
    duration,
    pxPerBar,
    setPxPerBar,
    minZoomPxPerBar,
    clampZoomForViewport,
    scrollLeft,
    viewportWidth,
    followPlayhead,
    setFollowPlayhead,
    scrollerRef,
    scrollTimelineToTime,
    isTimeVisible,
    seekToTime,
    seekToTimeAlways,
    captureZoomAnchor,
    fitToWidth,
    zoomIn,
    zoomOut,
  };
}
