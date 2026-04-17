import { useEffect, useRef } from "preact/hooks";

import IconButton from "@mui/material/IconButton";
import Tooltip from "@mui/material/Tooltip";
import FirstPageRoundedIcon from "@mui/icons-material/FirstPageRounded";
import KeyboardDoubleArrowLeftRoundedIcon from "@mui/icons-material/KeyboardDoubleArrowLeftRounded";
import PauseRoundedIcon from "@mui/icons-material/PauseRounded";
import PlayArrowRoundedIcon from "@mui/icons-material/PlayArrowRounded";
import SkipNextRoundedIcon from "@mui/icons-material/SkipNextRounded";
import SkipPreviousRoundedIcon from "@mui/icons-material/SkipPreviousRounded";

import { DEFAULT_ZOOM, MAX_ZOOM, MIN_ZOOM, dynamicLaneIds } from "../lib/config.js";
import {
  buildScrubSelection,
  centerTimeInView,
  findSelectionAtTrackPosition,
  getVisibleRange,
  renderTrackLane,
  renderTimelineMarkup,
  updateNowMarkers,
} from "../lib/timeline.js";
import { clamp, formatRange } from "../lib/utils.js";

export default function TimelinePanel({
  loadedSong,
  timeline,
  zoom,
  onZoomChange,
  selection,
  currentTime,
  isPlaying,
  followPlayhead,
  onSeek,
  onPlayPause,
  onJumpStart,
  onPreviousBar,
  onPreviousBeat,
  onNextBeat,
  onNextBar,
  onOpenSelectionOverlay,
  onCloseSelectionOverlay,
  onVisibleWindowChange,
  laneVisibility,
  waveformPeaks,
}) {
  const scrollerRef = useRef(null);
  const rowsRef = useRef(null);
  const viewportFrameRef = useRef(null);
  const dragStateRef = useRef({
    active: false,
    startClientX: 0,
    startScrollLeft: 0,
    moved: false,
  });
  const suppressClickRef = useRef(false);

  useEffect(() => {
    const rowsElement = rowsRef.current;
    const scrollerElement = scrollerRef.current;
    if (!rowsElement) {
      return undefined;
    }
    if (!timeline) {
      rowsElement.className = "timeline-rows empty";
      rowsElement.textContent = "Load a song to inspect the synchronized timeline lanes.";
      onVisibleWindowChange("Visible 0:00.0-0:00.0", "-");
      return undefined;
    }

    rowsElement.className = "timeline-rows";
    rowsElement.innerHTML = renderTimelineMarkup(timeline, laneVisibility, zoom);
    const visibleRange = getVisibleRange(scrollerElement, zoom, timeline.duration);
    for (const laneId of Object.keys(laneVisibility)) {
      if (laneVisibility[laneId]) {
        const track = rowsElement.querySelector(`[data-track-lane="${laneId}"]`);
        renderTrackLane(track, laneId, timeline, zoom, visibleRange, waveformPeaks);
      }
    }
    updateNowMarkers(rowsElement, timeline, zoom, currentTime);
    onVisibleWindowChange(`Visible ${formatRange(visibleRange.start, visibleRange.end)}`, formatRange(visibleRange.start, visibleRange.end));
    return undefined;
  }, [timeline, laneVisibility, zoom, waveformPeaks, onVisibleWindowChange]);

  useEffect(() => {
    if (!rowsRef.current || !timeline) {
      return;
    }
    updateNowMarkers(rowsRef.current, timeline, zoom, currentTime);
  }, [timeline, zoom, currentTime]);

  useEffect(() => {
    if (!timeline || !followPlayhead) {
      return;
    }
    centerTimeInView(scrollerRef.current, timeline, zoom, currentTime);
  }, [timeline, followPlayhead, zoom, currentTime]);

  useEffect(() => () => {
    if (viewportFrameRef.current) {
      cancelAnimationFrame(viewportFrameRef.current);
    }
  }, []);

  useEffect(() => {
    function handleWindowMouseMove(event) {
      const scrollerElement = scrollerRef.current;
      const dragState = dragStateRef.current;
      if (!dragState.active || !scrollerElement) {
        return;
      }

      const deltaX = event.clientX - dragState.startClientX;
      if (Math.abs(deltaX) > 3) {
        dragState.moved = true;
      }

      if (!dragState.moved) {
        return;
      }

      scrollerElement.scrollLeft = dragState.startScrollLeft - deltaX;
      event.preventDefault();
    }

    function stopDragging() {
      const dragState = dragStateRef.current;
      if (!dragState.active) {
        return;
      }

      if (dragState.moved) {
        suppressClickRef.current = true;
      }

      dragState.active = false;
      dragState.startClientX = 0;
      dragState.startScrollLeft = 0;
      dragState.moved = false;
      scrollerRef.current?.classList.remove("is-dragging");
    }

    window.addEventListener("mousemove", handleWindowMouseMove);
    window.addEventListener("mouseup", stopDragging);

    return () => {
      window.removeEventListener("mousemove", handleWindowMouseMove);
      window.removeEventListener("mouseup", stopDragging);
    };
  }, []);

  function handleTimelineMouseDown(event) {
    if (event.button !== 0 || !timeline || !scrollerRef.current) {
      return;
    }

    dragStateRef.current.active = true;
    dragStateRef.current.startClientX = event.clientX;
    dragStateRef.current.startScrollLeft = scrollerRef.current.scrollLeft;
    dragStateRef.current.moved = false;
    scrollerRef.current.classList.add("is-dragging");
  }

  function handleTimelineClick(event) {
    if (suppressClickRef.current) {
      suppressClickRef.current = false;
      return;
    }

    if (!timeline) {
      return;
    }
    const track = event.target.closest("[data-track-lane], .ruler-track");
    if (!track) {
      return;
    }
    const rectangle = track.getBoundingClientRect();
    const absoluteX = event.clientX - rectangle.left;
    const offsetY = event.clientY - rectangle.top;
    const regionSelection = findSelectionAtTrackPosition(track, absoluteX, offsetY);
    if (regionSelection) {
      onSeek(regionSelection.start_s, regionSelection);
      onOpenSelectionOverlay?.(regionSelection, {
        x: event.clientX,
        y: event.clientY,
      });
      return;
    }
    const time = absoluteX / zoom;
    onSeek(time, buildScrubSelection(track.dataset.trackLane, time));
    onCloseSelectionOverlay?.();
  }

  function handleScroll() {
    if (!timeline || !rowsRef.current) {
      return;
    }
    if (viewportFrameRef.current) {
      cancelAnimationFrame(viewportFrameRef.current);
    }
    viewportFrameRef.current = requestAnimationFrame(() => {
      const visibleRange = getVisibleRange(scrollerRef.current, zoom, timeline.duration);
      for (const laneId of ["waveform", "drums", "density", "energy", "validation"]) {
        if (laneVisibility[laneId]) {
          const track = rowsRef.current.querySelector(`[data-track-lane="${laneId}"]`);
          renderTrackLane(track, laneId, timeline, zoom, visibleRange, waveformPeaks);
        }
      }
      onVisibleWindowChange(`Visible ${formatRange(visibleRange.start, visibleRange.end)}`, formatRange(visibleRange.start, visibleRange.end));
    });
  }

  const transportDisabled = !timeline;

  function renderTransportButton(label, onClick, icon, extraSx = {}) {
    return (
      <Tooltip title={label}>
        <span>
          <IconButton
            aria-label={label}
            onClick={onClick}
            disabled={transportDisabled}
            size="small"
            sx={{
              width: 40,
              height: 40,
              border: "1px solid rgba(77, 53, 29, 0.14)",
              background: "rgba(255, 254, 250, 0.92)",
              color: "#23160e",
              borderRadius: "12px",
              '&:hover': {
                background: "rgba(255, 248, 240, 0.98)",
              },
              '&.Mui-disabled': {
                color: "rgba(112, 89, 71, 0.45)",
                borderColor: "rgba(77, 53, 29, 0.08)",
              },
              ...extraSx,
            }}
          >
            {icon}
          </IconButton>
        </span>
      </Tooltip>
    );
  }

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <h2>{loadedSong || "Timeline"}</h2>
        </div>
        <div className="player-controls">
          {renderTransportButton("Stop and return to start", onJumpStart, <FirstPageRoundedIcon fontSize="small" />)}
          {renderTransportButton("Previous bar", onPreviousBar, <KeyboardDoubleArrowLeftRoundedIcon fontSize="small" />)}
          {renderTransportButton("Previous beat", onPreviousBeat, <SkipPreviousRoundedIcon fontSize="small" />)}
          {renderTransportButton(
            isPlaying ? "Pause" : "Play",
            onPlayPause,
            isPlaying ? <PauseRoundedIcon fontSize="small" /> : <PlayArrowRoundedIcon fontSize="small" />,
            {
              width: 48,
              height: 48,
              background: "linear-gradient(135deg, #0f766e 0%, #155e75 100%)",
              color: "#f7fffd",
              border: "none",
              '&:hover': {
                background: "linear-gradient(135deg, #0d6b64 0%, #134f61 100%)",
              },
            },
          )}
          {renderTransportButton("Next beat", onNextBeat, <SkipNextRoundedIcon fontSize="small" />)}
          {renderTransportButton("Next bar", onNextBar, <KeyboardDoubleArrowLeftRoundedIcon fontSize="small" sx={{ transform: "scaleX(-1)" }} />)}
        </div>
        <div className="timeline-toolbar">
          <label className="range-control" htmlFor="zoom-control">
            <span>Zoom</span>
            <input id="zoom-control" type="range" min={MIN_ZOOM} max={MAX_ZOOM} step="2" value={zoom} onInput={(event) => onZoomChange(clamp(Number(event.currentTarget.value) || DEFAULT_ZOOM, MIN_ZOOM, MAX_ZOOM))} />
            <strong>{zoom} px/s</strong>
          </label>
          <div className="timeline-toolbar-readouts">
            <span>{timeline ? selection.visibleWindowLabel || `Visible ${formatRange(0, 0)}` : "Visible 0:00.0-0:00.0"}</span>
            <span>{selection.region ? `${selection.region.laneLabel}: ${selection.region.label} ${formatRange(selection.region.start_s, selection.region.end_s)}` : "No region selected."}</span>
          </div>
        </div>
      </div>
      <div className="timeline-scroller" ref={scrollerRef} onMouseDown={handleTimelineMouseDown} onScroll={handleScroll}>
        <div className="timeline-rows empty" ref={rowsRef} onClick={handleTimelineClick}>Load a song to inspect the synchronized timeline lanes.</div>
      </div>
    </section>
  );
}