import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { discoverSongs, useSong } from "./data";
import type { SectionRow } from "./data/types";
import { makeCoords } from "./timeline/coords";
import { followScrollLeft, LABEL_WIDTH } from "./timeline/follow";
import { LaneList } from "./timeline/LaneList";
import { useLaneState } from "./timeline/laneState";
import type { SegmentBlock } from "./timeline/segments";
import { TimelineGrid } from "./timeline/TimelineGrid";
import {
  clampPxPerBar,
  fitToWidthPxPerBar,
  ppbLabel,
  PX_PER_BAR_MAX,
  PX_PER_BAR_MIN,
  zoomInPxPerBar,
  zoomOutPxPerBar,
} from "./timeline/zoom";

type DrawerView = "song" | "timeline" | "inspector" | "review";

interface DrawerEntry {
  id: DrawerView;
  label: string;
  icon: string;
}

const DRAWER_ENTRIES: readonly DrawerEntry[] = [
  { id: "song", label: "Select Song", icon: "ph-file-audio" },
  { id: "timeline", label: "Timeline", icon: "ph-waveform" },
  { id: "inspector", label: "Artifact inspector", icon: "ph-squares-four" },
  { id: "review", label: "Review queue", icon: "ph-flag" },
] as const;

const TIMELINE_KEYS = ["info", "beats", "sectionsTopLevel", "harmonicLayer"] as const;

/**
 * Placeholder transport. Item 4 replaces this with `src/timeline/useTransport.ts`
 * bound to wavesurfer events — the seam is this hook's return shape
 * (`currentTime`, `playing`, `seek`, `togglePlay`, `duration`). No rAF loop
 * survives into item 4; wavesurfer's `audioprocess` drives `currentTime` there.
 */
function usePlaceholderTransport(duration: number) {
  const [currentTime, setCurrentTime] = useState(0);
  const [playing, setPlaying] = useState(false);
  const raf = useRef<number | null>(null);
  const last = useRef<number>(0);

  useEffect(() => {
    if (!playing) return;
    last.current = performance.now();
    const step = (now: number) => {
      const dt = (now - last.current) / 1000;
      last.current = now;
      setCurrentTime((t) => {
        const next = t + dt;
        if (next >= duration) {
          setPlaying(false);
          return duration;
        }
        return next;
      });
      raf.current = requestAnimationFrame(step);
    };
    raf.current = requestAnimationFrame(step);
    return () => {
      if (raf.current != null) cancelAnimationFrame(raf.current);
    };
  }, [playing, duration]);

  const seek = useCallback(
    (time: number) => setCurrentTime(Math.max(0, Math.min(time, duration || 0))),
    [duration],
  );
  const togglePlay = useCallback(() => setPlaying((p) => !p), []);

  return { currentTime, playing, seek, togglePlay, setPlaying, duration };
}

function formatClock(seconds: number): string {
  const safe = Math.max(0, seconds || 0);
  const m = Math.floor(safe / 60);
  const s = safe - m * 60;
  return `${m}:${s < 10 ? "0" : ""}${s.toFixed(1)}`;
}

export function App(): React.JSX.Element {
  const [drawerOpen, setDrawerOpen] = useState(true);
  const [activeView, setActiveView] = useState<DrawerView>("timeline");
  const [song, setSong] = useState<string | null>(null);
  const [songs, setSongs] = useState<string[]>([]);
  const [discoveryError, setDiscoveryError] = useState<string | null>(null);
  const [pxPerBar, setPxPerBar] = useState(62);
  const [laneListOpen, setLaneListOpen] = useState(false);

  const scrollerRef = useRef<HTMLDivElement>(null);
  const laneState = useLaneState();

  useEffect(() => {
    let cancelled = false;
    discoverSongs()
      .then((result) => {
        if (cancelled) return;
        setSongs(result.songs);
        setDiscoveryError(null);
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        setDiscoveryError(error instanceof Error ? error.message : "Discovery failed.");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const { artifacts } = useSong(song, TIMELINE_KEYS);
  const info = artifacts.info.data;
  const beats = useMemo(() => artifacts.beats.data ?? [], [artifacts.beats.data]);
  const sections: SectionRow[] = useMemo(
    () => artifacts.sectionsTopLevel.data ?? [],
    [artifacts.sectionsTopLevel.data],
  );
  const duration = info?.duration ?? beats.at(-1)?.time ?? 0;

  const transport = usePlaceholderTransport(duration);

  const coords = useMemo(
    () => makeCoords({ beats, duration, pxPerBar }),
    [beats, duration, pxPerBar],
  );

  // Follow-playhead scroll while playing (design notes §2).
  useEffect(() => {
    const el = scrollerRef.current;
    if (!el) return;
    const next = followScrollLeft({
      playheadX: LABEL_WIDTH + coords.timeToX(transport.currentTime),
      scrollLeft: el.scrollLeft,
      viewportWidth: el.clientWidth,
      maxScrollLeft: el.scrollWidth - el.clientWidth,
      playing: transport.playing,
    });
    if (Math.abs(next - el.scrollLeft) > 0.5) el.scrollLeft = next;
  }, [transport.currentTime, transport.playing, coords]);

  const fitToWidth = useCallback(() => {
    const el = scrollerRef.current;
    if (!el || !duration) return;
    setPxPerBar(fitToWidthPxPerBar(el.clientWidth, duration, coords.medianBarSeconds));
  }, [duration, coords.medianBarSeconds]);

  const stepBeat = useCallback(
    (dir: 1 | -1) => {
      if (beats.length === 0) return;
      const i = coords.beatIndexAtTime(transport.currentTime);
      const target = beats[Math.max(0, Math.min(i + dir, beats.length - 1))];
      if (target) transport.seek(target.time);
    },
    [beats, coords, transport],
  );

  const stepBar = useCallback(
    (dir: 1 | -1) => {
      const lines = coords.barLines;
      if (lines.length === 0) return;
      const t = transport.currentTime;
      const next =
        dir === 1
          ? lines.find((l) => l.time > t + 0.001)
          : [...lines].reverse().find((l) => l.time < t - 0.001);
      if (next) transport.seek(next.time);
    },
    [coords, transport],
  );

  const handleSelectSegment = useCallback(
    (block: SegmentBlock) => {
      // Move the shared playhead to the block start (design notes §4).
      transport.seek(block.section.start);
      // TODO(item 6): open the right-panel block inspector with this selection.
    },
    [transport],
  );

  const barBeat = coords.timeToBarBeat(transport.currentTime);
  const keyLabel = artifacts.harmonicLayer.data?.global_key?.label ?? "— key";

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-header__left">
          <button
            type="button"
            className="tp"
            style={{ fontSize: 18 }}
            aria-label="Toggle menu"
            aria-pressed={drawerOpen}
            onClick={() => setDrawerOpen((open) => !open)}
          >
            <i className="ph ph-list" />
          </button>
          <div className="app-header__divider" />
          <div className="app-header__transport">
            <button type="button" className="tp" aria-label="To start" onClick={() => transport.seek(0)}>
              <i className="ph ph-skip-back" />
            </button>
            <button type="button" className="tp" aria-label="Previous bar" onClick={() => stepBar(-1)}>
              <i className="ph ph-rewind" />
            </button>
            <button type="button" className="tp" aria-label="Previous beat" onClick={() => stepBeat(-1)}>
              <i className="ph ph-caret-left" />
            </button>
            <button
              type="button"
              className="tp tp-main"
              aria-label={transport.playing ? "Pause" : "Play"}
              onClick={transport.togglePlay}
            >
              <i className={`ph ${transport.playing ? "ph-pause" : "ph-play"}`} />
            </button>
            <button type="button" className="tp" aria-label="Next beat" onClick={() => stepBeat(1)}>
              <i className="ph ph-caret-right" />
            </button>
            <button type="button" className="tp" aria-label="Next bar" onClick={() => stepBar(1)}>
              <i className="ph ph-fast-forward" />
            </button>
          </div>
        </div>

        <div className="app-header__center">
          <div>
            <span className="app-header__time">{formatClock(transport.currentTime)}</span>
            <span className="app-header__time-sep"> / </span>
            <span className="app-header__total">{formatClock(duration)}</span>
          </div>
          <div className="app-header__divider" />
          <div style={{ display: "flex", alignItems: "baseline", gap: "var(--space-2)" }}>
            <span className="app-header__barbeat">
              {barBeat.bar}.{barBeat.beat}
            </span>
            <span className="app-header__barbeat-caption">bar.beat</span>
          </div>
        </div>

        <div className="app-header__right">
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

      <main className="app-main">
        {drawerOpen && (
          <nav className="app-drawer" aria-label="Primary">
            <div>
              <div className="app-drawer__section-label">Analysis</div>
              <div className="nav">
                {DRAWER_ENTRIES.map((entry) => (
                  <button
                    key={entry.id}
                    type="button"
                    className="dr-item"
                    aria-current={activeView === entry.id ? "page" : undefined}
                    onClick={() => setActiveView(entry.id)}
                  >
                    <i className={`ph ${entry.icon}`} />
                    {entry.label}
                  </button>
                ))}
              </div>
            </div>
          </nav>
        )}

        <div className="app-timeline-wrap" style={{ position: "relative", flex: 1, minWidth: 0, display: "flex" }}>
          {activeView === "song" ? (
            <SongPicker
              songs={songs}
              current={song}
              error={discoveryError}
              onPick={(name) => {
                setSong(name);
                setActiveView("timeline");
              }}
            />
          ) : song ? (
            <>
              <TimelineGrid
                coords={coords}
                lanes={laneState.visibleLanes}
                sections={sections}
                currentTime={transport.currentTime}
                playing={transport.playing}
                onSeek={transport.seek}
                onToggleExpand={laneState.toggleExpanded}
                onSelectSegment={handleSelectSegment}
                scrollerRef={scrollerRef}
              />
              {laneListOpen && (
                <LaneList
                  lanes={laneState.lanes}
                  onToggleVisible={laneState.toggleVisible}
                  onToggleExpanded={laneState.toggleExpanded}
                  onShowAll={laneState.showAll}
                  onReset={laneState.resetToDefaults}
                  onClose={() => setLaneListOpen(false)}
                />
              )}
            </>
          ) : (
            <div className="app-timeline tl">
              <div className="app-timeline__stub" style={{ padding: "var(--space-8)" }}>
                No song selected — open “Select Song”.
              </div>
            </div>
          )}
        </div>

        {activeView !== "timeline" && activeView !== "song" && (
          <aside className="app-rightpanel" aria-label={activeView}>
            <div className="card-kicker">{drawerLabel(activeView)}</div>
            <p className="card-body">This surface is built in a later plan item. The shell is chrome-only.</p>
          </aside>
        )}
      </main>

      <footer className="app-footer">
        <div className="app-footer__zoom">
          <button
            type="button"
            className="zic"
            aria-label="Zoom out"
            onClick={() => setPxPerBar((v) => zoomOutPxPerBar(v))}
          >
            <i className="ph ph-magnifying-glass-minus" />
          </button>
          <input
            type="range"
            min={PX_PER_BAR_MIN}
            max={PX_PER_BAR_MAX}
            value={pxPerBar}
            aria-label="Zoom (px per bar)"
            style={{ width: 148 }}
            onChange={(event) => setPxPerBar(clampPxPerBar(Number(event.target.value)))}
          />
          <button
            type="button"
            className="zic"
            aria-label="Zoom in"
            onClick={() => setPxPerBar((v) => zoomInPxPerBar(v))}
          >
            <i className="ph ph-magnifying-glass-plus" />
          </button>
          <span className="app-footer__ppb">{ppbLabel(pxPerBar)}</span>
          <button type="button" className="zbtn" onClick={fitToWidth}>
            <i className="ph ph-arrows-out-line-horizontal" />
            Fit to width
          </button>
        </div>
        <div className="app-footer__spacer" />
        <button
          type="button"
          className="zbtn"
          aria-pressed={laneListOpen}
          onClick={() => setLaneListOpen((open) => !open)}
        >
          <i className="ph ph-sliders-horizontal" />
          Lanes
        </button>
      </footer>
    </div>
  );
}

function SongPicker({
  songs,
  current,
  error,
  onPick,
}: {
  songs: readonly string[];
  current: string | null;
  error: string | null;
  onPick: (song: string) => void;
}): React.JSX.Element {
  return (
    <div className="app-rightpanel" style={{ width: "100%", borderLeft: "none" }}>
      <div className="card-kicker">Select Song</div>
      {error && <p className="card-body">Discovery failed: {error}</p>}
      {!error && songs.length === 0 && <p className="card-body">No analysed songs found.</p>}
      <div className="nav" style={{ marginTop: "var(--space-4)" }}>
        {songs.map((name) => (
          <button
            key={name}
            type="button"
            className="dr-item"
            aria-current={name === current ? "page" : undefined}
            onClick={() => onPick(name)}
          >
            <i className="ph ph-file-audio" />
            {name}
          </button>
        ))}
      </div>
    </div>
  );
}

function drawerLabel(view: DrawerView): string {
  const entry = DRAWER_ENTRIES.find((candidate) => candidate.id === view);
  return entry ? entry.label : view;
}
