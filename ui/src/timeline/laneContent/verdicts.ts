// verdicts.ts — the Verdict Checks lane adapter (v3.11 item 24). Read-only
// view of `reference/pre-analysis/verdict.json`: one block per verdict row
// whose first-pass evidence names sections, spanning the first to the last of
// them (ids resolved through the published `sections.json`). Rows with no
// section evidence (BPM, vocals coverage) get no block.

import type {
  PendingProposalsFile,
  SectionRow,
  VerdictFile,
  VerdictOperatorAnswer,
  VerdictOutcome,
  VerdictRow,
} from "../../data/types";
import type { SparseBlock } from "../laneContent";
import { formatRange } from "./shared";

const TINT: Record<VerdictOutcome, string> = {
  confirmed: "verdictConfirmed",
  refuted: "verdictRefuted",
  unresolved: "verdictUnresolved",
};

/**
 * The operator's decided answer for a field: the one stored in verdict.json,
 * else the one implied by a decided `verdict_check` queue row (so the lane
 * agrees with the card the operator just answered, before any song reload).
 */
function operatorFor(
  row: VerdictRow,
  queue: PendingProposalsFile | null,
): VerdictOperatorAnswer | null {
  const stored = row.second_pass?.operator ?? null;
  if (stored) return stored;
  for (const p of queue?.proposals ?? []) {
    if (p.type !== "verdict_check" || p.verdict_check.field !== row.field) continue;
    if (p.status === "approved") return { answer: "confirmed", reason: null, check_id: p.id };
    if (p.status === "rejected")
      return { answer: "rejected", reason: p.rejection_reason, check_id: p.id };
  }
  return null;
}

/** The outcome a block is tinted by: the operator's answer, else a settled second pass, else the first pass. */
export function effectiveOutcome(
  row: VerdictRow,
  operator: VerdictOperatorAnswer | null,
): VerdictOutcome {
  if (operator) return operator.answer === "confirmed" ? "confirmed" : "refuted";
  return row.second_pass?.verdict ?? row.verdict;
}

export function verdictChecksContent(
  file: VerdictFile | null,
  sections: readonly SectionRow[],
  queue: PendingProposalsFile | null,
): SparseBlock[] {
  const byId = new Map(sections.map((s) => [s.section_id, s]));
  const blocks: SparseBlock[] = [];
  for (const row of file?.rows ?? []) {
    const spans = row.section_ids
      .map((id) => byId.get(id))
      .filter((s): s is SectionRow => !!s);
    if (!spans.length) continue;
    const start = Math.min(...spans.map((s) => s.start));
    const end = Math.max(...spans.map((s) => s.end));
    const operator = operatorFor(row, queue);
    const outcome = effectiveOutcome(row, operator);
    const sp = row.second_pass;
    const pending = (queue?.proposals ?? []).find(
      (p) =>
        p.type === "verdict_check" &&
        p.status === "pending" &&
        p.verdict_check.field === row.field,
    );
    const lines = [`${row.field}: first pass ${row.verdict}`];
    if (sp?.verdict)
      lines.push(`second pass: ${sp.verdict}${sp.wrong ? ` (wrong: ${sp.wrong})` : ""}`);
    if (operator)
      lines.push(
        `operator: ${operator.answer}${operator.reason ? ` — ${operator.reason}` : ""}`,
      );
    if (pending) lines.push("verdict_check pending");
    blocks.push({
      id: `verdictChecks-${row.field}`,
      start_s: start,
      end_s: end,
      label: row.field,
      wideLabel: `${row.field} · ${outcome}`,
      laneLabel: "Verdict Checks",
      caption: `${formatRange(start, end)} · ${outcome}`,
      reference: row.field,
      detail: lines.slice(1).join(" · ") || "-",
      summary: lines[0]!,
      tintId: TINT[outcome],
      tooltip: [`${formatRange(start, end)} · ${row.field} · ${outcome}`, ...lines].join("\n"),
      raw: {
        field: row.field,
        first_pass_verdict: row.verdict,
        second_pass: sp,
        operator,
        section_ids: row.section_ids,
        pending_check_id: pending?.id ?? null,
      },
    });
  }
  return blocks.sort((a, b) => a.start_s - b.start_s);
}
