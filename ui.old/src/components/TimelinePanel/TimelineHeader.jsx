import TitleGroup from "./header/TitleGroup.jsx";
import Toolbar from "./header/Toolbar.jsx";
import TransportControls from "./header/TransportControls.jsx";

export default function TimelineHeader({
  loadedSong,
  isSidebarCollapsed,
  onToggleSidebar,
  onOpenSongMenu,
  transportDisabled,
  onJumpStart,
  onPreviousBar,
  onPreviousBeat,
  onPlayPause,
  isPlaying,
  onNextBeat,
  onNextBar,
  barIndicator,
  beatIndicator,
  zoom,
  onZoomChange,
  visibleWindowLabel,
  selectionLabel,
}) {
  return (
    <div className="panel-header">
      <TitleGroup loadedSong={loadedSong} isSidebarCollapsed={isSidebarCollapsed} onToggleSidebar={onToggleSidebar} onOpenSongMenu={onOpenSongMenu} />
      <TransportControls transportDisabled={transportDisabled} onJumpStart={onJumpStart} onPreviousBar={onPreviousBar} onPreviousBeat={onPreviousBeat} onPlayPause={onPlayPause} isPlaying={isPlaying} onNextBeat={onNextBeat} onNextBar={onNextBar} />
      <Toolbar barIndicator={barIndicator} beatIndicator={beatIndicator} zoom={zoom} onZoomChange={onZoomChange} visibleWindowLabel={visibleWindowLabel} selectionLabel={selectionLabel} />
    </div>
  );
}