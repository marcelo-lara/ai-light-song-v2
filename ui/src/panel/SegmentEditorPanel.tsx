// SegmentEditorPanel.tsx — right-panel mode: the Human Sections editor.
// Mirrors HintEditorPanel.tsx's conventions (‹ › prev/next, new, delete,
// Cancel / Save, explicit-Save-only write), but against segments.json's
// shape: Start / End / Label (optional, one of SEGMENT_FUNCTION_NAMES — never free text) /
// Description (optional free text) / Energy / Tension.
//
// Save issues `PUT /api/human-sections/<song>` on explicit Save only (via
// `buildHumanSectionsPayload` + `saveHumanSections`), then hands the
// server-normalised file back to the parent for the optimistic update +
// reload. Selecting or creating a segment scrolls the timeline to it.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { buildHumanSectionsPayload, saveHumanSections } from "../data/saveHumanSections";
import { SEGMENT_FUNCTIONS } from "../data/segmentFunctions";
import type { HumanSegmentsFile } from "../data/types";

import { SegmentedRating } from "./LaneEventsPanel";
import { RightPanel } from "./RightPanel";
import { parseTimeInput } from "./hintDraft";
import {
  draftIdForSegmentReference,
  draftToSegment,
  nextSegmentId,
  segmentDraftFromSeed,
  segmentToDraft,
  type SegmentDraftFields,
  type SegmentSeed,
} from "./segmentDraft";

interface SegmentEditorPanelProps {
  song: string;
  file: HumanSegmentsFile | null;
  currentTime: number;
  /** id of the segment a Human Sections block click selected, if any */
  activeReference: string | null;
  /**
   * A pending "open on a pre-filled draft" request — from a double-click on
   * the Human Sections lane background.
   */
  seed?: SegmentSeed | null;
  onClose: () => void;
  onSaved: (file: HumanSegmentsFile) => void;
  onScrollToTime: (seconds: number) => void;
}

type SaveState =
  | { status: "idle" }
  | { status: "saving" }
  | { status: "error"; message: string }
  | { status: "success" };

function seedDrafts(file: HumanSegmentsFile | null): SegmentDraftFields[] {
  const segments = Array.isArray(file) ? file : [];
  return segments.map(segmentToDraft);
}

export function SegmentEditorPanel({
  song,
  file,
  currentTime,
  activeReference,
  seed,
  onClose,
  onSaved,
  onScrollToTime,
}: SegmentEditorPanelProps): React.JSX.Element {
  const [drafts, setDrafts] = useState<SegmentDraftFields[]>(() => seedDrafts(file));
  const [activeId, setActiveId] = useState<string>("");
  const [save, setSave] = useState<SaveState>({ status: "idle" });
  const baseSigRef = useRef<string>("");
  const seedNonceRef = useRef<number | null>(null);

  // Reseed when the on-disk file changes (song switch, external reload).
  useEffect(() => {
    const sig = JSON.stringify({ song, segments: file ?? [] });
    if (sig === baseSigRef.current) return;
    baseSigRef.current = sig;
    setDrafts(seedDrafts(file));
    setActiveId("");
    setSave({ status: "idle" });
  }, [song, file]);

  // Follow a Human Sections block selection.
  useEffect(() => {
    const id = draftIdForSegmentReference(activeReference, drafts);
    if (!id) return;
    setActiveId(id);
    setSave({ status: "idle" });
    const d = drafts.find((x) => x.id === id);
    if (d) onScrollToTime(Number(parseTimeInput(d.start)) || 0);
  }, [activeReference, drafts, onScrollToTime]);

  // Consume a "create segment" seed once per nonce. Appends a draft to the
  // current drafts (not a reseed), so it does not fight the on-disk reseed
  // effect above, which keys off `file` — unchanged by an unsaved draft.
  useEffect(() => {
    if (!seed || seed.nonce === seedNonceRef.current) return;
    seedNonceRef.current = seed.nonce;
    setDrafts((cur) => {
      const next = segmentDraftFromSeed(seed, cur);
      setActiveId(next.id);
      return [...cur, next];
    });
    setSave({ status: "idle" });
    onScrollToTime(Math.max(0, seed.start));
    const raf = requestAnimationFrame(() => {
      document.getElementById("segment-label")?.focus();
    });
    return () => cancelAnimationFrame(raf);
  }, [seed, onScrollToTime]);

  const activeIndex = drafts.findIndex((d) => d.id === activeId);
  const active = activeIndex >= 0 ? drafts[activeIndex]! : null;
  const activeLabelHint = active
    ? SEGMENT_FUNCTIONS.find((f) => f.name === active.label)?.hint ?? ""
    : "";

  const patchActive = useCallback(
    (patch: Partial<SegmentDraftFields>) => {
      setDrafts((cur) =>
        cur.map((d) => (d.id === activeId ? { ...d, ...patch } : d)),
      );
      setSave({ status: "idle" });
    },
    [activeId],
  );

  // Same seg-rating buttons the Human Hints block-energy panel uses: clicking
  // the pressed value again clears the axis back to "unrated" (never a
  // defaulted 1).
  const patchRating = useCallback(
    (_hintId: string, axis: "energy" | "tension", v: number) => {
      setDrafts((cur) =>
        cur.map((d) => {
          if (d.id !== activeId) return d;
          const current = d[axis] ? Number(d[axis]) : null;
          return { ...d, [axis]: current === v ? "" : String(v) };
        }),
      );
      setSave({ status: "idle" });
    },
    [activeId],
  );

  const selectByIndex = useCallback(
    (index: number) => {
      const d = drafts[index];
      if (!d) return;
      setActiveId(d.id);
      setSave({ status: "idle" });
      onScrollToTime(Number(parseTimeInput(d.start)) || 0);
    },
    [drafts, onScrollToTime],
  );

  const addSegment = useCallback(() => {
    setDrafts((cur) => {
      const start = Math.max(0, currentTime || 0);
      const next: SegmentDraftFields = {
        id: nextSegmentId(cur),
        // Left unset — the label is a fixed vocabulary value to pick, not a
        // free-text default.
        label: "",
        description: "",
        start: String(start),
        end: String(start),
        energy: "",
        tension: "",
      };
      setActiveId(next.id);
      return [...cur, next];
    });
    setSave({ status: "idle" });
    onScrollToTime(Math.max(0, currentTime || 0));
  }, [currentTime, onScrollToTime]);

  const deleteActive = useCallback(() => {
    if (!activeId) return;
    setDrafts((cur) => cur.filter((d) => d.id !== activeId));
    setActiveId("");
    setSave({ status: "idle" });
  }, [activeId]);

  const doSave = useCallback(async () => {
    setSave({ status: "saving" });
    try {
      const payload = buildHumanSectionsPayload(drafts.map(draftToSegment));
      const written = await saveHumanSections(song, payload);
      baseSigRef.current = JSON.stringify({ song, segments: written });
      setDrafts(seedDrafts(written));
      setSave({ status: "success" });
      onSaved(written);
    } catch (err) {
      setSave({
        status: "error",
        message: err instanceof Error ? err.message : "Unable to save human sections.",
      });
    }
  }, [drafts, song, onSaved]);

  const header = useMemo(
    () => (
      <div className="hint-editor__header">
        <button
          type="button"
          className="tp tp--round"
          aria-label="Previous segment"
          disabled={drafts.length === 0}
          onClick={() =>
            selectByIndex(activeIndex <= 0 ? drafts.length - 1 : activeIndex - 1)
          }
        >
          <i className="ph ph-caret-left" />
        </button>
        <button
          type="button"
          className="tp tp--round"
          aria-label="Next segment"
          disabled={drafts.length === 0}
          onClick={() =>
            selectByIndex(activeIndex >= drafts.length - 1 ? 0 : activeIndex + 1)
          }
        >
          <i className="ph ph-caret-right" />
        </button>
        <span className="app-rightpanel__kicker">Human Section</span>
      </div>
    ),
    [drafts.length, activeIndex, selectByIndex],
  );

  const footer = (
    <>
      {save.status === "error" && (
        <p className="hint-editor__status is-error">{save.message}</p>
      )}
      {save.status === "success" && (
        <p className="hint-editor__status is-ok">Saved to segments.json.</p>
      )}
      <div className="hint-editor__actions">
        <button type="button" className="btn btn-ghost" onClick={onClose}>
          Cancel
        </button>
        <button
          type="button"
          className="btn btn-primary"
          disabled={save.status === "saving"}
          onClick={() => void doSave()}
        >
          {save.status === "saving" ? "Saving…" : "Save"}
        </button>
      </div>
    </>
  );

  return (
    <RightPanel
      open
      onClose={onClose}
      header={header}
      footer={footer}
      aria-label="Segment editor"
      data-testid="segment-editor"
      data-segment-id={activeId || undefined}
    >
      <div className="hint-editor__toolbar">
        <button type="button" className="btn btn-secondary btn-sm" onClick={addSegment}>
          <i className="ph ph-plus" /> New segment
        </button>
        <button
          type="button"
          className="btn btn-ghost btn-sm"
          disabled={!active}
          onClick={deleteActive}
        >
          <i className="ph ph-trash" /> Delete
        </button>
      </div>

      {!active ? (
        <p className="hint-editor__empty">
          {drafts.length === 0
            ? "No segments yet. “New segment” starts one at the playhead."
            : "Select a segment with ‹ › or click its pill on the timeline."}
        </p>
      ) : (
        <>
          <div className="hint-editor__row2">
            <div className="field">
              <label htmlFor="segment-start">Start</label>
              <div className="hint-editor__time">
                <input
                  id="segment-start"
                  className="input"
                  value={active.start}
                  inputMode="decimal"
                  onChange={(e) => patchActive({ start: e.target.value })}
                  onBlur={(e) => patchActive({ start: parseTimeInput(e.target.value) })}
                />
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  title="Set start to playhead"
                  onClick={() => patchActive({ start: String(Number((currentTime || 0).toFixed(3))) })}
                >
                  ⤓
                </button>
              </div>
            </div>
            <div className="field">
              <label htmlFor="segment-end">End</label>
              <div className="hint-editor__time">
                <input
                  id="segment-end"
                  className="input"
                  value={active.end}
                  inputMode="decimal"
                  onChange={(e) => patchActive({ end: e.target.value })}
                  onBlur={(e) => patchActive({ end: parseTimeInput(e.target.value) })}
                />
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  title="Set end to playhead"
                  onClick={() => patchActive({ end: String(Number((currentTime || 0).toFixed(3))) })}
                >
                  ⤓
                </button>
              </div>
            </div>
          </div>

          <div className="field">
            <label htmlFor="segment-label">Label</label>
            <select
              id="segment-label"
              className="input"
              value={active.label}
              onChange={(e) => patchActive({ label: e.target.value })}
            >
              <option value="">Unset</option>
              {SEGMENT_FUNCTIONS.map((f) => (
                <option key={f.name} value={f.name} title={f.hint}>
                  {f.name}
                </option>
              ))}
            </select>
            {activeLabelHint && (
              <p className="hint-editor__field-hint">{activeLabelHint}</p>
            )}
          </div>

          <div className="field">
            <label htmlFor="segment-description">Description</label>
            <textarea
              id="segment-description"
              className="input"
              rows={3}
              style={{ resize: "vertical", fontFamily: "var(--font-body)" }}
              value={active.description}
              onChange={(e) => patchActive({ description: e.target.value })}
            />
          </div>

          <div className="lane-events__rating">
            <SegmentedRating
              axis="energy"
              hintId={active.id}
              value={active.energy ? Number(active.energy) : null}
              onPick={patchRating}
            />
            <SegmentedRating
              axis="tension"
              hintId={active.id}
              value={active.tension ? Number(active.tension) : null}
              onPick={patchRating}
            />
          </div>
        </>
      )}
    </RightPanel>
  );
}
