import FirstPageRoundedIcon from "@mui/icons-material/FirstPageRounded";
import KeyboardDoubleArrowLeftRoundedIcon from "@mui/icons-material/KeyboardDoubleArrowLeftRounded";
import PauseRoundedIcon from "@mui/icons-material/PauseRounded";
import PlayArrowRoundedIcon from "@mui/icons-material/PlayArrowRounded";
import SkipNextRoundedIcon from "@mui/icons-material/SkipNextRounded";
import SkipPreviousRoundedIcon from "@mui/icons-material/SkipPreviousRounded";

import TransportButton from "./TransportButton.jsx";

export default function TransportControls(props) {
  return (
    <div className="player-controls">
      <TransportButton label="Stop and return to start" onClick={props.onJumpStart} disabled={props.transportDisabled} icon={<FirstPageRoundedIcon fontSize="small" />} />
      <TransportButton label="Previous bar" onClick={props.onPreviousBar} disabled={props.transportDisabled} icon={<KeyboardDoubleArrowLeftRoundedIcon fontSize="small" />} />
      <TransportButton label="Previous beat" onClick={props.onPreviousBeat} disabled={props.transportDisabled} icon={<SkipPreviousRoundedIcon fontSize="small" />} />
      <TransportButton label={props.isPlaying ? "Pause" : "Play"} onClick={props.onPlayPause} disabled={props.transportDisabled} icon={props.isPlaying ? <PauseRoundedIcon fontSize="large" /> : <PlayArrowRoundedIcon fontSize="large" />} extraSx={{ width: 48, height: 48, background: "linear-gradient(135deg, #14b8a6 0%, #0f766e 100%)", color: "#041311", border: "none", '&:hover': { background: "linear-gradient(135deg, #2dd4bf 0%, #0d5f59 100%)" } }} />
      <TransportButton label="Next beat" onClick={props.onNextBeat} disabled={props.transportDisabled} icon={<SkipNextRoundedIcon fontSize="small" />} />
      <TransportButton label="Next bar" onClick={props.onNextBar} disabled={props.transportDisabled} icon={<KeyboardDoubleArrowLeftRoundedIcon fontSize="small" sx={{ transform: "scaleX(-1)" }} />} />
    </div>
  );
}