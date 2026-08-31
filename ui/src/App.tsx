import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { artifactPaths, discoverSongs, useSong } from "./data";
import type { HumanHintsFile, SectionRow } from "./data/types";
import {
  BlockInspector,
  HintEditorPanel,
  ReviewQueuePanel,
  RightPanel,
  selectionFromMarker,
  selectionFromSection,
  type BlockSelection,
  type PanelMode,
} from "./panel";
import { ArtifactInspector } from "./inspector";
import { resolveKeyAction, shouldPreventDefault } from "./app/keymap";
import {
  selectSongListState,
  selectSongLoadState,
  type ArtifactLoadStatus,
  type SongListState,
} from "./app/loadStates";
import { makeCoords } from "./timeline/coords";
import { followScrollLeft, LABEL_WIDTH } from "./timeline/follow";
import { CanvasLane, type CanvasLaneSource } from "./timeline/CanvasLane";
import { SparseLane } from "./timeline/SparseLane";
import { buildLaneBlocks, type LaneContentSources } from "./timeline/laneContent";
import { LaneList } from "./timeline/LaneList";
import type { LaneMarker } from "./timeline/laneRenderers";
import { useLaneState } from "./timeline/laneState";
import type { Lane } from "./timeline/laneState";
import type { SegmentBlock } from "./timeline/segments";
import { TimelineGrid } from "./timeline/TimelineGrid";
import { useTransport } from "./timeline/useTransport";
import { WaveformLane } from "./timeline/WaveformLane";
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

const TIMELINE_KEYS = [
  "info",
  "beats",
  "sectionsTopLevel",
  "harmonicLayer",
  "fftBands",
  "rmsLoudness",
  "loudnessEnvelope",
  "drums",
  "energy",
  "humanHints",
  // item 9 sparse lanes
  "patterns",
  "identifierHints",
  "machineEvents",
  "mlEvents",
  "beatdropPlan",
  "symbolicPhrases",
] as const;

/** sparse lane id → the single artifact key that backs it (drives empty-state). */
const SPARSE_LANE_ARTIFACT: Record<string, (typeof TIMELINE_KEYS)[number]> = {
  humanHints: "humanHints",
  sections: "sectionsTopLevel",
  chords: "harmonicLayer",
  patterns: "patterns",
  identifierHints: "identifierHints",
  machineEvents: "machineEvents",
  mlEvents: "mlEvents",
  beatdropPlan: "beatdropPlan",
  phrases: "symbolicPhrases",
};

/** lane id → (artifact key, canvas renderer kind) for the item-5 data lanes. */
const CANVAS_LANES: Record<string, { key: (typeof TIMELINE_KEYS)[number]; kind: CanvasLaneSource["kind"] }> = {
  fftBands: { key: "fftBands", kind: "fft" },
  rmsLoudness: { key: "rmsLoudness", kind: "rms" },
  loudnessEnvelope: { key: "loudnessEnvelope", kind: "env" },
  drums: { key: "drums", kind: "drums" },
  energy: { key: "energy", kind: "energy" },
};

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
  const [discoveryLoaded, setDiscoveryLoaded] = useState(false);
  const [pxPerBar, setPxPerBar] = useState(62);
  const [laneListOpen, setLaneListOpen] = useState(false);
  const [scrollLeft, setScrollLeft] = useState(0);
  const [viewportWidth, setViewportWidth] = useState(0);

  // Right-panel modes (item 6). `review` is item 7's seam.
  const [panelMode, setPanelMode] = useState<PanelMode | null>(null);
  const [selection, setSelection] = useState<BlockSelection | null>(null);
  const [activeHintRef, setActiveHintRef] = useState<string | null>(null);
  const [hintsOverride, setHintsOverride] = useState<HumanHintsFile | null>(null);

  const scrollerRef = useRef<HTMLDivElement>(null);
  const laneState = useLaneState();

  useEffect(() => {
    let cancelled = false;
    discoverSongs()
      .then((result) => {
        if (cancelled) return;
        setSongs(result.songs);
        setDiscoveryError(null);
        setDiscoveryLoaded(true);
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        setDiscoveryError(error instanceof Error ? error.message : "Discovery failed.");
        setDiscoveryLoaded(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const { artifacts, reload: reloadSong } = useSong(song, TIMELINE_KEYS);
  const info = artifacts.info.data;
  const beats = useMemo(() => artifacts.beats.data ?? [], [artifacts.beats.data]);
  const sections: SectionRow[] = useMemo(
    () => artifacts.sectionsTopLevel.data ?? [],
    [artifacts.sectionsTopLevel.data],
  );
  const estimatedDuration = info?.duration ?? beats.at(-1)?.time ?? 0;

  const coords = useMemo(
    () => makeCoords({ beats, duration: estimatedDuration, pxPerBar }),
    [beats, estimatedDuration, pxPerBar],
  );

  const audioUrl = song ? artifactPaths.audio(song) : null;
  const transport = useTransport({ audioUrl, coords });
  const duration = transport.duration || estimatedDuration;

  const humanHintsFile = hintsOverride ?? artifacts.humanHints.data;

  // item 9: block lists for every sparse lane, rebuilt when a source changes.
  const laneContentSources = useMemo<LaneContentSources>(
    () => ({
      humanHints: humanHintsFile,
      sections,
      harmonicLayer: artifacts.harmonicLayer.data,
      patterns: artifacts.patterns.data,
      identifierHints: artifacts.identifierHints.data,
      machineEvents: artifacts.machineEvents.data,
      mlEvents: artifacts.mlEvents.data,
      beatdropPlan: artifacts.beatdropPlan.data,
      symbolicPhrases: artifacts.symbolicPhrases.data,
    }),
    [
      humanHintsFile,
      sections,
      artifacts.harmonicLayer.data,
      artifacts.patterns.data,
      artifacts.identifierHints.data,
      artifacts.machineEvents.data,
      artifacts.mlEvents.data,
      artifacts.beatdropPlan.data,
      artifacts.symbolicPhrases.data,
    ],
  );

  // Reset panel + hint override when the song changes.
  useEffect(() => {
    setPanelMode(null);
    setSelection(null);
    setActiveHintRef(null);
    setHintsOverride(null);
  }, [song]);

  const closePanel = useCallback(() => {
    setPanelMode(null);
    setSelection(null);
    setActiveHintRef(null);
  }, []);

  const scrollTimelineToTime = useCallback(
    (seconds: number) => {
      const el = scrollerRef.current;
      if (!el) return;
      const target = LABEL_WIDTH + coords.timeToX(seconds) - el.clientWidth * 0.3;
      const max = el.scrollWidth - el.clientWidth;
      el.scrollLeft = Math.max(0, Math.min(target, max));
    },
    [coords],
  );

  const openHintEditor = useCallback((reference: string | null) => {
    setSelection(null);
    setActiveHintRef(reference);
    setPanelMode("hint");
  }, []);

  const handleSelectMarker = useCallback(
    (marker: LaneMarker) => {
      transport.seekTo(marker.time);
      if (marker.laneId === "humanHints") {
        openHintEditor(marker.id);
        return;
      }
      setActiveHintRef(null);
      setSelection(selectionFromMarker(marker));
      setPanelMode("inspector");
    },
    [transport, openHintEditor],
  );

  const handleSaveHints = useCallback(
    (file: HumanHintsFile) => {
      setHintsOverride(file);
      reloadSong();
    },
    [reloadSong],
  );

  const renderLaneBody = useCallback(
    (lane: Lane): React.ReactNode => {
      if (lane.id === "waveform") {
        return (
          <WaveformLane
            surface={transport.surface}
            ready={transport.isReady}
            error={transport.error}
            width={coords.timelineW}
          />
        );
      }
      const entry = CANVAS_LANES[lane.id];
      if (entry) {
        const art = artifacts[entry.key];
        return (
          <CanvasLane
            lane={lane}
            coords={coords}
            source={{ kind: entry.kind, data: art.data as never } as CanvasLaneSource}
            status={art.status}
            error={art.error?.message ?? null}
            scrollLeft={scrollLeft}
            viewportWidth={viewportWidth}
            onSeek={transport.seekTo}
            onSelectMarker={handleSelectMarker}
          />
        );
      }

      const sparseKey = SPARSE_LANE_ARTIFACT[lane.id];
      if (sparseKey) {
        const art = artifacts[sparseKey];
        const blocks = buildLaneBlocks(lane.id, laneContentSources);
        return (
          <>
            <SparseLane
              lane={lane}
              laneId={lane.id}
              coords={coords}
              blocks={blocks}
              status={art.status}
              error={art.error?.message ?? null}
              activeId={lane.id === "humanHints" ? activeHintRef : null}
              onSeek={transport.seekTo}
              onSelectMarker={handleSelectMarker}
            />
            {lane.id === "humanHints" && (
              <button
                type="button"
                className="tl-hint-pill tl-hint-pill--new"
                title="New hint at the playhead"
                onClick={() => openHintEditor(null)}
              >
                <i className="ph ph-plus" />
              </button>
            )}
          </>
        );
      }

      if (lane.id === "validation") {
        // Regression Overlay — item 9 ships this as an empty-state stub; the
        // eventComparisons / beat-drift wiring is deferred to item 11's parity
        // pass (validation-artifact id alignment not verified). See D-log.
        return (
          <div className="tl-canvas-lane" style={{ position: "absolute", inset: 0 }}>
            <div className="tl-canvas-lane__state">
              Regression overlay — validation wiring deferred (item 11 parity)
            </div>
          </div>
        );
      }
      return null;
    },
    [
      transport.surface,
      transport.isReady,
      transport.error,
      transport.seekTo,
      coords,
      artifacts,
      scrollLeft,
      viewportWidth,
      handleSelectMarker,
      laneContentSources,
      activeHintRef,
      openHintEditor,
    ],
  );

  // Track the timeline scroll offset + viewport width for the canvas lanes
  // (sub-labels are anchored to the viewport's left edge). rAF-coalesced.
  useEffect(() => {
    const el = scrollerRef.current;
    if (!el) return;
    let raf = 0;
    const sync = () => {
      raf = 0;
      setScrollLeft(el.scrollLeft);
      setViewportWidth(el.clientWidth);
    };
    const onScroll = () => {
      if (!raf) raf = requestAnimationFrame(sync);
    };
    sync();
    el.addEventListener("scroll", onScroll, { passive: true });
    const observer = new ResizeObserver(sync);
    observer.observe(el);
    return () => {
      el.removeEventListener("scroll", onScroll);
      observer.disconnect();
      if (raf) cancelAnimationFrame(raf);
    };
  }, [song, activeView]);

  // Follow-playhead scroll while playing (design notes §2).
  useEffect(() => {
    const el = scrollerRef.current;
    if (!el) return;
    const next = followScrollLeft({
      playheadX: LABEL_WIDTH + coords.timeToX(transport.currentTime),
      scrollLeft: el.scrollLeft,
      viewportWidth: el.clientWidth,
      maxScrollLeft: el.scrollWidth - el.clientWidth,
      playing: transport.isPlaying,
    });
    if (Math.abs(next - el.scrollLeft) > 0.5) el.scrollLeft = next;
  }, [transport.currentTime, transport.isPlaying, coords]);

  const fitToWidth = useCallback(() => {
    const el = scrollerRef.current;
    if (!el || !duration) return;
    setPxPerBar(fitToWidthPxPerBar(el.clientWidth, duration, coords.medianBarSeconds));
  }, [duration, coords.medianBarSeconds]);

  const { stepBeat, stepBar } = transport;

  // esc target: panel → review view → lane list → drawer (refinement §10).
  const closeOverlay = useCallback(() => {
    if (panelMode) {
      closePanel();
      return;
    }
    if (activeView === "review") {
      setActiveView("timeline");
      return;
    }
    if (laneListOpen) {
      setLaneListOpen(false);
      return;
    }
    if (drawerOpen) setDrawerOpen(false);
  }, [panelMode, activeView, laneListOpen, drawerOpen, closePanel]);

  // Single global keyboard listener (plan item 10). Resolution + the
  // input-focus guard live in the pure `keymap` module.
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent): void => {
      const action = resolveKeyAction(event);
      if (!action) return;
      if (action === "closeOverlay") {
        closeOverlay();
        return;
      }
      if (activeView !== "timeline" || !song) return;
      if (shouldPreventDefault(action)) event.preventDefault();
      switch (action) {
        case "playPause":
          transport.togglePlay();
          break;
        case "stepBeatBack":
          stepBeat(-1);
          break;
        case "stepBeatForward":
          stepBeat(1);
          break;
        case "stepBarBack":
          stepBar(-1);
          break;
        case "stepBarForward":
          stepBar(1);
          break;
        case "zoomIn":
          setPxPerBar((v) => zoomInPxPerBar(v));
          break;
        case "zoomOut":
          setPxPerBar((v) => zoomOutPxPerBar(v));
          break;
        case "fitToWidth":
          fitToWidth();
          break;
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [activeView, song, transport, stepBeat, stepBar, fitToWidth, closeOverlay]);

  // Move focus into the drawer when it opens (non-modal — no trap).
  const drawerRef = useRef<HTMLElement>(null);
  const drawerWasOpen = useRef(drawerOpen);
  useEffect(() => {
    // only on an open transition (not initial mount) so we don't grab focus
    // out from under the page on load.
    if (drawerOpen && !drawerWasOpen.current) {
      drawerRef.current?.querySelector<HTMLElement>(".dr-item")?.focus();
    }
    drawerWasOpen.current = drawerOpen;
  }, [drawerOpen]);

  const handleSelectSegment = useCallback(
    (block: SegmentBlock) => {
      // Move the shared playhead to the block start (design notes §4).
      transport.seekTo(block.section.start);
      setActiveHintRef(null);
      setSelection(selectionFromSection(block, "segments"));
      setPanelMode("inspector");
    },
    [transport],
  );

  const barBeat = coords.timeToBarBeat(transport.currentTime);
  const keyLabel = artifacts.harmonicLayer.data?.global_key?.label ?? "— key";

  // Non-happy-path states (plan item 10). Both selectors are pure + unit-tested.
  const songListState = selectSongListState({
    loaded: discoveryLoaded,
    error: discoveryError,
    songs,
  });

  const laneArtifactStatus = useMemo<Record<string, ArtifactLoadStatus>>(() => {
    const entries: Record<string, ArtifactLoadStatus> = {};
    for (const lane of laneState.visibleLanes) {
      const key = CANVAS_LANES[lane.id]?.key ?? SPARSE_LANE_ARTIFACT[lane.id];
      if (key) entries[lane.label] = artifacts[key].status;
    }
    return entries;
  }, [laneState.visibleLanes, artifacts]);

  const songLoadState = selectSongLoadState({
    infoStatus: artifacts.info.status,
    infoError: artifacts.info.error?.message ?? null,
    hasBeats: beats.length > 0,
    laneArtifactStatus,
  });

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
            <button type="button" className="tp" aria-label="To start" onClick={() => transport.seekTo(0)}>
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
              aria-label={transport.isPlaying ? "Pause" : "Play"}
              onClick={transport.togglePlay}
            >
              <i className={`ph ${transport.isPlaying ? "ph-pause" : "ph-play"}`} />
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
          <nav className="app-drawer" aria-label="Primary" ref={drawerRef}>
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
          {activeView === "inspector" ? (
            <ArtifactInspector song={song} />
          ) : activeView === "song" ? (
            <SongPicker
              listState={songListState}
              current={song}
              onPick={(name) => {
                setSong(name);
                setActiveView("timeline");
              }}
            />
          ) : song && songLoadState.kind === "loading" ? (
            <div className="app-timeline tl">
              <div className="app-timeline__stub" style={{ padding: "var(--space-8)" }}>
                Loading {song}…
              </div>
            </div>
          ) : song && songLoadState.kind === "fatal" ? (
            <div className="app-timeline tl">
              <div className="app-timeline__state" style={{ padding: "var(--space-8)" }}>
                <p className="card-kicker">Can’t open {song}</p>
                <p className="card-body">{songLoadState.message}</p>
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  onClick={() => setActiveView("song")}
                >
                  Pick another song
                </button>
              </div>
            </div>
          ) : song ? (
            <>
              {songLoadState.kind === "degraded" && (
                <div className="app-timeline__banner" role="status">
                  {songLoadState.missing.length} lane
                  {songLoadState.missing.length === 1 ? "" : "s"} missing an artifact:{" "}
                  {songLoadState.missing.join(", ")}. Those lanes show an empty state.
                </div>
              )}
              <TimelineGrid
                coords={coords}
                lanes={laneState.visibleLanes}
                sections={sections}
                currentTime={transport.currentTime}
                playing={transport.isPlaying}
                onSeek={transport.seekTo}
                onToggleExpand={laneState.toggleExpanded}
                onSelectSegment={handleSelectSegment}
                renderLaneBody={renderLaneBody}
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

        {activeView === "timeline" && song && panelMode === "inspector" && selection && (
          <RightPanel
            open
            onClose={closePanel}
            aria-label="Block inspector"
            header={<span className="app-rightpanel__kicker">{selection.laneLabel}</span>}
          >
            <BlockInspector selection={selection} />
          </RightPanel>
        )}

        {activeView === "timeline" && song && panelMode === "hint" && (
          <HintEditorPanel
            song={song}
            file={humanHintsFile}
            currentTime={transport.currentTime}
            activeReference={activeHintRef}
            onClose={closePanel}
            onSaved={handleSaveHints}
            onScrollToTime={scrollTimelineToTime}
          />
        )}

        {/* item 7: the review queue is the RightPanel shell's third mode,
            opened from the "Review queue" drawer entry (no lane). */}
        {activeView === "review" &&
          (song ? (
            <ReviewQueuePanel song={song} onClose={() => setActiveView("timeline")} />
          ) : (
            <aside className="app-rightpanel" aria-label="Review queue">
              <div className="card-kicker">Review queue</div>
              <p className="card-body">Select a song to review its open questions.</p>
            </aside>
          ))}
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
  listState,
  current,
  onPick,
}: {
  listState: SongListState;
  current: string | null;
  onPick: (song: string) => void;
}): React.JSX.Element {
  return (
    <div className="app-rightpanel" style={{ width: "100%", borderLeft: "none" }}>
      <div className="card-kicker">Select Song</div>

      {listState.kind === "loading" && (
        <p className="card-body">Discovering analysed songs…</p>
      )}
      {listState.kind === "error" && (
        <p className="card-body">Discovery failed: {listState.message}</p>
      )}
      {listState.kind === "empty" && (
        <p className="card-body">
          No analysed songs found. Run the analysis pipeline so a song appears in
          both <code>data/analysis/</code> and <code>data/songs/</code>.
        </p>
      )}

      {listState.kind === "ready" && (
        <div className="nav" style={{ marginTop: "var(--space-4)" }}>
          {listState.songs.map((name) => (
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
      )}
    </div>
  );
}
