import { useState } from "preact/hooks";

import { DEFAULT_ZOOM } from "../lib/config.js";
import { createInitialLaneCollapsed, createInitialLaneVisibility } from "./laneState.js";

export function useShellState() {
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(true);
  const [selectedArtifactKey, setSelectedArtifactKey] = useState("");
  const [selectedRegion, setSelectedRegion] = useState(null);
  const [overlaySelection, setOverlaySelection] = useState(null);
  const [overlayAnchor, setOverlayAnchor] = useState(null);
  const [laneVisibility, setLaneVisibility] = useState(createInitialLaneVisibility);
  const [laneCollapsed, setLaneCollapsed] = useState(createInitialLaneCollapsed);
  const [zoom, setZoom] = useState(DEFAULT_ZOOM);
  const [followPlayhead, setFollowPlayhead] = useState(true);
  const [visibleWindowText, setVisibleWindowText] = useState("Visible 0:00.0-0:00.0");
  const [metaViewportText, setMetaViewportText] = useState("-");

  return {
    isSidebarCollapsed,
    selectedArtifactKey,
    selectedRegion,
    overlaySelection,
    overlayAnchor,
    laneVisibility,
    laneCollapsed,
    zoom,
    followPlayhead,
    visibleWindowText,
    metaViewportText,
    setZoom,
    setSelectedRegion,
    handleBeforeLoadSong() {
      setSelectedRegion(null);
      setOverlaySelection(null);
      setOverlayAnchor(null);
      setSelectedArtifactKey("");
    },
    handleSelectArtifact(event) { setSelectedArtifactKey(event.currentTarget.value); },
    handleLaneToggle(laneId, checked) { setLaneVisibility((current) => ({ ...current, [laneId]: checked })); },
    handleLaneCollapsedToggle(laneId) { setLaneCollapsed((current) => ({ ...current, [laneId]: !current[laneId] })); },
    handleFollowPlayheadChange(event) { setFollowPlayhead(event.currentTarget.checked); },
    handleVisibleWindowChange(nextVisibleWindowText, nextMetaViewportText) {
      setVisibleWindowText(nextVisibleWindowText);
      setMetaViewportText(nextMetaViewportText);
    },
    handleOpenSelectionOverlay(selection, anchorPosition) {
      setOverlaySelection(selection);
      setOverlayAnchor(anchorPosition || null);
    },
    handleCloseSelectionOverlay() {
      setOverlaySelection(null);
      setOverlayAnchor(null);
    },
    handleToggleSidebar() { setIsSidebarCollapsed((current) => !current); },
  };
}