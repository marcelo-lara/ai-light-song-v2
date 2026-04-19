import IconButton from "@mui/material/IconButton";
import Tooltip from "@mui/material/Tooltip";

export default function TransportButton({ label, onClick, icon, disabled, extraSx = {} }) {
  return (
    <Tooltip title={label}>
      <span>
        <IconButton
          aria-label={label}
          onClick={onClick}
          disabled={disabled}
          size="small"
          sx={{
            width: 40,
            height: 40,
            border: "1px solid rgba(141, 167, 191, 0.18)",
            background: "rgba(17, 28, 38, 0.92)",
            color: "#e5edf5",
            borderRadius: "4px",
            '&:hover': { background: "rgba(25, 38, 50, 0.98)" },
            '&.Mui-disabled': { color: "rgba(146, 165, 181, 0.4)", borderColor: "rgba(141, 167, 191, 0.08)" },
            ...extraSx,
          }}
        >
          {icon}
        </IconButton>
      </span>
    </Tooltip>
  );
}