// usePanelState.ts — which right-panel/editor is open, what's selected in
// it, and every handler that opens or seeds one. Split out of App.tsx (v3.9
// item 7) with no behaviour change.

import { useCallback, useState } from "react";

import type { HumanSegmentSeed } from "../data/types";
import {
  LANE_LABELS,
  selectionFromMarker,
  selectionFromSection,
  type BlockSelection,
  type HintSeed,
  type SegmentSeed,
  type PanelMode,
} from "../panel";
import type { LaneMarker } from "../timeline/laneRenderers";
import { LANE_DEFS } from "../timeline/laneState";
import type { SegmentBlock } from "../timeline/segments";
import { seekTimeForCardClick } from "./transportRules";

export interface PanelStateInputs {
  isPlaying: boolean;
  seekTo: (time: number) => void;
  isTimeVisible: (seconds: number) => boolean;
  scrollTimelineToTime: (seconds: number) => void;
  /** A click on an LLM Pending Proposals block opens the Pending Proposals
   *  drawer (a DrawerView, not a PanelMode) scrolled to that proposal's card. */
  openPendingProposal: (reference: string) => void;
}

export type PanelStateResult = ReturnType<typeof usePanelState>;

export function usePanelState({
  isPlaying,
  seekTo,
  isTimeVisible,
  scrollTimelineToTime,
  openPendingProposal,
}: PanelStateInputs) {
  // Right-panel modes (item 6). `review` is item 7's seam.
  const [panelMode, setPanelMode] = useState<PanelMode | null>(null);
  const [selection, setSelection] = useState<BlockSelection | null>(null);
  // plan v1.5 item 3: the sparse lane whose stacked events panel is open.
  const [eventsLaneId, setEventsLaneId] = useState<string | null>(null);
  const [activeHintRef, setActiveHintRef] = useState<string | null>(null);
  // Same reasoning as `activeHintRef`, for the Human Sections lane.
  const [activeSectionRef, setActiveSectionRef] = useState<string | null>(null);
  // A pending "open the hint editor on a pre-filled draft" request — from a
  // double-click on the Human Hints lane (item 8) or the block inspector's
  // "Create human hint" action (item 9). `nonce` makes each request distinct so
  // the panel consumes it exactly once.
  const [hintSeed, setHintSeed] = useState<HintSeed | null>(null);
  // Same reasoning as `hintSeed`, for the Human Sections lane.
  const [sectionSeed, setSectionSeed] = useState<SegmentSeed | null>(null);

  const closePanel = useCallback(() => {
    setPanelMode(null);
    setSelection(null);
    setActiveHintRef(null);
    setActiveSectionRef(null);
    setHintSeed(null);
    setSectionSeed(null);
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
      setActiveSectionRef(null);
      setHintSeed(null);
      setSectionSeed(null);
      setEventsLaneId(laneId);
      setPanelMode("lane");
    },
    [panelMode, eventsLaneId],
  );

  const openHintEditor = useCallback((reference: string | null) => {
    setSelection(null);
    setActiveHintRef(reference);
    setPanelMode("hint");
  }, []);

  // Same conventions as the Human Hints editor, for Human Sections.
  const openSegmentEditor = useCallback((reference: string | null) => {
    setSelection(null);
    setActiveSectionRef(reference);
    setPanelMode("segment");
  }, []);

  // item 8: a double-click on empty Human Hints lane background seeds a new
  // 1.0s draft hint in the editor and opens it.
  const handleCreateHintAt = useCallback((time: number) => {
    setSelection(null);
    setActiveHintRef(null);
    setHintSeed({ start: time, end: time + 1.0, nonce: Date.now() });
    setPanelMode("hint");
  }, []);

  const handleCreateSegmentAt = useCallback((time: number) => {
    setSelection(null);
    setActiveSectionRef(null);
    setSectionSeed({ start: time, end: time + 1.0, nonce: Date.now() });
    setPanelMode("segment");
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
    // the lane is in neither (no silent fallbacks — never guess to keep a run green).
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

  // "Create human section" on an allin1 / Segment Seeds / Moises block: seeds an
  // unsaved draft in the segment editor from the block — no save, no write to
  // the source artifact. Seed-lane blocks carry their draft energy/tension/rhythm.
  const handleCreateSectionFromSelection = useCallback((sel: BlockSelection) => {
    const end =
      typeof sel.end_s === "number" && Number.isFinite(sel.end_s)
        ? sel.end_s
        : sel.start_s + 1.0;
    const raw = (sel.raw ?? {}) as Partial<HumanSegmentSeed> & { function?: string | null };
    const isSeedLane = sel.laneId === "segmentSeeds";
    setSelection(null);
    setActiveSectionRef(null);
    setSectionSeed({
      start: sel.start_s,
      end,
      nonce: Date.now(),
      label: raw.function ?? raw.label ?? null,
      ...(isSeedLane ? { energy: raw.energy ?? null, tension: raw.tension ?? null, rhythm: raw.rhythm ?? null } : {}),
    });
    setPanelMode("segment");
  }, []);

  const handleSelectMarker = useCallback(
    (marker: LaneMarker) => {
      // R3/D1: a card click never moves the playhead while playing.
      const seekTime = seekTimeForCardClick(isPlaying, marker.time);
      if (seekTime !== null) {
        seekTo(seekTime);
        // scroll the playhead into view only when it's out of the current
        // window — never yank the timeline when it's already visible.
        if (!isTimeVisible(seekTime)) scrollTimelineToTime(seekTime);
      }
      if (marker.laneId === "humanHints") {
        openHintEditor(marker.id);
        return;
      }
      if (marker.laneId === "humanSections") {
        openSegmentEditor(marker.id);
        return;
      }
      if (marker.laneId === "llmPendingProposals") {
        const rawRef = (marker.raw as Record<string, unknown> | undefined)?.reference;
        openPendingProposal(typeof rawRef === "string" ? rawRef : marker.id);
        return;
      }
      setActiveHintRef(null);
      setActiveSectionRef(null);
      setSelection(selectionFromMarker(marker));
      setPanelMode("inspector");
    },
    [
      isPlaying,
      seekTo,
      openHintEditor,
      openSegmentEditor,
      openPendingProposal,
      isTimeVisible,
      scrollTimelineToTime,
    ],
  );

  const handleSelectSegment = useCallback(
    (block: SegmentBlock) => {
      // Move the shared playhead to the block start (design notes §4).
      // R3/D1: suppressed while the transport is playing.
      const seekTime = seekTimeForCardClick(isPlaying, block.section.start);
      if (seekTime !== null) seekTo(seekTime);
      setActiveHintRef(null);
      setSelection(selectionFromSection(block, "segments"));
      setPanelMode("inspector");
    },
    [isPlaying, seekTo],
  );

  return {
    panelMode,
    setPanelMode,
    selection,
    setSelection,
    eventsLaneId,
    setEventsLaneId,
    activeHintRef,
    setActiveHintRef,
    activeSectionRef,
    setActiveSectionRef,
    hintSeed,
    setHintSeed,
    sectionSeed,
    setSectionSeed,
    closePanel,
    toggleLaneEvents,
    openHintEditor,
    openSegmentEditor,
    handleCreateHintAt,
    handleCreateSegmentAt,
    handleCreateHintFromSelection,
    handleCreateSectionFromSelection,
    handleSelectMarker,
    handleSelectSegment,
    // `closePanel`'s body is exactly the song-change reset (see App.tsx) —
    // reused rather than duplicated.
    resetPanelState: closePanel,
  };
}
