// useLaneVisibility.ts — which lanes start hidden/collapsed on a ready-empty
// artifact, the guarded expand toggle that won't open an empty lane, the
// lane-events panel's props, and the block-review index lookup every
// claim-bearing lane's verdict control reads. Split out of App.tsx (v3.9
// item 7) with no behaviour change.

import { useCallback, useEffect, useMemo } from "react";

import { REVIEWABLE_LANE_IDS, matchBlockReviews, indexBlockReviews } from "../data/blockReviewMatch";
import type { BlockReviewMatched, BlockReviewsFile } from "../data/types";
import type { SongArtifacts } from "../data/useSong";
import { buildLaneBlocks, type LaneContentSources } from "../timeline/laneContent";
import { CANVAS_LANES, SPARSE_LANE_ARTIFACT, TIMELINE_KEYS, canvasLaneHasData } from "../timeline/laneConfig";
import { LANE_DEFS, type UseLaneStateResult } from "../timeline/laneState";
import type { CanvasLaneSource } from "../timeline/CanvasLane";

export interface LaneVisibilityInputs {
  song: string | null;
  laneState: UseLaneStateResult;
  artifacts: SongArtifacts;
  laneContentSources: LaneContentSources;
  panelMode: string | null;
  eventsLaneId: string | null;
  blockReviewsFile: BlockReviewsFile | null;
  /**
   * Owned by the caller (App.tsx), reset to `null` in the same song-change
   * effect that resets panel/override state — that reset MUST be registered
   * (called) before this hook, so it runs before the empty-lane-init effect
   * below in the same commit. See App.tsx's own comment at the call site.
   */
  emptyLaneInitSongRef: React.MutableRefObject<string | null>;
}

export function useLaneVisibility({
  song,
  laneState,
  artifacts,
  laneContentSources,
  panelMode,
  eventsLaneId,
  blockReviewsFile,
  emptyLaneInitSongRef,
}: LaneVisibilityInputs) {
  const laneById = useMemo(
    () => new Map(laneState.lanes.map((lane) => [lane.id, lane])),
    [laneState.lanes],
  );

  const laneArtifactsSettled = useMemo(() => {
    const keys = new Set<(typeof TIMELINE_KEYS)[number]>();
    for (const key of Object.values(SPARSE_LANE_ARTIFACT)) keys.add(key);
    for (const entry of Object.values(CANVAS_LANES)) keys.add(entry.key);
    for (const key of keys) {
      const status = artifacts[key].status;
      if (status === "idle" || status === "loading") return false;
    }
    return true;
  }, [artifacts]);

  // On song start, lanes with a ready-empty artifact should begin collapsed
  // and hidden (unchecked in the lane list).
  useEffect(() => {
    if (!song || emptyLaneInitSongRef.current === song) return;
    if (!laneArtifactsSettled) return;

    const updates: Array<{ id: string; hide: boolean; collapse: boolean }> = [];
    for (const lane of laneState.lanes) {
      let noData = false;

      const sparseKey = SPARSE_LANE_ARTIFACT[lane.id];
      if (sparseKey) {
        const art = artifacts[sparseKey];
        const blocks = buildLaneBlocks(lane.id, laneContentSources);
        noData = art.status === "ready" && blocks.length === 0;
      } else {
        const canvas = CANVAS_LANES[lane.id];
        if (canvas) {
          const art = artifacts[canvas.key];
          const source = {
            kind: canvas.kind,
            data: art.data as never,
          } as CanvasLaneSource;
          noData = art.status === "ready" && !canvasLaneHasData(source);
        }
      }

      if (noData && (lane.visible || lane.expanded)) {
        updates.push({ id: lane.id, hide: lane.visible, collapse: lane.expanded });
      }
    }

    for (const u of updates) {
      if (u.hide) laneState.setVisible(u.id, false);
      if (u.collapse) laneState.setExpanded(u.id, false);
    }

    emptyLaneInitSongRef.current = song;
  }, [song, laneArtifactsSettled, laneState, artifacts, laneContentSources, emptyLaneInitSongRef]);

  // Do not expand a lane when it is exactly in the same ready-empty state
  // that renders "No data in this artifact".
  const toggleExpandedGuarded = useCallback(
    (laneId: string) => {
      const lane = laneById.get(laneId);
      if (!lane) return;

      // Always allow collapsing.
      if (lane.expanded) {
        laneState.toggleExpanded(laneId);
        return;
      }

      const sparseKey = SPARSE_LANE_ARTIFACT[laneId];
      if (sparseKey) {
        const art = artifacts[sparseKey];
        const blocks = buildLaneBlocks(laneId, laneContentSources);
        const noData = art.status === "ready" && blocks.length === 0;
        if (noData) return;
        laneState.toggleExpanded(laneId);
        return;
      }

      const canvas = CANVAS_LANES[laneId];
      if (canvas) {
        const art = artifacts[canvas.key];
        const source = { kind: canvas.kind, data: art.data as never } as CanvasLaneSource;
        const noData = art.status === "ready" && !canvasLaneHasData(source);
        if (noData) return;
        laneState.toggleExpanded(laneId);
        return;
      }

      laneState.toggleExpanded(laneId);
    },
    [laneById, laneState, artifacts, laneContentSources],
  );

  // plan v1.5 item 3: props for the lane-events panel, or null when it is shut.
  const eventsPanel = useMemo(() => {
    if (panelMode !== "lane" || !eventsLaneId) return null;
    const key = SPARSE_LANE_ARTIFACT[eventsLaneId];
    const art = key ? artifacts[key] : null;
    const status = art?.status ?? "idle";
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

  // v3.7 item 1 — every current review for one lane, matched against that
  // lane's CURRENT blocks and indexed by (lane_id, start) for the verdict
  // control's O(1) per-block lookup. `undefined` for a lane not in
  // REVIEWABLE_LANE_IDS or with no reviews at all.
  const blockReviewIndexFor = useCallback(
    (laneId: string): Map<string, BlockReviewMatched> | null => {
      if (!blockReviewsFile || !REVIEWABLE_LANE_IDS.has(laneId)) return null;
      const laneReviews = blockReviewsFile.reviews.filter((r) => r.lane_id === laneId);
      if (!laneReviews.length) return new Map<string, BlockReviewMatched>();
      const blocks = buildLaneBlocks(laneId, laneContentSources);
      const matched = matchBlockReviews(
        laneReviews,
        new Map([[laneId, blocks.map((b) => b.start_s)]]),
      );
      return indexBlockReviews(matched);
    },
    [blockReviewsFile, laneContentSources],
  );

  return {
    toggleExpandedGuarded,
    eventsPanel,
    blockReviewIndexFor,
  };
}
