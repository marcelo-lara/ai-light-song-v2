// HintEditorPanel.tsx — right-panel mode: the Human Hints editor (design §4b).
//
// Start / End / Title / Musical hint / Lighting hint, ‹ › prev/next-hint,
// new hint, delete active hint, set start/end to playhead, Cancel / Save.
// Save issues `PUT /api/human-hints/<song>` on explicit Save only (via
// `buildHumanHintsPayload` + `saveHumanHints`), then hands the server-normalised
// file back to the parent for the optimistic update + reload. Selecting or
// creating a hint scrolls the timeline to it.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { buildHumanHintsPayload, saveHumanHints } from "../data/saveHumanHints";
import type { HumanHintsFile } from "../data/types";

import { RightPanel } from "./RightPanel";
import {
  draftIdForReference,
  draftToHint,
  hintToDraft,
  newHintDraft,
  parseTimeInput,
  type HintDraftFields,
} from "./hintDraft";

interface HintEditorPanelProps {
  song: string;
  file: HumanHintsFile | null;
  currentTime: number;
  /** id of the hint a Human Hints block click selected, if any */
  activeReference: string | null;
  onClose: () => void;
  onSaved: (file: HumanHintsFile) => void;
  onScrollToTime: (seconds: number) => void;
}

type SaveState =
  | { status: "idle" }
  | { status: "saving" }
  | { status: "error"; message: string }
  | { status: "success" };

function seedDrafts(file: HumanHintsFile | null): HintDraftFields[] {
  const hints = Array.isArray(file?.human_hints) ? file!.human_hints : [];
  return hints.map(hintToDraft);
}

export function HintEditorPanel({
  song,
  file,
  currentTime,
  activeReference,
  onClose,
  onSaved,
  onScrollToTime,
}: HintEditorPanelProps): React.JSX.Element {
  const [drafts, setDrafts] = useState<HintDraftFields[]>(() => seedDrafts(file));
  const [activeId, setActiveId] = useState<string>("");
  const [save, setSave] = useState<SaveState>({ status: "idle" });
  const baseSigRef = useRef<string>("");

  // Reseed when the on-disk file changes (song switch, external reload).
  useEffect(() => {
    const sig = JSON.stringify({ song, hints: file?.human_hints ?? [] });
    if (sig === baseSigRef.current) return;
    baseSigRef.current = sig;
    setDrafts(seedDrafts(file));
    setActiveId("");
    setSave({ status: "idle" });
  }, [song, file]);

  // Follow a Human Hints block selection.
  useEffect(() => {
    const id = draftIdForReference(activeReference, drafts);
    if (!id) return;
    setActiveId(id);
    setSave({ status: "idle" });
    const d = drafts.find((x) => x.id === id);
    if (d) onScrollToTime(Number(parseTimeInput(d.start)) || 0);
  }, [activeReference, drafts, onScrollToTime]);

  const activeIndex = drafts.findIndex((d) => d.id === activeId);
  const active = activeIndex >= 0 ? drafts[activeIndex]! : null;

  const patchActive = useCallback(
    (patch: Partial<HintDraftFields>) => {
      setDrafts((cur) =>
        cur.map((d) => (d.id === activeId ? { ...d, ...patch } : d)),
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

  const addHint = useCallback(() => {
    setDrafts((cur) => {
      const next = newHintDraft(currentTime, cur);
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
      const payload = buildHumanHintsPayload(
        file?.song_name || song,
        drafts.map(draftToHint),
      );
      const written = await saveHumanHints(song, payload);
      baseSigRef.current = JSON.stringify({
        song,
        hints: written.human_hints,
      });
      setDrafts(seedDrafts(written));
      setSave({ status: "success" });
      onSaved(written);
    } catch (err) {
      setSave({
        status: "error",
        message: err instanceof Error ? err.message : "Unable to save human hints.",
      });
    }
  }, [drafts, file?.song_name, song, onSaved]);

  const header = useMemo(
    () => (
      <div className="hint-editor__header">
        <button
          type="button"
          className="tp tp--round"
          aria-label="Previous hint"
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
          aria-label="Next hint"
          disabled={drafts.length === 0}
          onClick={() =>
            selectByIndex(activeIndex >= drafts.length - 1 ? 0 : activeIndex + 1)
          }
        >
          <i className="ph ph-caret-right" />
        </button>
        <span className="app-rightpanel__kicker">Human Hint</span>
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
        <p className="hint-editor__status is-ok">Saved to human_hints.json.</p>
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
      aria-label="Hint editor"
      data-testid="hint-editor"
      data-hint-id={activeId || undefined}
    >
      <div className="hint-editor__toolbar">
        <button type="button" className="btn btn-secondary btn-sm" onClick={addHint}>
          <i className="ph ph-plus" /> New hint
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
            ? "No hints yet. “New hint” starts one at the playhead."
            : "Select a hint with ‹ › or click its pill on the timeline."}
        </p>
      ) : (
        <>
          <div className="hint-editor__row2">
            <div className="field">
              <label htmlFor="hint-start">Start</label>
              <div className="hint-editor__time">
                <input
                  id="hint-start"
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
              <label htmlFor="hint-end">End</label>
              <div className="hint-editor__time">
                <input
                  id="hint-end"
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
            <label htmlFor="hint-title">Title</label>
            <input
              id="hint-title"
              className="input"
              value={active.title}
              onChange={(e) => patchActive({ title: e.target.value })}
            />
          </div>

          <div className="field">
            <label htmlFor="hint-musical">Musical hint</label>
            <textarea
              id="hint-musical"
              className="input"
              rows={3}
              style={{ resize: "vertical", fontFamily: "var(--font-body)" }}
              value={active.musical}
              onChange={(e) => patchActive({ musical: e.target.value })}
            />
          </div>

          <div className="field">
            <label htmlFor="hint-lighting">Lighting hint</label>
            <textarea
              id="hint-lighting"
              className="input"
              rows={3}
              style={{ resize: "vertical", fontFamily: "var(--font-body)" }}
              value={active.lighting}
              onChange={(e) => patchActive({ lighting: e.target.value })}
            />
          </div>
        </>
      )}
    </RightPanel>
  );
}
