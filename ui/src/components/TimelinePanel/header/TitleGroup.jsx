import IconButton from "@mui/material/IconButton";
import Tooltip from "@mui/material/Tooltip";
import MenuIcon from "@mui/icons-material/Menu";
import MenuOpenIcon from "@mui/icons-material/MenuOpen";
import OpenInNewIcon from "@mui/icons-material/OpenInNew";

export default function TitleGroup({ loadedSong, isSidebarCollapsed, onToggleSidebar, onOpenSongMenu }) {
  return (
    <div className="timeline-title-group">
      <Tooltip title={isSidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}>
        <IconButton aria-label={isSidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"} onClick={onToggleSidebar} size="small">
          {isSidebarCollapsed ? <MenuIcon fontSize="small" /> : <MenuOpenIcon fontSize="small" />}
        </IconButton>
      </Tooltip>
      <Tooltip title="Open song list from data/songs">
        <IconButton aria-label="Open song list" onClick={onOpenSongMenu} size="small"><OpenInNewIcon fontSize="small" /></IconButton>
      </Tooltip>
      <h2>{loadedSong || "Timeline"}</h2>
    </div>
  );
}