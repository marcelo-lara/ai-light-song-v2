// Pure merge/build helpers for `PUT /api/proposal-decision/<song>`
// (vite.config.ts). Kept in their own module, outside vite.config.ts itself,
// so they're unit-testable without importing `vite` into the jsdom test
// environment (see ./runRequestGuard.ts's header for why that import is
// avoided).
//
// v3.9 item 6 — root cause: the approve flow used to read
// reference/human/human_hints.json client-side (`loadHumanHints`), append
// the new hint in memory, and PUT the whole array back — a classic
// read-modify-write race, with no locking on either side. Approving several
// proposals in quick succession fired several of those reads before any
// write landed, so more than one browser request held the SAME stale
// snapshot; every write after the first silently discarded the others'
// hints, because the PUT handler replaces the file wholesale. The surviving
// ids on *Tutta L'Italia* (`human-hint-6`…`18`, no gaps) are the tell: each
// id came from `existingHints.length + 1` computed against whatever stale
// array that request's read had returned, so the six that lost the race are
// exactly the low numbers (1-5) a losing write's id would have taken.
//
// The fix moves the append server-side, inside the one place a decision is
// recorded, and:
//  - serializes concurrent requests for the same song (`withSongLock`) so a
//    later read always sees an earlier write, never a stale copy;
//  - derives the next id from the ids actually on disk, never array length;
//  - makes the append idempotent (`hintAlreadyCaptured`) so retrying after a
//    partial failure (hint written, status flip failed) can never
//    double-append.

export interface MergeHint {
  id: string;
  title: string;
  start_time: number;
  end_time: number;
  summary: string;
  lighting_hint: string;
  captured_from?: string;
  type?: "hint" | "review" | "vocal";
}

export interface HintProposalLike {
  id: string;
  hint?: { start: number; end: number; title: string; summary?: string };
}

/** The `captured_from` marker a captured hint carries — also the dedupe key. */
export function proposalCapturedFromMarker(proposalId: string): string {
  return `MCP proposal ${proposalId}`;
}

/** True when `existingHints` already has an entry captured from this
 *  proposal — makes a retried approve (hint written, status flip failed)
 *  safe to re-run without double-appending. */
export function hintAlreadyCaptured(
  existingHints: MergeHint[],
  proposalId: string,
): boolean {
  const marker = proposalCapturedFromMarker(proposalId);
  return existingHints.some((h) => h.captured_from === marker);
}

/** Next `human-hint-<N>` id: one past the highest `<N>` already in use.
 *  NEVER `existingHints.length + 1` — the ids are not contiguous
 *  (hand-authored hints interleave with captured ones), and that scheme is
 *  exactly what produced the colliding/overwritten ids under the
 *  read-modify-write race this module replaces. */
export function nextHumanHintId(existingHints: MergeHint[]): string {
  let max = 0;
  for (const hint of existingHints) {
    const match = /^human-hint-(\d+)$/.exec(hint.id);
    if (match) max = Math.max(max, Number(match[1]));
  }
  return `human-hint-${max + 1}`;
}

/** Build the hint row to append for an approved hint proposal.
 *  `approvedTimes`, when given, is the operator's dragged correction and
 *  wins over the proposal's own start/end (mirrors the removed client-side
 *  `hintDraftFromProposal`). */
export function buildApprovedHintEntry(
  proposal: HintProposalLike,
  existingHints: MergeHint[],
  approvedTimes: { start: number; end: number } | null,
): MergeHint {
  const hint = proposal.hint;
  if (!hint) {
    throw new Error(`Proposal "${proposal.id}" is missing its "hint" payload.`);
  }
  return {
    id: nextHumanHintId(existingHints),
    title: hint.title,
    start_time: approvedTimes?.start ?? hint.start,
    end_time: approvedTimes?.end ?? hint.end,
    summary: hint.summary ?? "",
    lighting_hint: "",
    captured_from: proposalCapturedFromMarker(proposal.id),
    type: "review",
  };
}

// ---- verdict_check (v3.11 item 24) -------------------------------------
//
// The operator's answer to a queued `verdict_check` lands in
// reference/pre-analysis/verdict.json as
// `second_pass.fields.<field>.operator = {answer, reason, check_id}` and
// NOTHING else in that file changes: an entry the second pass already wrote
// keeps its `verdict` / `wrong` / `evidence` / `first_pass_verdict`; a field
// with no entry yet gets those four as `null` (the shape mcp/verdict.py's
// `_entry` documents), so an operator-only entry is valid.

export const VERDICT_FIELDS = ["drops", "has_build_ups", "chorus_is_drop", "vocals", "bpm"] as const;

export interface VerdictOperatorWrite {
  answer: "confirmed" | "rejected";
  reason: string | null;
  check_id: string;
}

/** Returns a copy of `doc` with `operator` set on `second_pass.fields.<field>`;
 *  `changed` is false when this very check already wrote the same answer (a
 *  retry after a partial failure). Throws, writing nothing, when the field has
 *  no first-pass verdict row, or a different answer/check is already stored
 *  (the operator's answer is final). */
export function applyVerdictOperator(
  doc: unknown,
  field: string,
  operator: VerdictOperatorWrite,
): { doc: Record<string, unknown>; changed: boolean } {
  if (!doc || typeof doc !== "object") throw new Error("verdict.json is not a JSON object.");
  if (!(VERDICT_FIELDS as readonly string[]).includes(field)) {
    throw new Error(`Verdict field "${field}" is not one of ${VERDICT_FIELDS.join(", ")}.`);
  }
  const root = doc as Record<string, unknown>;
  const verdicts = root.verdicts as { fields?: Record<string, unknown> } | undefined;
  if (!verdicts?.fields || typeof verdicts.fields[field] !== "object" || !verdicts.fields[field]) {
    throw new Error(`verdict.json has no first-pass verdict for "${field}".`);
  }
  const secondPass = (root.second_pass && typeof root.second_pass === "object"
    ? root.second_pass
    : {}) as Record<string, unknown>;
  const fields = (secondPass.fields && typeof secondPass.fields === "object"
    ? secondPass.fields
    : {}) as Record<string, unknown>;
  const existing =
    fields[field] && typeof fields[field] === "object"
      ? (fields[field] as Record<string, unknown>)
      : {};
  const stored = existing.operator as VerdictOperatorWrite | null | undefined;
  if (stored) {
    if (
      stored.check_id === operator.check_id &&
      stored.answer === operator.answer &&
      (stored.reason ?? null) === operator.reason
    ) {
      return { doc: root, changed: false };
    }
    throw new Error(`The operator already answered the "${field}" claim.`);
  }
  const entry = {
    verdict: null,
    wrong: null,
    evidence: null,
    first_pass_verdict: null,
    ...existing,
    operator,
  };
  return {
    doc: {
      ...root,
      second_pass: { ...secondPass, fields: { ...fields, [field]: entry } },
    },
    changed: true,
  };
}

// One promise-chain per song, serializing every proposal-decision request
// against it. Node has no real thread race, only interleaved `await`s, so
// chaining is enough to guarantee a later request's file reads always see an
// earlier request's writes rather than a stale snapshot — the actual
// mechanism of the bug this module fixes.
const songLocks = new Map<string, Promise<unknown>>();

export function withSongLock<T>(song: string, fn: () => Promise<T>): Promise<T> {
  const tail = songLocks.get(song) ?? Promise.resolve();
  const result = tail.then(fn, fn);
  songLocks.set(
    song,
    result.then(
      () => undefined,
      () => undefined,
    ),
  );
  return result;
}
