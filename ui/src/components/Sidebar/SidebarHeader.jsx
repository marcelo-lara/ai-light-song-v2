import IconButton from "@mui/material/IconButton";
import Tooltip from "@mui/material/Tooltip";
import MenuOpenIcon from "@mui/icons-material/MenuOpen";

export default function SidebarHeader({ onToggleCollapse }) {
  return (
    <div className="sidebar-title-row">
      <div>
        <p className="eyebrow">AI Light Song v2</p>
        <h1>Artifact Debugger</h1>
        <p className="lede">Read-only inspection for generated inference surfaces, timing alignment, and regression drift under <code>data/artifacts</code>.</p>
      </div>
      <Tooltip title="Collapse sidebar">
        <IconButton aria-label="Collapse sidebar" onClick={onToggleCollapse} size="small">
          <MenuOpenIcon fontSize="small" />
        </IconButton>
      </Tooltip>
    </div>
  );
}