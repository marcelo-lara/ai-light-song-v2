import { createOverviewProps } from "./createOverviewProps.js";
import { createSidebarProps } from "./createSidebarProps.js";
import { createTimelineProps } from "./createTimelineProps.js";

export function createAppViewProps(context) {
  return {
    shellClassName: `shell${context.shellState.isSidebarCollapsed ? " sidebar-collapsed" : ""}`,
    sidebarProps: createSidebarProps(context),
    timelineProps: createTimelineProps(context),
    detailProps: {
      artifactRecords: context.artifactRecords,
      selectedArtifactKey: context.shellState.selectedArtifactKey,
      onSelectArtifact: context.shellState.handleSelectArtifact,
      selection: context.shellState.selectedRegion,
    },
    overviewProps: createOverviewProps(context),
    overlaySelection: context.shellState.overlaySelection,
    overlayAnchor: context.shellState.overlayAnchor,
    onCloseOverlay: context.shellState.handleCloseSelectionOverlay,
  };
}