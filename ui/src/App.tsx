import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { artifactPaths, discoverSongs, useSong } from "./data";
import type { HumanHintsFile, SectionRow } from "./data/types";
import { buildHumanHintsPayload, saveHumanHints } from "./data/saveHumanHints";
import { draftToHint, hintToDraft } from "./panel/hintDraft";
import {
  BlockInspector,
  HintEditorPanel,
  LaneEventsPanel,
  ReviewQueuePanel,
  RightPanel,
  LANE_LABELS,
  selectionFromMarker,
  selectionFromSection,
  type BlockSelection,
  type HintSeed,
  type PanelMode,
} from "./panel";
import { ArtifactInspector } from "./inspector";
import { resolveKeyAction, shouldPreventDefault } from "./app/keymap";
import {
  loadLeftPanelOpen,
  saveLeftPanelOpen,
  shouldDismissLeftPanel,
} from "./app/panelState";
import { seekTimeForCardClick } from "./app/transportRules";
import {
  selectSongListState,
  selectSongLoadState,
  type ArtifactLoadStatus,
  type SongListState,
} from "./app/loadStates";
import { makeCoords } from "./timeline/coords";
import {
  followScrollLeft,
  isUserScroll,
  LABEL_WIDTH,
  loadFollowPlayhead,
  saveFollowPlayhead,
} from "./timeline/follow";
import { CanvasLane, type CanvasLaneSource } from "./timeline/CanvasLane";
import { FitToWidthButton } from "./timeline/FitToWidthButton";
import { SparseLane } from "./timeline/SparseLane";
import {
  buildLaneBlocks,
  type LaneContentSources,
  type SparseBlock,
} from "./timeline/laneContent";
import { LaneList } from "./timeline/LaneList";
import type { LaneMarker } from "./timeline/laneRenderers";
import { LANE_DEFS, useLaneState } from "./timeline/laneState";
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
  // external word-level sung lyrics (reference/moises)
  "moisesLyrics",
  // item 9 sparse lanes
  "patterns",
  "identifierHints",
  "machineEvents",
  "mlEvents",
  "symbolicPhrases",
  // drop-sequence exploration (experiments/drop_detection)
  "dropProposals",
  // wave-2 experiments (docs/experiments_pending.md run orders 1-3, 6)
  "vocalPhrases",
  "reactiveBands",
  "gestures",
  "grid",
  // named song form under review (experiments/allin1)
  "allin1",
  // texture / character blocks under review (experiments/clap)
  "character",
  // sung lyrics + timing under review (experiments/vocalparse, acestep_transcriber)
  "vocalTranscription",
] as const;

/** sparse lane id → the single artifact key that backs it (drives empty-state). */
const SPARSE_LANE_ARTIFACT: Record<string, (typeof TIMELINE_KEYS)[number]> = {
  humanHints: "humanHints",
  moisesLyrics: "moisesLyrics",
  dropProposals: "dropProposals",
  vocalPhrases: "vocalPhrases",
  reactiveBands: "reactiveBands",
  gestures: "gestures",
  gridPhrase: "grid",
  allin1Transitions: "allin1",
  allin1Sections: "allin1",
  character: "character",
  vocalTranscription: "vocalTranscription",
  sections: "sectionsTopLevel",
  chords: "harmonicLayer",
  patterns: "patterns",
  identifierHints: "identifierHints",
  machineEvents: "machineEvents",
  mlEvents: "mlEvents",
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
  // Left panel (drawer): collapsed by default on first load (plan item 4 / R2),
  // open/closed persisted per session.
  const [drawerOpen, setDrawerOpen] = useState(loadLeftPanelOpen);
  const [activeView, setActiveView] = useState<DrawerView>("timeline");
  const [song, setSong] = useState<string | null>(null);
  const [songs, setSongs] = useState<string[]>([]);
  const [discoveryError, setDiscoveryError] = useState<string | null>(null);
  const [discoveryLoaded, setDiscoveryLoaded] = useState(false);
  const [pxPerBar, setPxPerBar] = useState(62);
  const [laneListOpen, setLaneListOpen] = useState(false);
  const [scrollLeft, setScrollLeft] = useState(0);
  const [viewportWidth, setViewportWidth] = useState(0);
  // plan v1.5 item 6 / R6: follow the playhead while playing. Persisted per
  // session, default on (D7). A user scroll during playback flips it off.
  const [followPlayhead, setFollowPlayhead] = useState(loadFollowPlayhead);

  // Right-panel modes (item 6). `review` is item 7's seam.
  const [panelMode, setPanelMode] = useState<PanelMode | null>(null);
  const [selection, setSelection] = useState<BlockSelection | null>(null);
  // plan v1.5 item 3: the sparse lane whose stacked events panel is open.
  const [eventsLaneId, setEventsLaneId] = useState<string | null>(null);
  const [activeHintRef, setActiveHintRef] = useState<string | null>(null);
  const [hintsOverride, setHintsOverride] = useState<HumanHintsFile | null>(null);
  // A pending "open the hint editor on a pre-filled draft" request — from a
  // double-click on the Human Hints lane (item 8) or the block inspector's
  // "Create human hint" action (item 9). `nonce` makes each request distinct so
  // the panel consumes it exactly once.
  const [hintSeed, setHintSeed] = useState<HintSeed | null>(null);

  const scrollerRef = useRef<HTMLDivElement>(null);
  // plan v1.5 D6: the offset the follow effect last wrote, so the scroll
  // listener can tell a user scroll from the effect's own. null until the
  // effect writes.
  const autoScrollRef = useRef<number | null>(null);
  const laneState = useLaneState();

  // Deep-link: `/?song=<name>` selects a song on load, and the current
  // selection is mirrored back into the URL so a reload restores it. This is
  // also the entry point the visual-regression suite drives (`gotoSong`).
  useEffect(() => {
    const initial = new URLSearchParams(window.location.search).get("song");
    if (initial) {
      setSong(initial);
      setActiveView("timeline");
    }
  }, []);

  useEffect(() => {
    const url = new URL(window.location.href);
    if (song) url.searchParams.set("song", song);
    else url.searchParams.delete("song");
    window.history.replaceState(null, "", url);
  }, [song]);

  // Persist the left panel open/closed state (plan item 4).
  useEffect(() => {
    saveLeftPanelOpen(drawerOpen);
  }, [drawerOpen]);

  // Persist the follow-playhead flag (plan v1.5 item 6 / D7).
  useEffect(() => {
    saveFollowPlayhead(followPlayhead);
  }, [followPlayhead]);

  // R5 (plan v1.5 item 2): while the drawer is open, a mousedown anywhere
  // outside it (and outside the burger) closes it. `mousedown`, not `click`,
  // matches RightPanel's dismissal so a drag that starts outside also closes.
  // Registered only while open; removed on cleanup.
  useEffect(() => {
    if (!drawerOpen) return;
    const onPointer = (event: MouseEvent): void => {
      if (shouldDismissLeftPanel(true, event.target as Element | null)) {
        setDrawerOpen(false);
      }
    };
    document.addEventListener("mousedown", onPointer);
    return () => document.removeEventListener("mousedown", onPointer);
  }, [drawerOpen]);

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

  const { artifacts } = useSong(song, TIMELINE_KEYS);
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
      moisesLyrics: artifacts.moisesLyrics.data,
      dropProposals: artifacts.dropProposals.data,
      vocalPhrases: artifacts.vocalPhrases.data,
      reactiveBands: artifacts.reactiveBands.data,
      gestures: artifacts.gestures.data,
      grid: artifacts.grid.data,
      allin1: artifacts.allin1.data,
      character: artifacts.character.data,
      vocalTranscription: artifacts.vocalTranscription.data,
      sections,
      harmonicLayer: artifacts.harmonicLayer.data,
      patterns: artifacts.patterns.data,
      identifierHints: artifacts.identifierHints.data,
      machineEvents: artifacts.machineEvents.data,
      mlEvents: artifacts.mlEvents.data,
      symbolicPhrases: artifacts.symbolicPhrases.data,
    }),
    [
      humanHintsFile,
      artifacts.moisesLyrics.data,
      artifacts.dropProposals.data,
      artifacts.vocalPhrases.data,
      artifacts.reactiveBands.data,
      artifacts.gestures.data,
      artifacts.grid.data,
      artifacts.allin1.data,
      artifacts.character.data,
      artifacts.vocalTranscription.data,
      sections,
      artifacts.harmonicLayer.data,
      artifacts.patterns.data,
      artifacts.identifierHints.data,
      artifacts.machineEvents.data,
      artifacts.mlEvents.data,
      artifacts.symbolicPhrases.data,
    ],
  );

  // Reset panel + hint override when the song changes.
  useEffect(() => {
    setPanelMode(null);
    setSelection(null);
    setActiveHintRef(null);
    setHintsOverride(null);
    setHintSeed(null);
    setEventsLaneId(null);
  }, [song]);

  const closePanel = useCallback(() => {
    setPanelMode(null);
    setSelection(null);
    setActiveHintRef(null);
    setHintSeed(null);
    setEventsLaneId(null);
  }, []);

  // plan v1.5 item 3 / R2: open the stacked events panel for a lane, replacing
  // any previous lane panel; a second click on the same lane's opener closes it.
  const toggleLaneEvents = useCallback(
    (laneId: string) => {
      if (panelMode === "lane" && eventsLaneId === laneId) {
        setPanelMode(null);
        setEventsLaneId(null);
        return;
      }
      setSelection(null);
      setActiveHintRef(null);
      setHintSeed(null);
      setEventsLaneId(laneId);
      setPanelMode("lane");
    },
    [panelMode, eventsLaneId],
  );

  // plan v1.5 item 3: props for the lane-events panel, or null when it is shut.
  const eventsPanel = useMemo(() => {
    if (panelMode !== "lane" || !eventsLaneId) return null;
    const key = SPARSE_LANE_ARTIFACT[eventsLaneId];
    const art = key ? artifacts[key] : null;
    const status: ArtifactLoadStatus = art?.status ?? "idle";
    const laneDef = LANE_DEFS.find((d) => d.id === eventsLaneId);
    return {
      laneId: eventsLaneId,
      laneLabel: laneDef?.label ?? eventsLaneId,
      experiment: laneDef?.experiment,
      blocks: buildLaneBlocks(eventsLaneId, laneContentSources),
      status,
      error: art?.error?.message ?? null,
    };
  }, [panelMode, eventsLaneId, artifacts, laneContentSources]);

  // R3/D1 + D2: a lane-events card click seeks (only when paused) and nothing
  // else — the panel stays on the same lane.
  const handleSelectBlock = useCallback(
    (block: SparseBlock) => {
      const seekTo = seekTimeForCardClick(transport.isPlaying, block.start_s);
      if (seekTo !== null) transport.seekTo(seekTo);
    },
    [transport],
  );

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

  // item 8: a double-click on empty Human Hints lane background seeds a new
  // 1.0s draft hint in the editor and opens it.
  const handleCreateHintAt = useCallback((time: number) => {
    setSelection(null);
    setActiveHintRef(null);
    setHintSeed({ start: time, end: time + 1.0, nonce: Date.now() });
    setPanelMode("hint");
  }, []);

  // plan v1.5 item 9 / R8: promote the inspected event to a new, editable human
  // hint. Seeds an unsaved draft pre-filled from the block — no seek, no save,
  // no write to the source artifact (D10, D13).
  const handleCreateHintFromSelection = useCallback((sel: BlockSelection) => {
    const end =
      typeof sel.end_s === "number" && Number.isFinite(sel.end_s)
        ? sel.end_s
        : sel.start_s + 1.0;
    // D11: one readable string naming the lane the event came from. Label via
    // LANE_LABELS, experiment via LANE_DEFS; fall back to the raw lane id when
    // the lane is in neither (constitution §2).
    const laneLabel = LANE_LABELS[sel.laneId] ?? sel.laneId;
    const experiment = LANE_DEFS.find((d) => d.id === sel.laneId)?.experiment;
    const capturedFrom = experiment
      ? `${laneLabel} · experiments/${experiment}`
      : laneLabel;
    setSelection(null);
    setActiveHintRef(null);
    setHintSeed({
      start: sel.start_s,
      end,
      title: sel.label,
      summary: sel.summary ?? "",
      capturedFrom,
      nonce: Date.now(),
    });
    setPanelMode("hint");
  }, []);

  const handleSelectMarker = useCallback(
    (marker: LaneMarker) => {
      // R3/D1: a card click never moves the playhead while playing.
      const seekTo = seekTimeForCardClick(transport.isPlaying, marker.time);
      if (seekTo !== null) transport.seekTo(seekTo);
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

  // item 7 (ui-issues finding 7): the server-normalised file returned by the
  // save flows into `hintsOverride`, which authoritatively updates the Human
  // Hints lane in place. We deliberately do NOT `reloadSong()` here — a full
  // reload reseeds every artifact to loading/null, collapsing beats → coords →
  // timelineW to zero and resetting the scroller's zoom/scroll to song start on
  // every hint drag-commit and panel Save.
  const handleSaveHints = useCallback((file: HumanHintsFile) => {
    setHintsOverride(file);
  }, []);

  // item 10: persist a humanHints block's new start/end after a timeline drag.
  // Builds the full file from the current hints (only the dragged one's times
  // change) through the same validator/PUT the hint editor uses, then feeds the
  // server-normalised result through `handleSaveHints`. Rejects on failure so
  // `SparseLane` reverts its optimistic preview.
  const handleCommitHintTimes = useCallback(
    async (id: string, start: number, end: number) => {
      if (!song) throw new Error("No song selected.");
      const current = humanHintsFile?.human_hints ?? [];
      const drafts = current.map((hint) => {
        const draft = hintToDraft(hint);
        return hint.id === id
          ? { ...draft, start: String(start), end: String(end) }
          : draft;
      });
      const payload = buildHumanHintsPayload(
        humanHintsFile?.song_name || song,
        drafts.map(draftToHint),
      );
      const written = await saveHumanHints(song, payload);
      handleSaveHints(written);
    },
    [song, humanHintsFile, handleSaveHints],
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
              onCommitHintTimes={
                lane.id === "humanHints" ? handleCommitHintTimes : undefined
              }
              onCreateHint={
                lane.id === "humanHints" ? handleCreateHintAt : undefined
              }
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
      handleCommitHintTimes,
      handleCreateHintAt,
    ],
  );

  // Latest values for the scroll listener below, read through refs so the
  // listener need not re-register on every playback tick (plan v1.5 item 6).
  const followPlayheadRef = useRef(followPlayhead);
  followPlayheadRef.current = followPlayhead;
  const playingRef = useRef(transport.isPlaying);
  playingRef.current = transport.isPlaying;

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
      // plan v1.5 item 6 / D6: a user scroll during playback turns following
      // off. `isUserScroll` distinguishes it from the follow effect's own write.
      if (
        playingRef.current &&
        followPlayheadRef.current &&
        isUserScroll(el.scrollLeft, autoScrollRef.current)
      ) {
        setFollowPlayhead(false);
      }
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

  // Follow-playhead scroll while playing (design notes §2; plan v1.5 item 6).
  useEffect(() => {
    const el = scrollerRef.current;
    if (!el) return;
    if (!(followPlayhead && transport.isPlaying)) return;
    const next = followScrollLeft({
      playheadX: LABEL_WIDTH + coords.timeToX(transport.currentTime),
      scrollLeft: el.scrollLeft,
      viewportWidth: el.clientWidth,
      maxScrollLeft: el.scrollWidth - el.clientWidth,
      playing: transport.isPlaying,
    });
    if (Math.abs(next - el.scrollLeft) > 0.5) {
      autoScrollRef.current = next;
      el.scrollLeft = next;
    }
  }, [transport.currentTime, transport.isPlaying, followPlayhead, coords]);

  const fitToWidth = useCallback(() => {
    const el = scrollerRef.current;
    if (!el || !duration) return;
    setPxPerBar(fitToWidthPxPerBar(el.clientWidth, duration, coords.medianBarSeconds));
  }, [duration, coords.medianBarSeconds]);

  const { stepBeat, stepBar } = transport;

  // esc target: panel → review view → lane list → left panel (drawer).
  // (refinement §10, extended by plan item 4 — the left panel is the drawer.)
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
      // R3/D1: suppressed while the transport is playing.
      const seekTo = seekTimeForCardClick(
        transport.isPlaying,
        block.section.start,
      );
      if (seekTo !== null) transport.seekTo(seekTo);
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

  // --- Test readiness marker (regression guide §5.2) ----------------------
  // `data-ui-ready` is "0" during any song load / full re-layout and flips to
  // "1" one paint after a fully-settled song's visible lanes have had a chance
  // to draw. `data-ui-loading` carries the in-flight artifact count.
  const inFlightCount = useMemo(
    () =>
      TIMELINE_KEYS.reduce(
        (n, key) => n + (artifacts[key].status === "loading" ? 1 : 0),
        0,
      ),
    [artifacts],
  );

  const canRenderTimeline =
    !!song && songLoadState.kind !== "loading" && songLoadState.kind !== "fatal";

  useEffect(() => {
    document.documentElement.dataset.uiLoading = String(inFlightCount);
  }, [inFlightCount]);

  // Clear the marker at the start of every song load / full re-layout.
  useEffect(() => {
    document.documentElement.dataset.uiReady = "0";
  }, [song, pxPerBar, viewportWidth]);

  useEffect(() => {
    if (!canRenderTimeline || inFlightCount > 0) {
      document.documentElement.dataset.uiReady = "0";
      return;
    }
    let raf2 = 0;
    const raf1 = requestAnimationFrame(() => {
      raf2 = requestAnimationFrame(() => {
        document.documentElement.dataset.uiReady = "1";
      });
    });
    return () => {
      cancelAnimationFrame(raf1);
      cancelAnimationFrame(raf2);
    };
  }, [canRenderTimeline, inFlightCount, pxPerBar, viewportWidth, activeView]);

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-header__left">
          <button
            type="button"
            className="tp"
            style={{ fontSize: 18 }}
            data-testid="burger-toggle"
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
          <span className="app-header__barbeat">
            {barBeat.bar}.{barBeat.beat}
          </span>
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
          <nav
            className="app-drawer"
            aria-label="Primary"
            data-testid="left-panel"
            data-open={drawerOpen ? "true" : "false"}
            ref={drawerRef}
          >
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
                // R4/D4: picking a song hides the left panel. Deliberately not
                // done on the `?song=` deep-link effect or the song-change
                // reset effect — only a user pick counts.
                setDrawerOpen(false);
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
                onOpenLaneEvents={toggleLaneEvents}
                eventsLaneId={panelMode === "lane" ? eventsLaneId : null}
                scrollerRef={scrollerRef}
              />
              {laneListOpen && (
                <LaneList
                  lanes={laneState.lanes}
                  onToggleVisible={laneState.toggleVisible}
                  onToggleExpanded={laneState.toggleExpanded}
                  onShowAll={laneState.showAll}
                  onHideAll={laneState.hideAll}
                  onReset={laneState.resetToDefaults}
                  onClose={() => setLaneListOpen(false)}
                />
              )}
              {/* item 10 (refinement v2.2 §10): lane-status notices are
                  low-urgency and belong out of the primary work area, so this
                  renders below the timeline / lane stack, flush at the bottom. */}
              {songLoadState.kind === "degraded" && (
                <div
                  className="app-timeline__banner app-timeline__banner--bottom"
                  role="status"
                >
                  {songLoadState.missing.length} lane
                  {songLoadState.missing.length === 1 ? "" : "s"} missing an artifact:{" "}
                  {songLoadState.missing.join(", ")}. Those lanes show an empty state.
                </div>
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
            <BlockInspector
              selection={selection}
              onCreateHint={handleCreateHintFromSelection}
            />
          </RightPanel>
        )}

        {activeView === "timeline" && song && eventsPanel && (
          <LaneEventsPanel
            laneId={eventsPanel.laneId}
            laneLabel={eventsPanel.laneLabel}
            experiment={eventsPanel.experiment}
            blocks={eventsPanel.blocks}
            status={eventsPanel.status}
            error={eventsPanel.error}
            currentTime={transport.currentTime}
            playing={transport.isPlaying}
            onClose={closePanel}
            onSelectBlock={handleSelectBlock}
          />
        )}

        {activeView === "timeline" && song && panelMode === "hint" && (
          <HintEditorPanel
            song={song}
            file={humanHintsFile}
            currentTime={transport.currentTime}
            activeReference={activeHintRef}
            seed={hintSeed}
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
            data-testid="zoom-out"
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
            data-testid="zoom-in"
            aria-label="Zoom in"
            onClick={() => setPxPerBar((v) => zoomInPxPerBar(v))}
          >
            <i className="ph ph-magnifying-glass-plus" />
          </button>
          <span className="app-footer__ppb">{ppbLabel(pxPerBar)}</span>
          <FitToWidthButton onClick={fitToWidth} />
        </div>
        <div className="app-footer__spacer" />
        <button
          type="button"
          className="zbtn zbtn--icon"
          data-testid="follow-toggle"
          aria-pressed={followPlayhead}
          aria-label="Follow playhead"
          title="Follow the playhead while playing"
          onClick={() => setFollowPlayhead((on) => !on)}
        >
          <i className="ph ph-arrows-in-line-horizontal" />
        </button>
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
