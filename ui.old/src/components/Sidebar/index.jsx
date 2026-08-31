import FileStatusPanel from "./FileStatusPanel.jsx";
import LaneTogglesPanel from "./LaneTogglesPanel.jsx";
import PathsPanel from "./PathsPanel.jsx";
import PlaybackPanel from "./PlaybackPanel.jsx";
import SidebarHeader from "./SidebarHeader.jsx";
import SongControlsPanel from "./SongControlsPanel.jsx";

export default function Sidebar(props) {
  return (
    <aside className="sidebar">
      <SidebarHeader onToggleCollapse={props.onToggleCollapse} />
      <SongControlsPanel {...props} />
      <PlaybackPanel {...props} />
      <LaneTogglesPanel timelineLoaded={props.timelineLoaded} laneVisibility={props.laneVisibility} onLaneToggle={props.onLaneToggle} />
      <PathsPanel />
      <FileStatusPanel fileStatuses={props.fileStatuses} />
    </aside>
  );
}