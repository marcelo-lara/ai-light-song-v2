// hintDraft.ts — the hint-editor draft model and its mapping to the
// human_hints.json payload (design notes §4).
//
//   draft field   | on-disk key    | notes
//   ------------- | -------------- | -----------------------------
//   start / end   | start_time / end_time (seconds)
//   title         | title
//   musical       | summary        (textarea, 3 rows)
//   lighting      | lighting_hint  (textarea, 3 rows)
//
// Start/End are held in the draft as canonical **seconds strings** (matching
// the previous app's numeric inputs and `buildHumanHintsPayload`'s `Number(...)`
// coercion); `parseTimeInput` additionally accepts `m:ss(.s)` for convenience.

import type { HintDraft } from "../data/saveHumanHints";
import type { HumanHint } from "../data/types";

export interface HintDraftFields {
  id: string;
  title: string;
  start: string;
  end: string;
  musical: string;
  lighting: string;
}

/** Accept "83.4" or "1:23.4" -> canonical seconds string ("83.4"). Empty and
 *  unparseable input pass through unchanged so validation can report it. */
export function parseTimeInput(raw: string): string {
  const text = String(raw ?? "").trim();
  if (text === "") return "";
  const colon = text.match(/^(\d+):([0-5]?\d(?:\.\d+)?)$/);
  if (colon) {
    const minutes = Number(colon[1]);
    const seconds = Number(colon[2]);
    return String(minutes * 60 + seconds);
  }
  return text;
}

export function formatSeconds(seconds: number): string {
  return Number.isFinite(seconds) ? String(Number(seconds.toFixed(3))) : "0";
}

export function hintToDraft(hint: HumanHint): HintDraftFields {
  return {
    id: String(hint.id ?? ""),
    title: String(hint.title ?? ""),
    start: formatSeconds(Number(hint.start_time ?? 0)),
    end: formatSeconds(Number(hint.end_time ?? 0)),
    musical: typeof hint.summary === "string" ? hint.summary : "",
    lighting: typeof hint.lighting_hint === "string" ? hint.lighting_hint : "",
  };
}

/** Draft -> the loose shape `buildHumanHintsPayload` validates + normalises. */
export function draftToHint(draft: HintDraftFields): HintDraft {
  return {
    id: draft.id,
    title: draft.title,
    start_time: parseTimeInput(draft.start),
    end_time: parseTimeInput(draft.end),
    summary: draft.musical,
    lighting_hint: draft.lighting,
  };
}

/** Next `hint-NNN` id given the existing drafts. */
export function nextHintId(existing: readonly HintDraftFields[]): string {
  const max = existing.reduce((acc, d) => {
    const m = /^hint-(\d+)$/.exec(d.id.trim());
    const n = m ? Number(m[1]) : NaN;
    return Number.isFinite(n) && n > acc ? n : acc;
  }, 0);
  return `hint-${String(max + 1).padStart(3, "0")}`;
}

export function newHintDraft(
  currentTime: number,
  existing: readonly HintDraftFields[],
): HintDraftFields {
  const t = formatSeconds(Math.max(0, currentTime || 0));
  return {
    id: nextHintId(existing),
    title: `Hint ${existing.length + 1}`,
    start: t,
    end: t,
    musical: "",
    lighting: "",
  };
}

/** Match a Human Hints block selection back to a draft id. */
export function draftIdForReference(
  reference: string | null | undefined,
  drafts: readonly HintDraftFields[],
): string {
  const ref = String(reference ?? "").trim();
  if (!ref) return "";
  return drafts.find((d) => d.id === ref)?.id ?? "";
}
