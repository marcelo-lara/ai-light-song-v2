import DetailPanels from "../components/DetailPanels/index.jsx";
import OverlayPanel from "../components/OverlayPanel/index.jsx";
import OverviewPanels from "../components/OverviewPanels/index.jsx";
import SelectionDetailCard from "../components/SelectionDetailCard/index.jsx";
import Sidebar from "../components/Sidebar/index.jsx";
import TimelinePanel from "../components/TimelinePanel/index.jsx";
import { formatRange } from "../lib/utils.js";

export default function AppView(props) {
  const { shellClassName, sidebarProps, timelineProps, detailProps, overviewProps, overlaySelection, overlayAnchor, onCloseOverlay } = props;

  return (
    <>
      <div className={shellClassName}>
        <Sidebar {...sidebarProps} />
        <div>
          <main className="main">
            <TimelinePanel {...timelineProps} />
            <DetailPanels {...detailProps} />
            <OverviewPanels {...overviewProps} />
          </main>
        </div>
      </div>

      <OverlayPanel
        isOpen={Boolean(overlaySelection)}
        title={overlaySelection?.label || "Selection Detail"}
        subtitle={overlaySelection ? `${overlaySelection.laneLabel} · ${formatRange(overlaySelection.start_s, overlaySelection.end_s)}` : ""}
        anchorPosition={overlayAnchor}
        onClose={onCloseOverlay}
      >
        <SelectionDetailCard selection={overlaySelection} emptyMessage="Click a lane item to inspect it here." />
      </OverlayPanel>
    </>
  );
}