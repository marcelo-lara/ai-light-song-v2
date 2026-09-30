// AppHeader.tsx — transport controls, clock, song title and BPM/key tags.
// Split out of App.tsx (v3.9 item 7) with no behaviour change.

import type { BarBeat } from "../timeline/coords";
import type { SongInfo } from "../data/types";
import { RunAnalysisControl } from "../RunAnalysisControl";
import { formatClock, formatSecondsFixed } from "./format";

export function AppHeader({
  drawerOpen,
  onToggleDrawer,
  onSeekToStart,
  onStepBar,
  onStepBeat,
  isPlaying,
  onTogglePlay,
  currentTime,
  barBeat,
  song,
  info,
  keyLabel,
}: {
  drawerOpen: boolean;
  onToggleDrawer: () => void;
  onSeekToStart: () => void;
  onStepBar: (dir: 1 | -1) => void;
  onStepBeat: (dir: 1 | -1) => void;
  isPlaying: boolean;
  onTogglePlay: () => void;
  currentTime: number;
  barBeat: BarBeat;
  song: string | null;
  info: SongInfo | null | undefined;
  keyLabel: string;
}): React.JSX.Element {
  return (
    <header className="app-header">
      <div className="app-header__left">
        <button
          type="button"
          className="tp"
          style={{ fontSize: 18 }}
          data-testid="burger-toggle"
          aria-label="Toggle menu"
          aria-pressed={drawerOpen}
          onClick={onToggleDrawer}
        >
          <i className="ph ph-list" />
        </button>
        <div className="app-header__divider" />
        <div className="app-header__transport">
          <button type="button" className="tp" aria-label="To start" onClick={onSeekToStart}>
            <i className="ph ph-skip-back" />
          </button>
          <button type="button" className="tp" aria-label="Previous bar" onClick={() => onStepBar(-1)}>
            <i className="ph ph-rewind" />
          </button>
          <button type="button" className="tp" aria-label="Previous beat" onClick={() => onStepBeat(-1)}>
            <i className="ph ph-caret-left" />
          </button>
          <button
            type="button"
            className="tp tp-main"
            aria-label={isPlaying ? "Pause" : "Play"}
            onClick={onTogglePlay}
          >
            <i className={`ph ${isPlaying ? "ph-pause" : "ph-play"}`} />
          </button>
          <button type="button" className="tp" aria-label="Next beat" onClick={() => onStepBeat(1)}>
            <i className="ph ph-caret-right" />
          </button>
          <button type="button" className="tp" aria-label="Next bar" onClick={() => onStepBar(1)}>
            <i className="ph ph-fast-forward" />
          </button>
        </div>
      </div>

      <div className="app-header__center">
        <div>
          <span className="app-header__time">{formatClock(currentTime)}</span>
          <span className="app-header__time-sep"> / </span>
          <span className="app-header__time_s">{formatSecondsFixed(currentTime)}</span>
        </div>
        <div className="app-header__divider" />
        <span className="app-header__barbeat">
          {barBeat.bar}.{barBeat.beat}
        </span>
      </div>

      <div className="app-header__right">
        {song && <RunAnalysisControl song={song} />}
        <div className="app-header__song">
          <div className="app-header__song-title">{info?.song_name ?? "No song selected"}</div>
          <div className="app-header__song-sub">
            {info ? "Score Analysis DAW" : "Select a song from the drawer"}
          </div>
        </div>
        <div className="app-header__tags">
          <span className="tag tag-accent" style={{ justifyContent: "center" }}>
            {info?.bpm ? `${Math.round(info.bpm)} BPM` : "— BPM"}
          </span>
          <span className="tag tag-outline" style={{ justifyContent: "center" }}>
            {keyLabel}
          </span>
        </div>
      </div>
    </header>
  );
}
